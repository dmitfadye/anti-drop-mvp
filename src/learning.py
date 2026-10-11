"""Server-graded learning and synthetic rewards, with owned PostgreSQL state."""
import hashlib
import json
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, StrictInt
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from anti_drop_ml.contracts import ClosedModel
from src.database import get_engine
from src.learning_models import LearningProfile, LearningReplay
from src.sandbox import trusted_subject

router = APIRouter(prefix='/api/v1/learning', tags=['Synthetic financial education'])
COURSE_PATH = Path(__file__).resolve().parents[1] / 'data' / 'learning' / 'course.json'
MOSCOW = ZoneInfo('Europe/Moscow')
RANKS = [(0, 'new', 'Новый участник'), (100, 'confident', 'Уверенный пользователь'),
         (300, 'knowledgeable', 'Знаток денег'), (700, 'navigator', 'Финансовый навигатор'),
         (1200, 'master', 'Мастер безопасных переводов')]
REWARDS = [(3, 30), (7, 70), (14, 150), (30, 300)]
CATEGORIES = [{'id': key, 'title': title} for key, title in [
    ('groceries', 'Продукты'), ('transport', 'Транспорт'), ('communication', 'Связь'),
    ('education', 'Образование'), ('health', 'Здоровье')]]
Category = Literal['groceries', 'transport', 'communication', 'education', 'health']


def now_utc():
    """Single injectable server clock; clients cannot submit completion dates."""
    return datetime.now(timezone.utc)


def load_course():
    try:
        return json.loads(COURSE_PATH.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise HTTPException(503, 'Учебные материалы временно недоступны') from None


class CompletionRequest(ClosedModel):
    module_id: str = Field(min_length=1, max_length=80)
    format: Literal['quiz', 'lesson', 'article']
    answers: dict[str, StrictInt] = Field(max_length=100)
    idempotency_key: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9._:-]+$')


class RewardClaim(ClosedModel):
    category: Category
    idempotency_key: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9._:-]+$')


def empty_state():
    return {'xp': 0, 'last_completed_date': None, 'streak_days': 0,
            'completed_modules': [], 'daily': {}, 'unlocked_rewards': [], 'selected_category': None}


def rank_at(xp):
    rank = max((r for r in RANKS if r[0] <= xp), key=lambda r: r[0])
    next_rank = next((r for r in RANKS if r[0] > xp), None)
    def payload(r):
        return {'min_xp': r[0], 'id': r[1], 'title': r[2]} if r else None
    percent = min(100, int((xp-rank[0])*100/(next_rank[0]-rank[0]))) if next_rank else 100
    return payload(rank), payload(next_rank), percent


def progress(state, today):
    rank, next_rank, percent = rank_at(state['xp'])
    last = date.fromisoformat(state['last_completed_date']) if state['last_completed_date'] else None
    streak = state['streak_days'] if last and today-last <= timedelta(days=1) else 0
    return {'xp': state['xp'], 'rank': rank, 'next_rank': next_rank,
            'points_to_next': max(0, next_rank['min_xp']-state['xp']) if next_rank else 0,
            'rank_progress_percent': percent, 'streak_days': streak,
            'last_completed_date': state['last_completed_date'],
            'completed_modules': sorted(state['completed_modules']),
            'rewards': [{'days': days, 'title': f'{days} дней подряд: +{points} учебных баллов',
                         'points': points, 'unlocked': days in state['unlocked_rewards'],
                         'selected_category': state['selected_category'] if days == 30 else None}
                        for days, points in REWARDS],
            'percentile': None, 'rank_note': 'Рейтинг пока недоступен: нет сравнительной выборки.',
            'categories': CATEGORIES, 'demo': True,
            'reward_note': 'Учебные награды: деньги не начисляются. Категория выбирается один раз после 30 дней подряд.'}


def grade(module, body):
    questions = module['quiz'] if body.format == 'quiz' else module['cards'] + module['quiz'] if body.format == 'lesson' else module['cards'][:1]
    if not questions:
        raise HTTPException(503, 'Для выбранного формата отсутствует проверка знаний')
    if set(body.answers) != {q['id'] for q in questions}:
        raise HTTPException(422, 'Ответьте на все вопросы выбранного формата, без дополнительных ответов')
    feedback = []
    for q in questions:
        answer = body.answers[q['id']]
        if not 0 <= answer < len(q['options']):
            raise HTTPException(422, 'Недопустимый вариант ответа')
        feedback.append({'question_id': q['id'], 'correct': answer == q['correct'],
                         'explanation': q['explanation'], 'source_needed': q.get('source_needed', False)})
    score = sum(item['correct'] for item in feedback)
    return {'score': score, 'total': len(questions), 'passed': score*100 >= len(questions)*80,
            'feedback': feedback}


