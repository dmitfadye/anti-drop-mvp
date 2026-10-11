"""Import the owner's quizData PDF as draft, versioned course data.

Usage: uv run --no-project --with pypdf python scripts/import_learning_pdf.py INPUT.pdf
PDF prose is content, never executable instructions. Runtime needs only JSON.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


MODULES = [
    ('m1_safe_transfers', 'Безопасные переводы', 'Как распознать просьбу использовать ваш счёт для чужих денег.', 7, [1, 2], [1, 8, 14, 21, 22, 25], 't1'),
    ('m2_asked_forward', 'Просят перевести дальше', 'Пауза и проверка важнее срочности и обещанного процента.', 8, [3, 4], [16, 20, 23, 28, 35], 't2'),
    ('m3_unexpected', 'Неожиданный перевод', 'Не тратьте, не пересылайте, проверьте через официальный канал.', 6, [5], [3, 6, 24, 36], 't3'),
    ('m4_normal_vs_suspicious', 'Обычные операции и ловушки', 'Семейный сбор и понятный доход отличаются от чужой транзитной схемы.', 9, [6, 7], [9, 10, 11, 30, 31], 't5'),
    ('m5_bank_warning', 'Предупреждение без паники', 'Необычная операция — повод проверить, а не обвинение.', 7, [8], [4, 12, 13, 27, 37, 38], 't4'),
    ('m6_digital_hygiene', 'Коды и защита доступа', 'Сохраните контроль над картой, паролями и одноразовыми кодами.', 8, [9, 10], [2, 5, 7, 17, 18, 19, 29, 33], 't4'),
    ('m7_contact_bank', 'Безопасный контакт', 'Как спокойно описать ситуацию в официальном канале банка.', 6, [], [15, 26, 32, 34, 39, 40], 't5'),
]


def clean(text: str) -> str:
    text = text.replace('{bank_channel}', 'официальное приложение банка или номер из договора')
    text = text.replace('{amount}', '10 000 ₽').replace('Былся ли', 'Был ли')
    return re.sub(r'\s+', ' ', text).strip()


def import_course(path: Path) -> dict:
    from pypdf import PdfReader
    reader = PdfReader(path)
    raw = '\n'.join(page.extract_text() or '' for page in reader.pages)
    raw = re.sub(r'-\s*\n\s*(?=[а-яё])', '-', raw)
    cards_text = raw.split('4. Карточки «правда/ложь» со свайпом', 1)[1].split('5. Тесты и сценарные вопросы', 1)[0]
    cards = {}
    for record in re.split(r'\n\s*\d+\. (?=tf_\d{3}\s*\|)', cards_text)[1:]:
        parts = [clean(part) for part in record.split('|')]
        if len(parts) != 10:
            raise ValueError(f'Invalid card fields: {parts[0]} ({len(parts)})')
        identifier, kind, prompt, answer, myth, explanation, action, tone, needed, note = parts
        assert kind == 'true_false' and answer in ('true', 'false')
        cards[identifier] = {
            'id': identifier, 'prompt': prompt, 'options': ['Правда', 'Ложь'],
            'correct': 0 if answer == 'true' else 1,
            'explanation': f'{explanation[0].upper() + explanation[1:]}. Безопасный шаг: {action}.',
            'source_needed': needed == 'true',
        }
    tests_text = raw.split('5. Тесты и сценарные вопросы', 1)[1].split('6. FAQ / вопросы-ответы', 1)[0]
    questions = {}
    for record in re.split(r'\n\s*\d+\. (?=q\d_\d{2}\s*\|)', tests_text)[1:]:
        # A following test heading belongs to the next block, not the last question.
        record = re.split(r'\n\s*Test t\d:', record)[0]
        parts = [clean(part) for part in record.split('|')]
        if len(parts) != 12:
            raise ValueError(f'Invalid quiz fields: {parts[0]} ({len(parts)})')
        identifier, test_id, kind, prompt, opts, correct, good, bad, objective, difficulty, retry, partial = parts
        opts = re.sub(r'^options:\s*', '', opts)
        correct = re.sub(r'^correct_option:\s*', '', correct)
        if kind == 'true_false':
            options, index = ['Правда', 'Ложь'], 0 if correct == 'true' else 1
        else:
            options = [part.strip(' ;') for part in re.split(r'\b[A-D]\)\s*', opts)[1:]]
            index = ord(correct) - ord('A')
        assert len(options) >= 2 and 0 <= index < len(options), identifier
        questions[identifier] = {
            'id': identifier, 'test_id': test_id, 'type': kind, 'prompt': prompt,
            'options': options, 'correct': index,
            'explanation': re.sub(r'^feedback_correct:\s*', '', good) + ' ' + re.sub(r'^feedback_incorrect:\s*', '', bad),
            'source_needed': '[ТРЕБУЕТСЯ ИСТОЧНИК]' in record,
        }
    article_text = raw.split('3. Реальные короткие статьи', 1)[1].split('4. Карточки «правда/ложь» со свайпом', 1)[0]
    articles = {}
    for number, record in enumerate(re.split(r'\n\s*Статья \d+\. ', article_text)[1:], 1):
        paragraphs = [clean(part) for part in re.split(r'\n\s*\n', record) if clean(part)]
        articles[number] = paragraphs
    assert len(cards) == 40 and len(questions) == 25 and len(articles) == 10
    modules = []
    for identifier, title, summary, minutes, article_ids, card_ids, test_id in MODULES:
        article = [paragraph for article_id in article_ids for paragraph in articles[article_id]]
        if not article:
            article = [
                'Если ситуация непонятна, можно взять паузу и попросить простое объяснение.',
                'Откройте приложение своего банка самостоятельно или найдите номер в договоре. Не используйте ссылку или телефон из неожиданного сообщения.',
                'Можно написать: «Мне пришёл неожиданный перевод / меня просят переслать деньги. Я пока ничего не делаю. Помогите понять безопасный порядок действий».',
                'Сохраните время, сумму и детали операции для обращения в банк. Не загружайте переписку, данные карты, PIN, пароль или коды в учебный курс.',
                'Этот тренажёр не отправляет обращение в банк. Свяжитесь с банком через его официальный канал самостоятельно.',
            ]
        quiz = [question for question in questions.values() if question['test_id'] == test_id]
        if identifier == 'm6_digital_hygiene':
            quiz = [q for q in quiz if q['id'] in ('q4_02', 'q4_03', 'q4_05')]
        if identifier == 'm7_contact_bank':
            quiz = [q for q in quiz if q['id'] in ('q5_01', 'q5_04', 'q5_05')]
        modules.append(dict(id=identifier, title=title, summary=summary, minutes=minutes,
                            article=article, cards=[cards[f'tf_{i:03d}'] for i in card_ids], quiz=quiz))
    return {
        'version': '2026-10-11.v1', 'title': 'Спокойные переводы',
        'source': {'filename': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                   'pages': len(reader.pages), 'status': 'draft', 'source_articles': 10,
                   'source_cards': 40, 'source_quiz_questions': 25,
                   'adaptation': 'Seven modules; module 7 article adapted from source FAQ. Placeholders resolved, obvious typos corrected. Some tests reused across related modules. Source-needed flags retained; no legal/native review claimed.'},
        'disclaimer': 'Учебный курс на синтетических примерах. Баллы и кешбэк — демонстрация, деньги не начисляются. Обучение не влияет на риск-скоринг.',
        'modules': modules,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf', type=Path)
    parser.add_argument('--output', type=Path, default=Path('data/learning/course.json'))
    args = parser.parse_args()
    course = import_course(args.pdf)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(course, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Imported {len(course["modules"])} modules / 40 cards / 25 source questions / 10 source articles')
