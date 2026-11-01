"""Education: deterministic calendar, grading, atomic PostgreSQL progression."""
import json
import os
import secrets
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from main import app
from src import learning
from src.database import get_engine
from src.learning_models import LearningProfile, LearningReplay

COURSE = {'version': 'test-v1', 'modules': [{'id': 'safe', 'title': 'Безопасность',
          'summary': 'Учебная проверка', 'minutes': 3, 'article': ['Не сообщайте коды.'],
          'cards': [{'id': 'c1', 'prompt': 'Сообщать код?', 'options': ['Нет', 'Да'],
                     'correct': 0, 'explanation': 'Код сохраняйте в тайне.'}],
          'quiz': [{'id': 'q1', 'prompt': 'Перезвонить по официальному номеру?',
                    'options': ['Да', 'Нет'], 'correct': 0, 'explanation': 'Проверяйте канал независимо.'}]}]}


@pytest.fixture(autouse=True)
def course(monkeypatch):
    monkeypatch.setattr(learning, 'load_course', lambda: COURSE)


def test_catalog_never_discloses_answers():
    response = TestClient(app).get('/api/v1/learning/catalog')
    assert response.status_code == 200
    assert response.json()['modules'][0]['cards'][0] == {'id': 'c1', 'prompt': 'Сообщать код?', 'options': ['Нет', 'Да']}
    assert 'correct' not in response.text and 'explanation' not in response.text


def test_grading_requires_exact_questions_and_real_integer_indices():
    module = COURSE['modules'][0]
    valid = learning.CompletionRequest(module_id='safe', format='lesson', answers={'c1': 0, 'q1': 0}, idempotency_key='test')
    assert learning.grade(module, valid)['passed']
    valid.answers.pop('c1')
    with pytest.raises(Exception) as error:
        learning.grade(module, valid)
    assert error.value.status_code == 422
    with pytest.raises(ValueError):
        learning.CompletionRequest(module_id='safe', format='quiz', answers={'q1': True}, idempotency_key='test')


def test_practice_returns_card_feedback_without_storage_or_xp(monkeypatch):
    course = json.loads(json.dumps(COURSE))
    course['modules'][0]['cards'][0].update(safe_action='Проверьте канал связи.', danger_sign='Просят код.')
    monkeypatch.setattr(learning, 'load_course', lambda: course)
    def no_storage():
        pytest.fail('Practice must not access storage')
    monkeypatch.setattr(learning, 'get_engine', no_storage)
    client = TestClient(app)
    catalog = client.get('/api/v1/learning/catalog').json()
    assert catalog['version'] == catalog['course_version'] == COURSE['version']
    assert 'safe_action' not in catalog['modules'][0]['cards'][0]
    response = client.post('/api/v1/learning/practice', json={
        'module_id': 'safe', 'question_id': 'c1', 'answer': 1, 'course_version': COURSE['version']})
    assert response.status_code == 200
    assert response.json() == {'course_version': COURSE['version'], 'question_id': 'c1',
        'correct': False, 'correct_index': 0, 'explanation': course['modules'][0]['cards'][0]['explanation'],
        'source_needed': False, 'safe_action': 'Проверьте канал связи.', 'danger_sign': 'Просят код.'}
    assert client.post('/api/v1/learning/practice', json={
        'module_id': 'safe', 'question_id': 'c1', 'answer': 0}).json()['correct'] is True


@pytest.mark.parametrize('updates,status', [
    ({'question_id': 'q1'}, 404),  # Final quiz questions cannot be practiced.
    ({'module_id': 'missing'}, 404),
    ({'answer': -1}, 422), ({'answer': 2}, 422),
    ({'answer': True}, 422), ({'answer': '0'}, 422),
    ({'course_version': 'obsolete'}, 409), ({'xp': 100}, 422),
])
def test_practice_rejects_invalid_answers_and_stale_content(updates, status):
    payload = {'module_id': 'safe', 'question_id': 'c1', 'answer': 0, **updates}
    response = TestClient(app).post('/api/v1/learning/practice', json=payload)
    assert response.status_code == status