def apply_completion(state, module_id, format, today):
    """10 base XP per module/format/day, daily base cap 100; first module bonus 50.

    Passing any chosen format (including the article attention check) completes
    its module. This reflects user choice, rather than claiming a full exam pass.
    Streak rewards and the 30-day category entitlement are once per subject.
    """
    day = today.isoformat()
    # Only the current day is needed; replay records preserve historical responses.
    daily = state['daily'] if state['daily'].get('date') == day else {'date': day, 'keys': [], 'base_xp': 0}
    key = f'{module_id}:{format}'
    if key not in daily['keys']:
        state['xp'] += min(10, 100-daily['base_xp'])
        daily['base_xp'] = min(100, daily['base_xp']+10)
        daily['keys'].append(key)
    state['daily'] = daily
    if module_id not in state['completed_modules']:
        state['completed_modules'].append(module_id)
        state['xp'] += 50
    last = date.fromisoformat(state['last_completed_date']) if state['last_completed_date'] else None
    if last != today:
        state['streak_days'] = state['streak_days']+1 if last == today-timedelta(days=1) else 1
        state['last_completed_date'] = day
    for days, points in REWARDS:
        if state['streak_days'] >= days and days not in state['unlocked_rewards']:
            state['unlocked_rewards'].append(days)
            state['xp'] += points


def mutate(subject, operation, body, action):
    instant = now_utc()
    fingerprint = hashlib.sha256(json.dumps({'operation': operation, 'payload': body.model_dump(exclude={'idempotency_key'})}, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    digest = hashlib.sha256(body.idempotency_key.encode()).hexdigest()
    lock = int.from_bytes(hashlib.sha256(('learning|'+subject).encode()).digest()[:8], 'big', signed=True)
    with Session(get_engine()) as session, session.begin():
        session.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': lock})
        replay = session.scalar(select(LearningReplay).where(LearningReplay.subject_ref == subject, LearningReplay.key_digest == digest))
        if replay:
            if replay.fingerprint != fingerprint:
                raise HTTPException(409, 'Ключ повторного запроса уже использован с другими данными')
            return replay.response
        profile = session.get(LearningProfile, subject)
        state = json.loads(json.dumps(profile.state)) if profile else empty_state()
        response = action(state, instant.astimezone(MOSCOW).date())
        if profile:
            profile.state = state
        else:
            session.add(LearningProfile(subject_ref=subject, state=state))
        session.add(LearningReplay(subject_ref=subject, key_digest=digest, fingerprint=fingerprint,
                                   response=response, created_at=instant))
    return response


@router.get('/catalog')
def catalog():
    course = load_course()
    modules = []
    for module in course['modules']:
        public = {key: module[key] for key in ('id', 'title', 'summary', 'minutes', 'article')}
        for kind in ('cards', 'quiz'):
            public[kind] = [{**{key: q[key] for key in ('id', 'prompt', 'options')},
                             **({'source_needed': q['source_needed']} if 'source_needed' in q else {})}
                            for q in module[kind]]
        modules.append(public)
    return {'version': course['version'], 'modules': modules, 'demo': True,
            'disclaimer': course.get('disclaimer', 'Учебные награды, без начисления денег.'),
            'source': course.get('source', {})}


@router.get('/progress')
def get_progress(subject: str = Depends(trusted_subject)):
    with Session(get_engine()) as session:
        profile = session.get(LearningProfile, subject)
        return progress(profile.state if profile else empty_state(), now_utc().astimezone(MOSCOW).date())


@router.post('/completions')
def complete(body: CompletionRequest, subject: str = Depends(trusted_subject)):
    module = next((m for m in load_course()['modules'] if m['id'] == body.module_id), None)
    if module is None:
        raise HTTPException(404, 'Учебный модуль не найден')
    result = grade(module, body)
    def action(state, today):
        if result['passed']:
            apply_completion(state, body.module_id, body.format, today)
        return {'progress': progress(state, today), 'result': result}
    return mutate(subject, 'completion', body, action)


@router.post('/rewards/30/claim')
def claim(body: RewardClaim, subject: str = Depends(trusted_subject)):
    def action(state, today):
        if 30 not in state['unlocked_rewards']:
            raise HTTPException(409, 'Категория доступна после 30 дней занятий подряд')
        if state['selected_category'] and state['selected_category'] != body.category:
            raise HTTPException(409, 'Учебная категория уже выбрана')
        state['selected_category'] = body.category
        return {'progress': progress(state, today)}
    return mutate(subject, 'claim30', body, action)
