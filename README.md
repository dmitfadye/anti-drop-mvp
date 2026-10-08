# Анти-Дроп: Защита и Адаптация
### Сервис финансовой безопасности для нерезидентов | Финтех-хакатон MVP

**Проблема:** иностранцы — частая мишень вербовщиков в «дропы». Человек принимает «транзит», а дальше возможны ограничение операций по 115-ФЗ и проверка по ст. 187 УК РФ — часто он даже не понимает, что оказался в чужой схеме.

**Решение:** онбординг с обучением + объяснимый мониторинг + экстренный алерт «Стоп-Дроп» на родном языке + учебный тренажёр смены номера.

**Стек:** FastAPI + Pydantic v2 (бэкенд, валидация, локальный Swagger) • TailwindCSS локальной сборки (без CDN) • stdlib-ядро детектора без ML-зависимостей.

> 🧪 **Демо-режим.** Это учебный демонстратор на синтетике: поддержка не вызывается, деньги не двигаются и не начисляются, SMS не отправляются. Все имитации явно помечены в UI и API (`demo: true`).

## Быстрый старт

```bash
cd anti-drop-mvp
uv sync  # или: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

.venv/bin/uvicorn main:app --reload
# дашборд → http://localhost:8000 (работает без интернета)
# Swagger  → http://localhost:8000/docs (локальные ассеты)

# тесты (ядро + API + регрессия аудита, 41 шт.):
.venv/bin/python -m unittest discover -s tests -v

# CLI-демо детектора:
.venv/bin/python src/demo.py

# Пересобрать CSS после правок index.html (нужен npm-пакет @tailwindcss/cli):
printf '@import "tailwindcss";\n' > /tmp/tw-input.css && ./node_modules/.bin/tailwindcss -i /tmp/tw-input.css -o static/tailwind.css --minify
```

## API

| Метод | Путь | Что делает |
|---|---|---|
| `GET` | `/` | Дашборд (локальный Tailwind, без внешних запросов) |
| `GET` | `/docs` | Swagger UI из локальных файлов |
| `GET` | `/api/health` | Статус + `rules_version` + `server_time_utc` + `demo_mode` |
| `GET` | `/api/langs` | 7 языков алертов |
| `GET` | `/api/content` | Сторис + квиз **без** правильных ответов (проверка на сервере) |
| `POST` | `/api/analyze` | `{transactions[], lang, subject_id?, analysis_at?}` → `{score, level, reasons[], metrics, alert?, rules_version}`. Смешение `user_id`, дубли `id`, мусор во времени/суммах → `422` |
| `POST` | `/api/quiz` | `{answers[]}` → `{score, passed, cashback, reward_status: "simulated"}` (выплат нет) |
| `POST` | `/api/sim` | Учебный тренажёр смены номера (SMS нет) → запрет или кулдаун |
| `POST` | `/api/cases` | Учебный кейс обращения: устойчивый `case_id`, повтор по `idempotency_key` не плодит дубликаты |
| `GET` | `/api/cases/{id}` | Статус кейса (хранилище — память процесса) |

Контракт анализа: **один запрос — один клиент**. Несколько `user_id` без `subject_id` отклоняются. Время: ISO, наивные метки считаются московскими, всё приводится к UTC; операции позже `analysis_at` исключаются (метрика `excluded_future_count`), нулевые суммы не считаются переводами.

## Структура

```
main.py            FastAPI (uvicorn main:app); request-id, локальный Swagger, без CORS-*
models.py          Pydantic-схемы: datetime-TZ, один субъект, уникальные id, лимиты строк
static/index.html  Фронт: esc()-рендер, обработка ошибок/загрузки, aria-live, учебные кейсы
static/tailwind.css Локальная сборка Tailwind v4 (пересобрать после правок HTML)
static/swagger/    Локальный Swagger UI (без CDN)
src/policy.py      Версионированные пороги правил (RULES_VERSION=2026-10-08.p1)
src/detector.py    Эвристики: транзит, веер, обнал, ночь, SIM+всплеск; скоринг 0–100
src/alerts.py      «Стоп-Дроп» на 7 языках, нейтральная юридическая лексика
src/quiz.py        3 микро-сторис + квиз (учебный приз, выплат нет)
src/sim_security.py Каноническое сравнение номеров + 24ч кулдаун (тренажёр)
src/cases.py       Sandbox-кейсы: детерминированный case_id + идемпотентность
app_stdlib.py      LEGACY фолбэк без зависимостей (только диагностика ядра, не для демо)
data/              2 CSV-сценария: норма vs дроп-атака
tests/             test_detector.py + test_api.py + test_audit.py (регрессия T02–T22)
requirements-lock.txt  Точный пин 56 пакетов (uv pip freeze)
```

## Честные границы (limitations для слайда жюри)

- Демо показывает **распознавание эпизода после вывода**, а не предотвращение первого перевода (5 входящих без вывода = YELLOW без алерта).
- Пороги правил не калиброваны на банковской разметке; 85 баллов — не «вероятность 85%».
- Переводы шаблонов не проверены носителями; для пилота нужен один приоритетный язык + review.
- Кейсы/кулдауны живут в памяти процесса; SMS, выплаты и ограничения операций отсутствуют.
- Для пилота с реальными данными нужны: банковский gateway/identity, PostgreSQL + audit, approved юридические тексты, data/security-согласования.

## Демо-сценарий для жюри (3 минуты)

1. Дашборд → **«Симулировать атаку вербовщика»** → RED-скоринг + алерт на узбекском/таджикском.
2. **«Создать учебное обращение»** → устойчивый `CASE-XXXXXXXX`, повтор не плодит дубликаты.
3. Открыть `/docs` → показать контракт API (работает офлайн).
4. Квиз → учебный приз (деньги не начисляются).
5. Тренажёр номера: без галочки OTP — запрет; один номер в разных форматах («+7 916…» vs «+7916…») — тоже запрет.


## P0 risk quality and reproducible evaluation

The isolated `anti_drop_ml` package adds strict RiskSnapshotV1/RiskDecisionV1 contracts, a thin adapter to existing rules, Wilson 95% intervals, threshold PR curves, legitimate-negative reporting, closed PII-rejecting event schemas and an approximate per-arm A/B power helper. Existing demo endpoints remain compatible. New endpoint: `POST /api/v1/risk/evaluate`; naive timestamps, duplicate IDs, future events, zero transfers and mixed subjects return 422. Score is not probability.

```sh
python -m anti_drop_ml.make_labeling_template --output-dir fixtures/episodes
python -m anti_drop_ml.evaluation.runner --dataset fixtures/episodes/labeled_episodes.jsonl --output-dir reports/evaluation --positive-level RED --rule-version 2026-10-08.p1
python -m unittest discover -s tests -v
```

Add `--positive-threshold 60` for a different decision threshold. All 21 provided labeled episodes are synthetic placeholders, development-only: they measure the pipeline, not banking accuracy. An intentional family-collection/rent false positive demonstrates the importance of legitimate negatives. Independent human-reviewed holdout, legal/native-language review and a bank data owner remain necessary.

See [P0 architecture and commands](docs/ml_p0_quality_layer.md), [labeling workflow](docs/labeling_guideline.md), [limitations](docs/limitations.md), [actual example report](reports/evaluation/report.md), and [legitimate-negative report](reports/evaluation/legitimate_negatives_report.md). Versioned JSON Schemas are in `docs/schemas/`.
