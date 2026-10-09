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

docker compose up

.venv/bin/uvicorn main:app --reload
# дашборд → http://localhost:8000 (работает без интернета)
# Swagger  → http://localhost:8000/docs (локальные ассеты)

# тесты (ядро + API + регрессия аудита + sandbox-кейсы, 128 шт.):
.venv/bin/python -m unittest discover -s tests -v

# ручной smoke перезапуска процесса (поднимает и убивает настоящий uvicorn):
.venv/bin/python scripts/restart_smoke.py

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
| `POST` | `/api/analyze` | `{transactions[], lang, subject_id?, analysis_at?}` → `{score, level, reasons[], reason_codes[], metrics, alert?, rules_version, evaluation_id}`. Смешение `user_id`, дубли `id`, мусор во времени/суммах → `422` |
| `POST` | `/api/quiz` | `{answers[]}` → `{score, passed, cashback, reward_status: "simulated"}` (выплат нет) |
| `POST` | `/api/sim` | Учебный тренажёр смены номера (SMS нет) → запрет или кулдаун |
| `POST` | `/api/cases`, `GET` `/api/cases/{id}` | **Отключены (410 `LEGACY_CASES_DISABLED`).** Хранили кейсы в памяти процесса и не знали про субъекта. Целевой путь — `/sandbox/cases` |

### Sandbox cases: подтверждённое обращение вместо имитации

Кнопка «Создать обращение» вызывает реальный endpoint, а не меняет текст на кнопке.
Кейс сохраняется в SQLite и переживает перезапуск сервера.

| Метод | Путь | Что делает |
|---|---|---|
| `POST` | `/sandbox/cases` | Создать кейс (201). Требует `X-Sandbox-Subject` и `Idempotency-Key` |
| `GET` | `/sandbox/cases` | Свои кейсы: `limit` (1–100), `offset` ≥ 0, `total_count`; сортировка `created_at DESC` |
| `GET` | `/sandbox/cases/{case_id}` | Свой кейс. Чужой кейс неразличим от отсутствующего (404) |

#### Переменные окружения

`.env`, а при его отсутствии — `.env.example` в корне репозитория подхватываются
автоматически (приоритет: окружение процесса > `.env` > `.env.example`).
Для Docker-PostgreSQL достаточно раскомментировать `PG_DSN` в `.env.example`.

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `PG_DSN` | — | DSN PostgreSQL (`postgresql://anti_drop:anti_drop@localhost:5433/anti_drop`). Если задан — пишем в PostgreSQL, иначе — в SQLite |
| `DATABASE_PATH` | `./data/anti_drop_mvp.db` | Путь к SQLite. Относительный разрешается от корня репозитория, а не от текущего каталога — иначе можно молча получить другую БД |
| `LOG_LEVEL` | `INFO` | Уровень логов |
| `SANDBOX_MODE` | `true` | `false` отключает case API (503 `SANDBOX_DISABLED`) |
| `APP_ENV` | `sandbox` | Метка окружения |
| `MAX_CLIENT_COMMENT_LENGTH` | `1000` | Лимит `client_comment` |

```bash
DATABASE_PATH=./data/anti_drop_mvp.db .venv/bin/uvicorn main:app --reload
```

#### Идемпотентность

Область действия ключа — **(субъект, `Idempotency-Key`)**, а не ключ глобально.
Глобальная уникальность позволяла бы одному субъекту занять ключ и заблокировать
им другого, а по коду ответа — узнать, что ключ уже кем-то использован.

| Субъект | Ключ | Тело | Результат |
|---|---|---|---|
| тот же | тот же | то же | `200`, тот же `case_id`, `Idempotency-Replayed: true` |
| тот же | тот же | другое | `422 IDEMPOTENCY_KEY_PAYLOAD_MISMATCH` |
| **другой** | **тот же** | любое | `201`, **свой независимый кейс** |

```bash
# alice создаёт (201)
curl -i -X POST http://127.0.0.1:8000/sandbox/cases \
  -H 'Content-Type: application/json' \
  -H 'X-Sandbox-Subject: alice' \
  -H 'Idempotency-Key: shared-key-1' \
  -d '{"evaluation_id":"eval-alice-1","selected_language":"ru","contact_reason":"suspicious_transfer_request"}'

# повтор alice с тем же ключом и тем же телом -> 200, тот же case_id, Replayed: true
# bob с тем же ключом и своим evaluation_id -> 201, СВОЙ case_id (не 422!)
# GET чужого кейса -> 404 CASE_NOT_FOUND (не 403, чтобы не выдавать существование)
```

#### Миграция БД