def test_new_completion_checks_course_version_but_legacy_request_still_passes(monkeypatch):
    monkeypatch.setattr(learning, 'mutate', lambda subject, operation, body, action:
                        action(learning.empty_state(), date(2026, 10, 1)))
    legacy = learning.CompletionRequest(module_id='safe', format='quiz', answers={'q1': 0}, idempotency_key='legacy')
    assert 'course_version' not in legacy.model_dump(exclude_none=True)
    assert learning.complete(legacy, 'sub_12345678')['result']['passed']
    current = legacy.model_copy(update={'course_version': COURSE['version']})
    assert learning.complete(current, 'sub_12345678')['course_version'] == COURSE['version']
    stale = legacy.model_copy(update={'course_version': 'obsolete'})
    with pytest.raises(Exception) as error:
        learning.complete(stale, 'sub_12345678')
    assert error.value.status_code == 409


def test_independent_assessment_cannot_be_passed_by_practicing_cards():
    module = json.loads(json.dumps(COURSE['modules'][0]))
    module['assessment_independent'] = True
    module['cards'] = [{**module['cards'][0], 'id': f'practice-{index}'} for index in range(6)]
    body = learning.CompletionRequest(module_id='safe', format='lesson',
        answers={**{q['id']: 0 for q in module['cards']}, 'q1': 1}, idempotency_key='assessment')
    result = learning.grade(module, body)
    assert result['score'] == 6 and result['total'] == 7
    assert result['assessment_score'] == 0 and result['assessment_total'] == 1
    assert result['passed'] is False
    body.answers['q1'] = 0
    assert learning.grade(module, body)['passed'] is True
    module.pop('assessment_independent')
    body.answers['q1'] = 1
    assert learning.grade(module, body)['passed'] is True  # Existing module policy is retained.


def test_catalog_includes_public_scenario_context_but_not_feedback(monkeypatch):
    course = json.loads(json.dumps(COURSE))
    metadata = {'scenario_type': 'message', 'scenario_text': 'Учебное сообщение',
        'learning_goal': 'Проверка канала', 'difficulty': 'basic', 'source_url': 'https://example.org/',
        'content_version': 'v1'}
    course['modules'][0]['assessment_independent'] = True
    course['modules'][0]['cards'][0].update(**metadata, safe_action='Проверьте канал', danger_sign='Просят код')
    monkeypatch.setattr(learning, 'load_course', lambda: course)
    module = learning.catalog()['modules'][0]
    assert module['assessment_independent'] is True
    card = module['cards'][0]
    assert all(card[key] == value for key, value in metadata.items())
    assert not {'correct', 'explanation', 'safe_action', 'danger_sign'} & card.keys()


