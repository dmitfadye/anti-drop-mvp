# Анти-Дроп: Защита и Адаптация
### Сервис финансовой безопасности для нерезидентов | Финтех-хакатон MVP

**Проблема:** иностранцы — главная мишень вербовщиков в «дропы». Человек принимает «транзит», а получает блокировку по 115-ФЗ и уголовную ответственность (ст. 187 УК РФ), часто не понимая, что нарушил закон.

**Решение:** онбординг с обучением + поведенческий мониторинг + экстренный алерт «Стоп-Дроп» на родном языке + безопасная смена номера.

**Стек:** FastAPI + Pydantic v2 (бэкенд, валидация, Swagger) • TailwindCSS (фронт) • stdlib-ядро детектора без ML-зависимостей.

## Быстрый старт

```bash
cd anti-drop-mvp
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

.venv/bin/uvicorn main:app --reload
# дашборд → http://localhost:8000
# Swagger  → http://localhost:8000/docs

# тесты (ядро + API):
.venv/bin/python -m unittest discover -s tests -v

# CLI-демо детектора и stdlib-фолбэк без зависимостей:
.venv/bin/python src/demo.py
python3 app_stdlib.py  # тот же MVP на чистом http.server
```

## API

| Метод | Путь | Что делает |
|---|---|---|
| `GET` | `/` | Дашборд (Tailwind) |
| `GET` | `/docs` | Swagger UI — удобно показать жюри контракт |
| `GET` | `/api/health`, `/api/langs` | Статус, 7 языков алертов |
| `GET` | `/api/content` | Сторис + квиз **без** правильных ответов (проверка на сервере) |
| `POST` | `/api/analyze` | `{transactions[], lang}` → `{score, level, reasons[], metrics, alert?}`; мусор отклоняется с `422` |
| `POST` | `/api/quiz` | `{answers[]}` → `{score, passed, cashback}` |
| `POST` | `/api/sim` | `{old_phone, new_phone, otp_ok_old, otp_ok_new}` → смена номера или запрет |

## Структура

```
main.py            FastAPI-приложение (uvicorn main:app)
models.py          Pydantic-схемы запросов/ответов
static/index.html  Фронт на TailwindCSS (CDN), fetch к /api/*
src/detector.py    Эвристики: транзит, веерные P2P, обнал, ночь, SIM+всплеск; скоринг 0–100
src/alerts.py      «Стоп-Дроп» на 7 языках: ru/en/uz/tg/ky/zh/ar
src/quiz.py        3 микро-сторис + квиз из 5 вопросов, кешбэк 100 ₽
src/sim_security.py OTP с обоих номеров + 24ч кулдаун (P2P до 5 000 ₽)
app_stdlib.py      Фолбэк-вариант без зависимостей (тот же функционал)
data/              2 CSV-сценария: норма vs дроп-атака
tests/             test_detector.py (ядро) + test_api.py (8 тестов FastAPI)
```

## Демо-сценарий для жюри (3 минуты)

1. Дашборд → **«Симулировать атаку вербовщика»** → RED-скоринг + алерт на узбекском/таджикском с объяснением 115-ФЗ.
2. Открыть `/docs` → показать контракт API (плюс для технической оценки).
3. Квиз → «кешбэк 100 ₽».
4. Смена номера: без галочки OTP — запрет, с галочками — кулдаун.
