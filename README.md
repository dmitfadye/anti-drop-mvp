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

---

## P1 — коммуникационный слой

P0 сделал детектор честным и измеримым. P1 добавляет то, что обычно спрашивают,
а в отчёт не кладут: легитимные негативы, отчёт по правильности и темам,
локализацию, экран оператора, инструментацию эксперимента, честный финмодель и
план остановки пилота.

**Никакого банковского действия не выполняется: перевод не блокируется, деньги не
замораживаются, OTP не присылается, поддержка не создаётся.**

### Быстрый запуск с честными флагами

```bash
python -m scripts.generate_synthetic_fixtures --output-dir fixtures/episodes
python -m anti_drop_ml.evaluation.runner \
  --dataset fixtures/episodes/all_episodes_p1.jsonl --output-dir reports/evaluation \
  --cost-false-alert 650 --cost-missed-risk 45000 --prevalence 0.002
python -m scripts.run_financial_model --config configs/financial_assumptions.json --output-dir reports/finance
python -m scripts.export_blinded_scoring --experiment-id exp-warning-language-2026.10
python -m scripts.validate_localization --require-locale ru-RU --require-locale uz-UZ
python -m scripts.validate_stop_criteria --config configs/pilot_stop_criteria.json
python -m unittest discover -s tests -v
uvicorn main:app --host 127.0.0.1 --port 8000
```

`make help` — те же шаги целями. Сборка CI: `make ci`, Dockerfile: `make docker-build`,
экран оператора: `make operator`.

### Флаги (безопасное состояние по умолчанию)

| Переменная | По умолчанию | Значение |
|---|---|---|
| `ANTI_DROP_DEMO_MODE` | `true` | мастер-выключатель всех sandbox-поверхностей |
| `ANTI_DROP_OPERATOR_UI_ENABLED` | `false` | экран оператора (только с localhost) |
| `ANTI_DROP_OPERATOR_EXPORT_ENABLED` | `false` | псевдонимный экспорт JSON/CSV |
| `ANTI_DROP_EXPERIMENT_ENABLED` | `false` | детерминированное разведение |
| `ANTI_DROP_EXPERIMENT_ALLOW_DRAFT_TREATMENT` | `false` | демонстрация чернового перевода |
| `ANTI_DROP_ADVISORY_ENABLED` | `false` | pre-transfer advisory (только совет, не блокировка) |
| `ANTI_DROP_TARGET_LOCALE` | `uz-UZ` | целевой язык эксперимента |

### Что самое важное про чтение

| Артефакт | Вопрос |
|---|---|
| `reports/evaluation/report.md` | что делает детектор и где он ошибается |
| `reports/evaluation/warnings.md` | что нельзя заявлять |
| `reports/evaluation/legitimate_negative_report.md` | не обвиняет ли честных клиентов |
| `reports/evaluation/rule_ablation.csv` | какое правило даёт эффект |
| `reports/finance/financial_scenarios.csv` | экономика; база близка к нулю |
| `reports/experiment/experiment_plan.md` | план эксперимента; данных НЕТ |
| `configs/pilot_stop_criteria.json` | `ready_to_start: false` — пилот не разрешён |

### Обязательное ограничение

Один целевой код: FastAPI (`uvicorn main:app`). `app_stdlib.py` — legacy-диагностика
из P0, в deploy-путь не входит. Без Kafka, Redis, ClickHouse, Kubernetes,
микросервисов, LLM/RAG, ML-обучения, реальных ПДн и реальных сервисов.

Полная карта P1: `docs/p1_layer.md`. Ограничения: `docs/limitations.md`.
Доказательства и их статус: `docs/evidence_ledger.md`, `docs/hypothesis_tracker.md`.
Каталог легитимных негативов: `docs/legitimate_negative_catalog.md`.
Локализация: `docs/localization_workflow.md`, `docs/translation_checklist.md`,
`docs/legal_text_review_checklist.md`.
Экран оператора: `docs/operator_sandbox_guide.md`, `docs/operator_status_machine.md`.
Эксперимент: `docs/experiment_design.md`, `docs/blinded_scoring_rubric.md`.
Экономика: `docs/financial_model_methodology.md`.
Пилот: `docs/pilot_protocol.md`, `docs/rollback_plan.md`,
`docs/security_privacy_gate_checklist.md`, `configs/pilot_stop_criteria.json`.
Воспроизводимость: `docs/reproducibility.md`, `docs/ci_guide.md`.
Доступность: `docs/accessibility_checklist.md`.
Discovery: `docs/discovery_interview_guide.md`, `docs/jtbd_canvas.md`,
`docs/alternatives_map.md`, `research/`.