@pytest.mark.parametrize('course_version', [None, 'test-v1'])
def test_completion_replay_precedes_catalog_load(monkeypatch, course_version):
    # Exercise the actual mutate replay branch without an alternative database.
    import hashlib
    body = learning.CompletionRequest(module_id='safe', format='quiz', answers={'q1': 0},
                                      idempotency_key='historical', course_version=course_version)
    fingerprint = hashlib.sha256(json.dumps({'operation': 'completion',
        'payload': body.model_dump(exclude={'idempotency_key'}, exclude_none=True)},
        sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    historical = {'progress': {'xp': 60}, 'result': {'passed': True}}
    replay = SimpleNamespace(fingerprint=fingerprint, response=historical)
    class ReplaySession:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def begin(self):
            return nullcontext()
        def execute(self, *args):
            pass
        def scalar(self, *args):
            return replay
    monkeypatch.setattr(learning, 'get_engine', lambda: None)
    monkeypatch.setattr(learning, 'Session', lambda engine: ReplaySession())
    def unavailable_course():
        pytest.fail('Historical replay must not load the current course')
    monkeypatch.setattr(learning, 'load_course', unavailable_course)
    assert learning.complete(body, 'sub_12345678') == historical
    # Version is part of the fingerprint when supplied, even for historical keys.
    conflict = body.model_copy(update={'course_version': 'different-version'})
    with pytest.raises(Exception) as error:
        learning.complete(conflict, 'sub_12345678')
    assert error.value.status_code == 409


def test_calendar_gap_keeps_xp_and_one_completion_per_day():
    state = learning.empty_state()
    day = date(2026, 10, 1)
    learning.apply_completion(state, 'safe', 'quiz', day)
    learning.apply_completion(state, 'safe', 'quiz', day)
    assert state['xp'] == 60 and state['streak_days'] == 1
    learning.apply_completion(state, 'safe', 'article', day)
    assert state['xp'] == 70 and state['streak_days'] == 1
    learning.apply_completion(state, 'safe', 'quiz', day+timedelta(days=1))
    assert state['streak_days'] == 2
    assert learning.progress(state, day+timedelta(days=3))['streak_days'] == 0
    learning.apply_completion(state, 'safe', 'quiz', day+timedelta(days=3))
    assert state['streak_days'] == 1 and state['xp'] == 90


def test_daily_base_cap_rewards_once_and_rank_boundaries():
    state = learning.empty_state()
    day = date(2026, 10, 1)
    for i in range(20):
        learning.apply_completion(state, f'm{i}', 'quiz', day)
    assert state['daily']['base_xp'] == 100 and state['xp'] == 1100
    for offset in range(1, 30):
        learning.apply_completion(state, 'm0', 'quiz', day+timedelta(days=offset))
    assert state['unlocked_rewards'] == [3, 7, 14, 30]
    total = state['xp']
    learning.apply_completion(state, 'm0', 'quiz', day+timedelta(days=29))
    assert state['xp'] == total
    learning.apply_completion(state, 'm0', 'quiz', day+timedelta(days=40))
    for offset in (41, 42):
        learning.apply_completion(state, 'm0', 'quiz', day+timedelta(days=offset))
    assert state['xp'] == total+30  # no duplicate 3-day reward after a gap
    assert learning.rank_at(99)[0]['id'] == 'new'
    assert learning.rank_at(100)[0]['id'] == 'confident'
    assert learning.rank_at(1200)[1] is None


def test_category_calendar_month_is_earned_only_by_successful_thirty_day_streak():
    state = learning.empty_state()
    day = date(2026, 10, 1)
    for offset in range(30):
        learning.apply_completion(state, 'safe', 'quiz', day+timedelta(days=offset))
    state['category_entitlements']['2026-10'] = 'groceries'
    learning.apply_completion(state, 'safe', 'quiz', date(2026, 10, 31))
    assert state['category_entitlements'] == {'2026-10': 'groceries'}
    learning.apply_completion(state, 'safe', 'quiz', date(2026, 11, 1))
    assert state['category_entitlements'] == {'2026-10': 'groceries', '2026-11': None}
    shown = learning.progress(state, date(2026, 11, 1))
    assert shown['reward_period'] == '2026-11'
    assert shown['rewards'][-1]['selected_category'] is None
    learning.apply_completion(state, 'safe', 'quiz', date(2026, 12, 1))
    assert state['streak_days'] == 1 and '2026-12' not in state['category_entitlements']


def test_legacy_category_choice_is_retained_without_schema_migration():
    state = learning.empty_state()
    state.pop('category_entitlements')
    state.update(last_completed_date='2026-10-30', streak_days=30,
                 unlocked_rewards=[3, 7, 14, 30], selected_category='health')
    assert learning.progress(state, date(2026, 10, 30))['rewards'][-1]['selected_category'] == 'health'
    learning.apply_completion(state, 'safe', 'quiz', date(2026, 10, 31))
    assert state['category_entitlements'] == {'2026-10': 'health'}
    # Omitted optional period preserves fingerprints for historical claim replay.
    body = learning.RewardClaim(category='health', idempotency_key='old-key')
    assert body.model_dump(exclude={'idempotency_key'}, exclude_none=True) == {'category': 'health'}


@pytest.fixture
def db(monkeypatch):
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('TEST_DATABASE_URL required for actual PostgreSQL learning tests')
    assert make_url(url).database.startswith('antidrop_test')
    monkeypatch.setenv('DATABASE_URL', url)
    subjects = ['sub_'+uuid4().hex for _ in range(2)]
    tokens = [secrets.token_hex(32) for _ in subjects]
    monkeypatch.setenv('SANDBOX_TOKENS', json.dumps(dict(zip(tokens, subjects))))
    command.upgrade(Config('alembic.ini'), 'head')
    clock = [datetime(2026, 10, 1, 20, 59, tzinfo=timezone.utc)]
    monkeypatch.setattr(learning, 'now_utc', lambda: clock[0])
    client = TestClient(app, raise_server_exceptions=False)
    headers = [{'Authorization': 'Bearer '+token} for token in tokens]
    yield client, subjects, headers, clock
    monkeypatch.setenv('DATABASE_URL', url)
    with Session(get_engine()) as session, session.begin():
        session.execute(delete(LearningReplay).where(LearningReplay.subject_ref.in_(subjects)))
        session.execute(delete(LearningProfile).where(LearningProfile.subject_ref.in_(subjects)))


def complete(db, key='completion', index=0, answers=None, format='quiz'):
    return db[0].post('/api/v1/learning/completions', headers=db[2][index], json={
        'module_id': 'safe', 'format': format, 'answers': {'q1': 0} if answers is None else answers,
        'idempotency_key': key})


def test_pg_moscow_midnight_replay_and_isolation(db):
    client, subjects, headers, clock = db
    first = complete(db)
    assert first.status_code == 200, first.text
    assert first.json()['progress']['last_completed_date'] == '2026-10-01'
    clock[0] += timedelta(minutes=2)  # UTC21:01 = next Moscow date
    assert complete(db).json() == first.json()  # stable historical replay
    second = complete(db, key='next-day').json()
    assert second['progress']['streak_days'] == 2 and second['progress']['xp'] == 70
    assert complete(db, answers={'q1': 1}).status_code == 409
    assert client.get('/api/v1/learning/progress', headers=headers[1]).json()['xp'] == 0
    assert complete(db, index=1).json()['progress']['xp'] == 60
    assert client.get('/api/v1/learning/progress').status_code == 401
    failed = complete(db, key='failed', answers={'q1': 1}).json()
    assert failed['result']['passed'] is False and failed['progress']['xp'] == 70


def test_pg_completion_replay_survives_catalog_change_and_removal(db, monkeypatch):
    client, _, headers, _ = db
    payload = {'module_id': 'safe', 'format': 'quiz', 'answers': {'q1': 0},
               'course_version': COURSE['version'], 'idempotency_key': 'versioned'}
    first = client.post('/api/v1/learning/completions', headers=headers[0], json=payload)
    assert first.status_code == 200
    changed = json.loads(json.dumps(COURSE))
    changed['version'] = 'test-v2'
    changed['modules'][0]['quiz'][0]['id'] = 'replacement'
    monkeypatch.setattr(learning, 'load_course', lambda: changed)
    assert client.post('/api/v1/learning/completions', headers=headers[0], json=payload).json() == first.json()
    stale = client.post('/api/v1/learning/completions', headers=headers[0],
                        json={**payload, 'idempotency_key': 'new-stale'})
    assert stale.status_code == 409
    changed['modules'] = []
    replay = client.post('/api/v1/learning/completions', headers=headers[0], json=payload)
    assert replay.status_code == 200 and replay.json() == first.json()
    assert client.get('/api/v1/learning/progress', headers=headers[0]).json()['xp'] == 60


def test_pg_concurrent_completions_award_once(db):
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(lambda i: complete(db, key=f'concurrent-{i}'), range(16)))
    assert {r.status_code for r in responses} == {200}
    assert {r.json()['progress']['xp'] for r in responses} == {60}
    assert db[0].get('/api/v1/learning/progress', headers=db[2][0]).json()['streak_days'] == 1


def test_pg_concurrent_same_key_has_one_stable_response(db):
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(lambda _: complete(db, key='same-key'), range(16)))
    assert {r.status_code for r in responses} == {200}
    assert all(r.json() == responses[0].json() for r in responses)
    with Session(get_engine()) as session:
        records = list(session.scalars(select(LearningReplay).where(LearningReplay.subject_ref == db[1][0])))
        assert len(records) == 1


