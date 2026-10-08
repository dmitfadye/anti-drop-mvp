"""Real PostgreSQL tests. No SQLite or memory substitute is accepted."""
import json
import os
import secrets
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from anti_drop_ml.make_labeling_template import make_snapshot, transaction
from main import app
from src.database import CaseEvent, IdempotencyRecord, RiskEvaluation, SandboxCase, engine_for, get_engine


@pytest.fixture
def sandbox(monkeypatch):
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('TEST_DATABASE_URL required: these tests need actual PostgreSQL')
    if not make_url(url).database.startswith('antidrop_test'):
        pytest.fail('Use a dedicated antidrop_test* database only')
    monkeypatch.setenv('DATABASE_URL', url)
    subjects = ['sub_' + uuid4().hex for _ in range(2)]
    tokens = [secrets.token_hex(32) for _ in range(2)]
    monkeypatch.setenv('SANDBOX_TOKENS', json.dumps(dict(zip(tokens, subjects))))
    command.upgrade(Config('alembic.ini'), 'head')
    client = TestClient(app, raise_server_exceptions=False)
    headers = [{'Authorization': 'Bearer ' + token} for token in tokens]
    yield client, subjects, headers
    with Session(get_engine()) as session, session.begin():
        session.execute(delete(RiskEvaluation).where(RiskEvaluation.subject_ref.in_(subjects)))


def evaluation(sandbox, index=0):
    client, subjects, headers = sandbox
    payload = make_snapshot([transaction(i, minutes=40-i*5, sim=0) for i in range(5)] + [transaction(9, minutes=1, direction='out', amount=1400000)])
    payload['subject_ref'] = subjects[index]
    response = client.post('/sandbox/evaluations', json=payload, headers=headers[index])
    assert response.status_code == 200, response.text
    assert response.json()['level'] == 'RED'
    return response.json()


def create(sandbox, evaluation_id, key='demo-key', index=0, **extra):
    client, _, headers = sandbox
    return client.post('/sandbox/cases', json={'evaluation_id': evaluation_id, 'contact_reason': 'need_assistance', **extra},
                       headers={**headers[index], 'Idempotency-Key': key})


def test_migrations_and_end_to_end_replay(sandbox):
    client, _, headers = sandbox
    decision = evaluation(sandbox)
    assert decision['sandbox'] is True
    assert decision['source_type'] == 'synthetic'
    assert decision['score_interpretation'] == 'deterministic_rule_score_not_probability'
    response = create(sandbox, decision['evaluation_id'])
    assert response.status_code == 201, response.text
    case = response.json()
    assert create(sandbox, decision['evaluation_id']).json() == case
    assert client.get('/sandbox/cases/' + case['case_id'], headers=headers[0]).json() == case
    assert client.get('/sandbox/cases', headers=headers[0]).json() == [case]
    assert client.get('/sandbox/evaluations/' + decision['evaluation_id'], headers=headers[0]).json() == decision
    assert create(sandbox, decision['evaluation_id'], selected_language='en').status_code == 409
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count()).select_from(CaseEvent).where(CaseEvent.case_id == case['case_id'])) == 1


def test_concurrent_idempotent_requests(sandbox):
    identifier = evaluation(sandbox)['evaluation_id']
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(lambda _: create(sandbox, identifier), range(16)))
    assert {r.status_code for r in responses} == {201}
    assert len({r.json()['case_id'] for r in responses}) == 1
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count()).select_from(SandboxCase).where(SandboxCase.evaluation_id == identifier)) == 1


def test_cross_subject_isolation_and_same_key(sandbox):
    client, subjects, headers = sandbox
    first = evaluation(sandbox)['evaluation_id']
    case = create(sandbox, first).json()
    assert client.get('/sandbox/cases/' + case['case_id'], headers=headers[1]).status_code == 404
    assert client.get('/sandbox/evaluations/' + first, headers=headers[1]).status_code == 404
    assert create(sandbox, first, index=1).status_code == 404
    assert client.get('/sandbox/cases', headers=headers[1]).json() == []
    payload = make_snapshot([transaction()])
    payload['subject_ref'] = subjects[1]
    assert client.post('/sandbox/evaluations', json=payload, headers=headers[0]).status_code == 403
    second = evaluation(sandbox, index=1)['evaluation_id']
    response = create(sandbox, second, index=1)
    assert response.status_code == 201
    assert response.json()['case_id'] != case['case_id']


