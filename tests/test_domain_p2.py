"""Regressions reproduced during the PostgreSQL milestone."""
from copy import deepcopy
from decimal import Decimal

from fastapi.testclient import TestClient

from anti_drop_ml.adapter import evaluate_snapshot
from anti_drop_ml.make_labeling_template import make_snapshot, transaction
from main import app
from src.detector import analyze_transactions
from src.sim_security import start_number_change

client = TestClient(app)


def test_zero_operations_cannot_trigger_night_or_sim_rules():
    rows = [{'id': str(i), 'user_id': 'synthetic', 'ts': '2026-10-07T01:00:00+03:00',
             'amount': 0, 'type': 'incoming_p2p', 'sim_changed_days_ago': 0} for i in range(5)]
    decision = analyze_transactions(rows)
    assert decision['score'] == 0
    assert decision['level'] == 'INSUFFICIENT_DATA'
    assert decision['metrics']['excluded_zero_count'] == 5


def test_empty_snapshot_is_explicitly_insufficient():
    decision = evaluate_snapshot(make_snapshot([]))
    assert decision.level == 'INSUFFICIENT_DATA'
    assert decision.status == 'insufficient_data'
    assert 'insufficient_data' in decision.reason_codes


def test_composite_event_identity():
    row = transaction()
    other = {**row, 'source': 'src_12345678'}
    assert client.post('/api/v1/risk/evaluate', json=make_snapshot([row, other])).status_code == 200
    other['source'] = 'src_00000000'
    assert client.post('/api/v1/risk/evaluate', json=make_snapshot([row, other])).status_code == 422


def test_boolean_sim_is_not_integer_age():
    payload = {'transactions': [{'id': '1', 'ts': '2026-10-07T10:00:00Z', 'amount': 1, 'sim_changed_days_ago': True}]}
    assert client.post('/api/analyze', json=payload).status_code == 422


def test_legacy_future_date_without_explicit_time_is_excluded():
    payload = {'transactions': [{'id': str(i), 'ts': '2099-01-01T01:00:00Z', 'amount': 100,
                                'type': 'incoming_p2p', 'counterparty': str(i)} for i in range(5)]}
    response = client.post('/api/analyze', json=payload)
    assert response.status_code == 200
    assert response.json()['score'] == 0
    assert response.json()['metrics']['excluded_future_count'] == 5


def test_phone_canonical_and_cooldown_timezone():
    for old in ('79160000001', '89160000001', '+7 (916) 000-00-01'):
        assert not start_number_change(old, '+79160000001', True, True)['ok']
    assert '+00:00' in start_number_change('+79160000001', '+79160000002', True, True)['cooldown_until']


def test_money_is_exact_decimal_in_legacy_boundary():
    from models import Transaction
    assert Transaction(id='1', ts='2026-10-08T00:00:00Z', amount='0.01').amount == Decimal('0.01')


def test_warning_does_not_imply_bank_action_or_legal_verdict():
    from src.alerts import build_stop_drop_alert
    from src.quiz import STORIES
    body = build_stop_drop_alert('ru', 0, 0, 85)['body']
    assert 'банк не уведомлён' in body
    assert 'деньги приходят' not in body
    assert '187' not in body and '115-ФЗ' not in body
    assert not any('Итог: блок' in story['text'] for story in STORIES)


def test_request_size_and_privacy():
    response = client.post('/api/analyze', content=b'x'*(2*1024*1024+1))
    assert response.status_code == 413
    response = client.post('/api/analyze', json={'transactions': [{'ts': 'SECRET_INVALID_VALUE', 'amount': 1}]})
    assert response.status_code == 422
    assert 'SECRET_INVALID_VALUE' not in response.text
    assert response.json()['request_id'] == response.headers['X-Request-ID']


def test_extreme_datetime_and_money_return_422():
    for value in ('0001-01-01T00:00:00Z', '0001-01-01T00:00:00+14:00', '9999-12-31T23:59:59-14:00'):
        payload = make_snapshot([transaction()])
        payload['analysis_at'] = value
        assert client.post('/api/v1/risk/evaluate', json=payload).status_code == 422
        assert client.post('/api/analyze', json={'transactions': [{'id': '1', 'ts': value, 'amount': 1}]}).status_code == 422
    for amount in ('1e999999999', '1e100', '1000000000001', '0.001'):
        assert client.post('/api/analyze', json={'transactions': [{'id': '1', 'ts': '2026-10-08T00:00:00Z', 'amount': amount}]}).status_code == 422


def test_unknown_keys_do_not_reflect_sensitive_identifiers():
    payload = make_snapshot([])
    payload['SENSITIVE_UNKNOWN_KEY'] = 'SENSITIVE_VALUE'
    response = client.post('/api/v1/risk/evaluate', json=payload)
    assert response.status_code == 422
    assert 'SENSITIVE_' not in response.text


def test_timezone_conversion_cannot_escape_supported_utc_years():
    for value in ('2000-01-01T00:00:00+14:00', '2100-12-31T23:59:59-14:00'):
        assert client.post('/api/analyze', json={'transactions': [{'id': '1', 'ts': value, 'amount': 1}]}).status_code == 422
        payload = make_snapshot([transaction()])
        payload['analysis_at'] = value
        assert client.post('/api/v1/risk/evaluate', json=payload).status_code == 422
        payload = make_snapshot([transaction()])
        payload['transactions'][0]['occurred_at'] = value
        assert client.post('/api/v1/risk/evaluate', json=payload).status_code == 422