def test_pg_atomic_failure_and_outage(db, monkeypatch):
    def fail(*_):
        raise SQLAlchemyError('private injected audit failure')
    event.listen(LearningReplay, 'before_insert', fail)
    try:
        response = complete(db)
    finally:
        event.remove(LearningReplay, 'before_insert', fail)
    assert response.status_code == 503 and 'private' not in response.text
    assert db[0].get('/api/v1/learning/progress', headers=db[2][0]).json()['xp'] == 0
    assert complete(db).status_code == 200
    monkeypatch.setenv('DATABASE_URL', 'postgresql+psycopg://unavailable@127.0.0.1:1/unavailable')
    assert complete(db, key='outage').status_code == 503


def test_pg_reward_entitlement_claim_and_replay(db):
    client, subjects, headers, clock = db
    claim = lambda category='groceries', key='claim': client.post('/api/v1/learning/rewards/30/claim',
        headers=headers[0], json={'category': category, 'idempotency_key': key})
    assert claim().status_code == 409
    for i in range(30):
        clock[0] = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)+timedelta(days=i)
        assert complete(db, key=f'day-{i}').status_code == 200
    assert complete(db, key='day-29').json()['progress']['xp'] == 900
    first = claim()
    assert first.status_code == 200, first.text
    assert claim().json() == first.json()
    assert first.json()['progress']['rewards'][-1]['selected_category'] == 'groceries'
    assert claim('transport', 'other').status_code == 409
    assert client.post('/api/v1/learning/rewards/30/claim', headers=headers[1],
                       json={'category': 'groceries', 'idempotency_key': 'claim'}).status_code == 409