Схема создаётся и обновляется идемпотентно при старте (`schema_version` в таблице
`schema_meta`). Отдельного ручного шага не нужно: если в существующей БД остался
старый глобальный индекс `ux_sandbox_cases_idempotency_key`, он будет удалён
(`DROP INDEX`, данные не трогаются), а вместо него создан составной
`ux_sandbox_cases_subject_idempotency_key`. Таблица не пересоздаётся.

**Границы этой подсистемы.** `X-Sandbox-Subject` — намеренная sandbox-замена,
а **не** production auth. Субъект нельзя передать в теле запроса (попытка даёт
422 `UNTRUSTED_SUBJECT_FIELD` для полей `subject`, `subject_ref`, `user_id`,
`client_id`, `phone`, `msisdn`, `device_id`, `otp`, `passport`, `card`, `pan` —
регистр не важен): в реальном контуре он обязан приходить из банковского
gateway/SSO/mTLS. `client_comment` не сохраняется и не логируется —
он влияет только на `payload_hash`. Кейс не является обращением в поддержку банка.

### Формат ошибок

Все ошибки отдаются одним объектом, а не голым `detail`:

```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "Проверьте переданные данные.",
  "request_id": "req_1f2e...",
  "field": "selected_language",
  "details": [{"field": "selected_language", "message": "..."}]
}
```

`X-Request-ID` возвращается в заголовке ответа; если его не передали, сервер
генерирует `req_<uuid4hex>`. Заголовок проставляется **на всех** ответах,
включая 404, 405 и 500. Роутерные ошибки тоже в envelope: `404` → `NOT_FOUND`,
`405` → `METHOD_NOT_ALLOWED`.

Коды ошибок:

| Код | Когда |
|---|---|
| `VALIDATION_ERROR` | Общая валидация тела, query-параметров; лимит `client_comment` |
| `MISSING_IDEMPOTENCY_KEY` | Нет заголовка `Idempotency-Key` |
| `INVALID_IDEMPOTENCY_KEY` | Формат ключа: только `A-Za-z0-9._:-`, длина 1–128 |
| `IDEMPOTENCY_KEY_PAYLOAD_MISMATCH` | Тот же ключ у того же субъекта, но другое тело |
| `SUBJECT_REQUIRED` | Нет заголовка `X-Sandbox-Subject` (401) |
| `INVALID_SUBJECT_HEADER` | Недопустимое значение заголовка (401) |
| `UNTRUSTED_SUBJECT_FIELD` | Попытка передать `subject`/`user_id`/`phone`/`otp`/… в теле (422) |
| `UNSUPPORTED_LANGUAGE` | Языка нет в списке шаблонов (422) |
| `INVALID_CONTACT_REASON` | Причина обращения не из allowlist (422) |
| `INVALID_EVALUATION_ID` | `evaluation_id` пуст или из недопустимых символов (422) |
| `CASE_NOT_FOUND` | Кейс не найден **или принадлежит другому субъекту** (404) |
| `NOT_FOUND` / `METHOD_NOT_ALLOWED` | Роутерные 404 / 405 |
| `LEGACY_CASES_DISABLED` | Отключённые `/api/cases` (410) |
| `SANDBOX_DISABLED` | `SANDBOX_MODE=false` (503) |
| `STORAGE_UNAVAILABLE` | БД недоступна (503) |
| `INTERNAL_ERROR` | Непредвиденная ошибка; traceback клиенту не отдаётся (500) |

Ошибка БД никогда не превращается в фейковый успех: недоступное хранилище даёт
`503 STORAGE_UNAVAILABLE` без внутренних деталей и без `case_id`.

### Reason codes

`POST /api/analyze` возвращает `reason_codes` рядом с человеческими `reasons`.
Коды стабильны, не зависят от языка и не содержат ПДн; это отражение уже
существующих правил — score и level при их добавлении не изменились.

`MULTIPLE_SMALL_INBOUND`, `MULTIPLE_SMALL_INBOUND_SUSPICIOUS`,
`OUTBOUND_AFTER_INBOUND`, `HIGH_CASHOUT_RATIO`, `RAPID_OUTFANOUT`,
`NIGHT_ACTIVITY`, `SIM_CHANGED_RECENTLY`, `NEW_DEVICE`, `FUTURE_EVENT_EXCLUDED`,
`INVALID_TIMESTAMP_EXCLUDED`, `ZERO_AMOUNT_EXCLUDED`, `INSUFFICIENT_DATA`,
`NO_RISK_SIGNAL`.

Также в ответе: `evaluation_id` (ссылка для создания кейса) и
`score_interpretation: deterministic_rule_sum_not_probability`.

Контракт анализа: **один запрос — один клиент**. Несколько `user_id` без `subject_id` отклоняются. Время: ISO, наивные метки считаются московскими, всё приводится к UTC; операции позже `analysis_at` исключаются (метрика `excluded_future_count`), нулевые суммы не считаются переводами.

## Структура

