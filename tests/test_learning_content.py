"""Validate the shipped UTF-8 course rather than an injected test catalog."""
import json
from pathlib import Path
import re

import pytest
from fastapi import HTTPException

from src import learning

COURSE_PATH = Path(__file__).resolve().parents[1] / 'data' / 'learning' / 'course.json'
MOJIBAKE = re.compile(r'(?:Р[\u0080-\u00bfЀ-џ]|С[Ѐ-џ]){2,}|[ÃÂÐÑ][\u0080-\u00bf]|â€|ðŸ')


def course():
    return json.loads(COURSE_PATH.read_text(encoding='utf-8'))


def text_fields(value, path='course'):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from text_fields(child, f'{path}.{key}')
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from text_fields(child, f'{path}[{index}]')
    elif isinstance(value, str):
        yield path, value


def test_actual_course_text_has_no_encoding_damage():
    for path, text in text_fields(course()):
        assert not re.search(r'\?{2,}', text), f'Lost Unicode characters at {path}'
        assert '\ufffd' not in text, f'Unicode replacement character at {path}'
        assert not MOJIBAKE.search(text), f'Possible mojibake at {path}'


def test_actual_course_question_identity_and_answer_ranges():
    catalog = course()
    modules = catalog['modules']
    assert len({module['id'] for module in modules}) == len(modules)
    for module in modules:
        questions = module['cards'] + module['quiz']
        assert len({question['id'] for question in questions}) == len(questions), module['id']
        for question in questions:
            assert len(question['options']) >= 2, question['id']
            assert type(question['correct']) is int, question['id']
            assert 0 <= question['correct'] < len(question['options']), question['id']


@pytest.mark.parametrize('field,value', [
    ('prompt', 'Что делать ???'),
    ('options', ['Правильный ответ', 'Повреждённый ?? ответ']),
    ('explanation', 'Повреждённый \ufffd текст'),
    ('scenario_text', 'Пример ??? звонка'),
    ('safe_action', 'Не раскрывать \ufffd'),
])
def test_load_course_fails_closed_on_damaged_display_text(tmp_path, monkeypatch, field, value):
    path = tmp_path / 'course.json'
    path.write_text(json.dumps({'modules': [{'cards': [{field: value}]}]}, ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(learning, 'COURSE_PATH', path)
    with pytest.raises(HTTPException) as error:
        learning.load_course()
    assert error.value.status_code == 503
    assert error.value.detail == 'Учебные материалы временно недоступны'
    if isinstance(value, str):
        assert value not in error.value.detail


def test_load_course_accepts_cyrillic_and_single_question_marks(tmp_path, monkeypatch):
    payload = {'title': 'Как проверить звонок?', 'article': ['Сделайте паузу.'],
        'modules': [{'cards': [{'prompt': 'Вам звонят?', 'options': ['Проверить контакт', 'Довериться'],
            'source_url': 'https://example.org/search??query=1', 'explanation': 'Проверьте информацию сами.'}]}]}
    path = tmp_path / 'course.json'
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(learning, 'COURSE_PATH', path)
    assert learning.load_course() == payload


@pytest.mark.parametrize('question_id,correct', [('phone_c4_file', 1), ('phone_c5_uncertainty', 2)])
def test_actual_phone_cards_have_readable_russian_feedback(question_id, correct):
    catalog = course()
    module = next(module for module in catalog['modules'] if module['id'] == 'm8_phone_fraud')
    card = next(question for question in module['cards'] if question['id'] == question_id)
    assert catalog['version'] == '2026-11-01.v4'
    assert module['content_version'] == '2026-11-01.phone.v3'
    assert card['content_version'] == module['content_version']
    assert card['correct'] == correct
    for field in ('prompt', 'explanation', 'scenario_text', 'learning_goal', 'danger_sign', 'safe_action'):
        assert re.search(r'[А-Яа-яЁё]{3,}', card[field]), f'{question_id}.{field}'
    for option in card['options']:
        assert re.search(r'[А-Яа-яЁё]{3,}', option), question_id
    assert card['source_url'] == 'https://www.cbr.ru/psystem/field_offices/secur/'
    if question_id == 'phone_c4_file':
        assert 'программ' in card['scenario_text']
        assert 'удалённ' in card['scenario_text']
        assert 'Отказаться' in card['options'][correct]
    else:
        assert 'знакомый номер банка' in card['scenario_text']
        assert 'по имени' in card['scenario_text']
        assert 'не подтверждают личность' in card['explanation']
        assert 'Данных недостаточно' in card['options'][correct]