def test_pg_monthly_category_moscow_boundary_replay_and_historical_claim(db):
    client, subjects, headers, clock = db
    state = learning.empty_state()
    state.update(last_completed_date='2026-10-30', streak_days=30, xp=900,
                 completed_modules=['safe'], unlocked_rewards=[3, 7, 14, 30],
                 category_entitlements={'2026-10': None})
    with Session(get_engine()) as session, session.begin():
        session.add(LearningProfile(subject_ref=subjects[0], state=state))
    claim = lambda category, key, **extra: client.post('/api/v1/learning/rewards/30/claim',
        headers=headers[0], json={'category': category, 'idempotency_key': key, **extra})
    clock[0] = datetime(2026, 10, 31, 20, 59, tzinfo=timezone.utc)
    october = complete(db, key='october').json()
    assert october['progress']['reward_period'] == '2026-10'
    clock[0] += timedelta(minutes=2)  # next Moscow month; still October in UTC
    november = complete(db, key='november').json()
    assert november['progress']['reward_period'] == '2026-11'
    assert november['progress']['xp'] == 920  # milestone XP does not repeat
    first = claim('transport', 'nov-claim')
    assert first.status_code == 200
    assert first.json()['progress']['rewards'][-1]['selected_category'] == 'transport'
    assert claim('transport', 'nov-claim').json() == first.json()
    assert claim('health', 'nov-change').status_code == 409
    historical = claim('groceries', 'oct-claim', period='2026-10')
    assert historical.status_code == 200
    assert historical.json()['progress']['category_entitlements'] == [
        {'period': '2026-10', 'selected_category': 'groceries'},
        {'period': '2026-11', 'selected_category': 'transport'}]
    assert historical.json()['progress']['rewards'][-1]['selected_category'] == 'transport'
    assert claim('health', 'future-claim', period='2026-12').status_code == 409
    clock[0] = datetime(2026, 12, 1, 12, tzinfo=timezone.utc)
    after_gap = complete(db, key='after-gap').json()['progress']
    assert after_gap['streak_days'] == 1 and after_gap['reward_period'] == '2026-11'
    assert claim('health', 'gap-claim', period='2026-12').status_code == 409
    # A historical idempotency replay stays exactly the same after time advances.
    assert claim('transport', 'nov-claim').json() == first.json()


def test_pg_persistence_from_fresh_process(db):
    assert complete(db).status_code == 200
    code = """import os,json
from fastapi.testclient import TestClient
from main import app
r=TestClient(app).get('/api/v1/learning/progress',headers=json.loads(os.environ['AUDIT_LEARNING_HEADERS']))
assert r.status_code==200,r.text
assert r.json()['xp']==60
"""
    result = subprocess.run([sys.executable, '-c', code], env={**os.environ,
        'AUDIT_LEARNING_HEADERS': json.dumps(db[2][0])}, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