```
main.py            FastAPI (uvicorn main:app); lifespan, request-id, envelope-ошибки, локальный Swagger, без CORS-*
models.py          Pydantic-схемы: datetime-TZ, один субъект, уникальные id, sandbox-кейсы, reason codes
static/index.html  Фронт: esc()/textContent-рендер, состояния загрузки/ошибки/replay, aria-live
static/tailwind.css Локальная сборка Tailwind v4 (пересобрать после правок HTML)
static/swagger/    Локальный Swagger UI (без CDN)
src/policy.py      Версионированные пороги правил (RULES_VERSION=2026-10-08.p1)
src/detector.py    Эвристики: транзит, веер, обнал, ночь, SIM+всплеск; скоринг 0–100
src/alerts.py      «Стоп-Дроп» на 7 языках, нейтральная юридическая лексика
src/quiz.py        3 микро-сторис + квиз (учебный приз, выплат нет)
src/sim_security.py Каноническое сравнение номеров + 24ч кулдаун (тренажёр)
src/config.py      Env-конфиг: DATABASE_PATH (resolved), LOG_LEVEL, лимиты, sandbox-тексты
src/db.py          SQLite: WAL, составной unique (subject, key), миграция индекса, schema_version
src/errors.py      Единый error envelope: error_code / message / request_id
src/identity.py    X-Sandbox-Subject (test-only) + регистронезависимый запрет identity-полей в теле
src/sandbox_cases.py Идемпотентность в scope субъекта: Idempotency-Key + payload_hash, replay 200
src/reason_codes.py Машиночитаемые коды причин риска (score не меняют)
scripts/restart_smoke.py Ручной smoke перезапуска процесса (демонстрация вживую)
tests/test_sandbox_cases.py Persistency, trusted subject, idempotency, envelope, OpenAPI, логи, concurrency (100)
app_stdlib.py      LEGACY фолбэк без зависимостей (только диагностика ядра, не для демо)
data/              2 CSV-сценария: норма vs дроп-атака
tests/             test_detector.py + test_api.py + test_audit.py (регрессия T02–T22)
requirements-lock.txt  Точный пин 56 пакетов (uv pip freeze)
```

## Честные границы (limitations для слайда жюри)

- Демо показывает **распознавание эпизода после вывода**, а не предотвращение первого перевода (5 входящих без вывода = YELLOW без алерта).
- Пороги правил не откалиброваны на банковской разметке; 85 баллов — не «вероятность 85%». Score — сумма правил с потолком 100.
- Точность детектора не подтверждена без независимой разметки и holdout. Синтетика — это фикстуры для демо, а не validation dataset.
- Переводы шаблонов не проверены носителями; для пилота нужен один приоритетный язык + review.
- Sandbox-кейс — это запись в локальной БД демо. Это **не** обращение в поддержку банка: блокировки переводов, SMS, кешбэка и смены SIM нет. Срок ответа поддержки не гарантируется.
- `X-Sandbox-Subject` — заглушка вместо авторизации. Для реальных данных нужны банковский gateway/identity, RBAC, PostgreSQL + audit, retention и требования ИБ.
- **Rate limiting не реализован.** Демо рассчитано на синтетику и локальный запуск; в пилоте квоты и лимиты обязаны закрываться на шлюзе банка.
- `/api/cases` и кейсы тренажёра смены номера отключены (410). Целевой путь — `/sandbox/cases` (SQLite).
- Логи пишутся в stdout, ПДн в них нет: субъект — только как необратимый хеш-префикс, `client_comment` не логируется вовсе. Для пилота нужны структурированные логи в SIEM и политика хранения.
- Финансовая модель иллюстративна и не является обещанием ROI.

> О score: добавление `reason_codes` не изменило ни score, ни level ни для одного
> демо-сценария (проверено тестом `test_reason_codes_do_not_change_score_for_sample_normal_and_sample_drop_attack`).
> При этом ранее исправленные дефекты аудита T03/T04/T07 **могли** изменить граничные
> значения score — это было осознанное решение аудита, а не регресс.

## Демо-сценарий для жюри (3 минуты)

1. Дашборд → **«Симулировать атаку вербовщика»** → RED-скоринг + алерт на узбекском/таджикском.
2. **«Создать обращение (песочница)»** → устойчивый `case_…`, повтор не плодит дубликаты, чужой кейс не виден.
3. Открыть `/docs` → показать контракт API, где видны `X-Sandbox-Subject` и `Idempotency-Key` (работает офлайн).
4. `python scripts/restart_smoke.py` → кейс переживает реальный перезапуск процесса.
5. Квиз → учебный приз (деньги не начисляются).
6. Тренажёр номера: без галочки OTP — запрет; один номер в разных форматах («+7 916…» vs «+7916…») — тоже запрет.