def test_auth_and_validation(sandbox):
    client, _, headers = sandbox
    assert client.get('/sandbox/cases').status_code == 401
    assert client.get('/sandbox/cases', headers={'Authorization': 'Bearer ' + 'invalid'*8}).status_code == 401
    identifier = evaluation(sandbox)['evaluation_id']
    assert create(sandbox, '0'*64).status_code == 404
    assert create(sandbox, 'invalid').status_code == 422
    assert create(sandbox, identifier, key=' ').status_code == 422
    assert create(sandbox, identifier, key='x'*129).status_code == 422
    assert client.post('/sandbox/cases', json={'evaluation_id': identifier, 'contact_reason': 'need_assistance'}, headers=headers[0]).status_code == 422
    payload = make_snapshot([])
    payload.update(subject_ref=sandbox[1][0], source_type='bank_trusted')
    response = client.post('/sandbox/evaluations', json=payload, headers=headers[0])
    assert response.status_code == 422
    assert 'bank_trusted' not in response.text
    assert response.json()['request_id'] == response.headers['X-Request-ID']


def test_atomic_rollback_on_audit_write_failure(sandbox):
    identifier = evaluation(sandbox)['evaluation_id']

    def fail(*_):
        raise SQLAlchemyError('injected audit failure with secret parameters')

    event.listen(CaseEvent, 'before_insert', fail)
    try:
        response = create(sandbox, identifier)
    finally:
        event.remove(CaseEvent, 'before_insert', fail)
    assert response.status_code == 503
    assert 'secret parameters' not in response.text
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count()).select_from(SandboxCase).where(SandboxCase.evaluation_id == identifier)) == 0
        assert session.scalar(select(func.count()).select_from(IdempotencyRecord).where(IdempotencyRecord.subject_ref == sandbox[1][0])) == 0
    assert create(sandbox, identifier).status_code == 201


def test_database_unique_and_owner_constraints(sandbox):
    identifier = evaluation(sandbox)['evaluation_id']
    create(sandbox, identifier)
    with Session(get_engine()) as session:
        original = session.scalar(select(IdempotencyRecord).where(IdempotencyRecord.subject_ref == sandbox[1][0]))
        values = {k: getattr(original, k) for k in ('subject_ref', 'operation_type', 'idempotency_key', 'request_fingerprint', 'response_reference')}
    with pytest.raises(IntegrityError), Session(get_engine()) as session, session.begin():
        session.add(IdempotencyRecord(**values))
    with pytest.raises(IntegrityError), Session(get_engine()) as session, session.begin():
        session.add(SandboxCase(evaluation_id=identifier, subject_ref=sandbox[1][1], selected_language='ru', contact_reason='need_assistance'))


def test_persistence_in_new_process(sandbox):
    identifier = evaluation(sandbox)['evaluation_id']
    case = create(sandbox, identifier).json()
    code = """import os
from fastapi.testclient import TestClient
from main import app
r = TestClient(app).get('/sandbox/cases/' + os.environ['CASE_TO_VERIFY'], headers={'Authorization': os.environ['AUTH_TO_VERIFY']})
assert r.status_code == 200, r.text
assert r.json()['case_id'] == os.environ['CASE_TO_VERIFY']
print('fresh-process persistence verified')
"""
    env = {**os.environ, 'CASE_TO_VERIFY': case['case_id'], 'AUTH_TO_VERIFY': sandbox[2][0]['Authorization']}
    result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr


def test_database_failure_returns_no_success(sandbox, monkeypatch):
    identifier = evaluation(sandbox)['evaluation_id']
    monkeypatch.setenv('DATABASE_URL', 'postgresql+psycopg://unavailable@127.0.0.1:1/unavailable')
    response = create(sandbox, identifier)
    assert response.status_code == 503
    assert response.json()['error_code'] == 'DATABASE_UNAVAILABLE'
    assert 'postgresql' not in response.text
    monkeypatch.setenv('DATABASE_URL', os.environ['TEST_DATABASE_URL'])


def test_missing_database_never_falls_back_to_memory(sandbox, monkeypatch):
    monkeypatch.delenv('DATABASE_URL')
    response = sandbox[0].get('/sandbox/cases', headers=sandbox[2][0])
    assert response.status_code == 503
    monkeypatch.setenv('DATABASE_URL', os.environ['TEST_DATABASE_URL'])
