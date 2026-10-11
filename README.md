# AntiDrop / Анти-Дроп

Учебный fintech MVP для конкурса ВТБ «Финтех без границ»: объяснимый анализ синтетических переводов, безопасные подсказки, сохраняемые учебные обращения и курс «Спокойные переводы».

**Демонстрация, без банковской интеграции.** Реальные счета не подключены, переводы не блокируются, обращения в банк и SMS не отправляются, деньги и кешбэк не начисляются. Баллы правил — не вероятность мошенничества. Происхождение, гражданство и язык не являются признаками риска.

## Что работает

- Next.js: утверждённый светлый интерфейс, мониторинг, предупреждения, база знаний, учебная смена номера.
- FastAPI: детерминированные правила, строгие versioned snapshots, серверная проверка входных данных и владельца.
- PostgreSQL: evaluations, обращения, audit events, идемпотентность, учебный прогресс и награды.
- Обучение: семь тем из предоставленного `quizData.pdf`, 10 исходных статей, 40 карточек «правда/ложь», 25 исходных вопросов. В связанных темах некоторые тесты повторяются. Седьмая статья адаптирована из FAQ документа.
- На выбор: тест; мини-урок → карточки → итоговый тест; статья → вопрос на понимание.
- Серии 3/7/14/30 дней, учебные бонусы, ранги и шкала до следующего звания. После 30 дней подряд — выбор +1 демонстрационной категории кешбэка.
- Сохранены локализация RU/UZ, optional advisory и offline-инструменты экспериментов, оценки правил и финансовой модели. Переводы и учебные материалы имеют статус draft.

На локальном стенде **один общий синтетический профиль**: его прогресс виден всем участникам стенда. Это не персональная банковская аутентификация. «Топ 10%» не показывается без определённой сравнительной выборки.

## Архитектура

```mermaid
flowchart LR
  UI[Next.js / React] --> BFF[Next server API allowlist]
  BFF --> API[FastAPI]
  API --> RULES[Deterministic rules]
  API --> DB[(PostgreSQL 16)]
  API --> COURSE[Versioned learning catalog]
```

Браузер передаёт ответы, а не XP, дату или владельца. Next хранит demo credential на сервере и вызывает разрешённые API. FastAPI сопоставляет bearer-токен субъекту. Обучение не влияет на риск-скоринг. Case/event/idempotency и учебные начисления фиксируются транзакционно; недоступная БД даёт ошибку вместо успешного результата.

## Требования

Для Docker: Git, Python 3.10+ для генератора локальной конфигурации, работающий Docker Engine/Desktop с Compose v2. Проверены Python 3.12, PostgreSQL 16 и Node.js 22 в контейнерах.

Для разработки: uv, Python 3.12, Node.js 22 с npm. Next требует Node >=20.9. Python зависимости фиксирует `uv.lock`, npm — `frontend/package-lock.json`. На Windows Playwright по умолчанию использует установленный Edge; Linux CI использует Chromium.

## Быстрый старт

Все актуальные изменения находятся в единственной рабочей ветке `master`:

```powershell
git clone --branch master https://github.com/dmitfadye/anti-drop-mvp.git
cd anti-drop-mvp
python scripts/init_sandbox.py
docker compose up -d --build
docker compose ps
```

Генератор создаёт случайные локальные credentials в игнорируемых `.env` и `.local/`. Существующий `.env` не перезаписывается. Пароли не выводятся. Миграции выполняет одноразовый service `migrate`; API запускается после его успешного завершения, frontend — после готовности API.

- Приложение: http://127.0.0.1:3000/#learning
- Мониторинг: http://127.0.0.1:3000/#monitoring
- Swagger с локальными assets: http://127.0.0.1:8010/docs
- API process health: http://127.0.0.1:8010/api/health
- БД и schema readiness: http://127.0.0.1:8010/api/ready

Используйте именно `127.0.0.1`. Для другого адреса/порта измените `APP_ORIGIN` и пересоздайте frontend. Compose публикует frontend/API/PostgreSQL только на loopback (`3000`/`8010`/`5433`); наружу за хост ничего не выходит.

Остановка: `docker compose stop`. Повторный запуск: `docker compose up -d`. Не удаляйте volume, если нужен сохранённый прогресс. Старые существующие БД автоматически не конвертируются.

## Конфигурация

| Переменная | Назначение |
|---|---|
| `POSTGRES_PASSWORD` | Случайный пароль владельца схемы, только migration/admin job |
| `API_DATABASE_PASSWORD` | Отдельный пароль роли `antidrop_app` с DML privileges |
| `SANDBOX_TOKENS` | Серверный JSON token → `sub_...`, одинаковый профиль для API и Next |
| `SANDBOX_WEB_TOKEN` | Серверный credential Next; никогда не `NEXT_PUBLIC_*` |
| `SANDBOX_WEB_SUBJECT` | Синтетический subject для фиксированных demo episodes |
| `APP_ORIGIN` | Точный внешний origin, по умолчанию `http://127.0.0.1:3000` |
| `DATABASE_URL` | `postgresql+psycopg://...`; Compose задаёт внутренний адрес, генератор — native localhost:5433 |
| `BACKEND_URL` | Next runtime upstream; Compose `http://api:8000`, native `http://127.0.0.1:8010` |
| `TEST_DATABASE_URL` | Только отдельная `antidrop_test*` БД для PG-тестов |
| `PLAYWRIGHT_CHANNEL` | `chromium` для Linux/Chromium, иначе установленный Edge |
| `COMPOSE_PROJECT_NAME` | Необязательное стабильное имя локального стенда; сохраняйте его при переносе папки, чтобы использовать прежний volume |

Безопасный шаблон — `.env.example`, но быстрый старт использует генератор. Не публикуйте `.env` или `.local/demo-client.json`.

Optional P1 flags и ограничения описаны в [P1 preservation](docs/integration/P1_PRESERVATION.md). Advisory, experiments и event sink по умолчанию выключены. Они не включают реальные банковские действия.

## Разработка

Frontend локально, API/БД в Compose:

```powershell
uv sync --frozen
python scripts/configure_frontend.py
docker compose up -d --build api
cd frontend
npm ci
npm run dev
```

Откройте `http://127.0.0.1:3000`. Если Docker frontend уже занимает порт, сначала `docker compose stop frontend`. `configure_frontend.py` создаёт игнорируемый серверный `frontend/.env.local`, существующий файл сохраняет.

Для native backend вместо контейнерного API:

```powershell
docker compose stop api frontend
docker compose -f compose.yaml -f compose.dev.yaml up -d postgres
docker compose -f compose.yaml -f compose.dev.yaml run --rm migrate
uv run --frozen uvicorn main:app --reload --host 127.0.0.1 --port 8010 --env-file .env
```

`compose.dev.yaml` публикует PostgreSQL только на `127.0.0.1:5433`; generated `DATABASE_URL` использует runtime role. Этот override нужен только для native API. Миграция: `docker compose run --rm migrate`; inspection: `uv run --frozen alembic heads`. Не применять root migration поверх старой SQLite/psycopg2 схемы с одноимёнными таблицами.

## API

Актуальный контракт: `/openapi.json` и Swagger. Next BFF ограничивает доступ списком поддерживаемых путей; browser identity/auth headers не определяют владельца.

| Метод и путь FastAPI | Назначение |
|---|---|
| `POST /api/analyze` | Совместимый анализ одного синтетического клиента |
| `POST /api/v1/risk/evaluate` | Строгий snapshot, aware time, суммы в minor units |
| `POST /sandbox/evaluations` | Authenticated расчёт и сохранение решения |
| `POST /sandbox/cases` | Authenticated case; заголовок `Idempotency-Key` |
| `GET /sandbox/cases/{id}` | Case только своего субъекта |
| `GET /api/v1/learning/catalog` | Каталог без правильных ответов |
| `GET /api/v1/learning/progress` | Сохранённый прогресс своего субъекта |
| `POST /api/v1/learning/completions` | Проверка ответов и атомарное начисление |
| `POST /api/v1/learning/rewards/30/claim` | Разовый выбор учебной категории |
| `GET /api/content`, `POST /api/quiz`, `POST /api/sim` | Legacy учебные контракты |
| `/api/cases` | Retired unscoped case API, HTTP410 |

Пример completion body:

```json
{"module_id":"m1_safe_transfers","format":"article","answers":{"tf_001":1},"idempotency_key":"example-article-v1"}
```

Для `quiz` нужны все вопросы теста, для `lesson` — все карточки и тест, для `article` — первый вопрос-карточка. При 80% правильных ответов занятие засчитывается. Response содержит `result.score/total/passed/feedback` и `progress`; неправильные ответы не добавляют risk score. Повтор того же ключа возвращает исходный ответ, другой payload с тем же ключом —409. Валидация —422; недоступное хранилище —503; чужой объект —404/403. SQL, secrets и raw financial payload не возвращаются в ошибках.

## Учебные награды

Сутки считаются сервером по `Europe/Moscow`. Засчитывается максимум один день серии в сутки. Повтор одного module/format за день не начисляет XP повторно. Базовый лимит —100 баллов/день; первый успешно завершённый модуль отдельно даёт50. Первый успешный выбранный формат завершает модуль.

Награды серии: 3 дня +30, 7 +70, 14 +150, 30 +300 виртуальных баллов. После30 дней можно один раз выбрать продукты, транспорт, связь, образование или здоровье как дополнительную **учебную** категорию. Балльные награды этапов разовые. При успешном занятии с серией не короче 30 дней выдаётся один выбор категории за московский календарный месяц. Новый подходящий месяц открывает новый выбор; история сохраняется, прошлый незаявленный выбор доступен через optional period в API. Grace/freeze пока отсутствует; пропуск начинает новую серию, сохраняя XP и завершённые модули.

Звания: Новый участник → Уверенный пользователь → Знаток денег → Финансовый навигатор → Мастер безопасных переводов. Это прогресс курса, не сертифицированная оценка финансовой грамотности.

## Демо для жюри

1. Откройте мониторинг → «Проверить учебный сценарий».
2. Выберите обычные операции: GREEN/0. Затем сценарий вербовщика: RED/85 при фиксированных учебных данных и времени.
3. Прочитайте объяснения. «Поддержка — демо» создаёт настоящий PostgreSQL sandbox-case, но обращение в банк не отправляет.
4. Нажмите «Проверить сохранённый кейс»: интерфейс получает тот же ID из API.
5. В обучении выберите формат и тему. Для первой статьи правильное действие — не считать просьбу знакомого автоматически безопасной: ответ «Ложь».
6. Завершите занятие, перезагрузите страницу: прогресс сохранён. Многократное нажатие не создаёт повторных баллов.
7. Перезапустите services без удаления volume: кейсы и прогресс остаются.

CLI-проверка case/replay/retrieval:

```powershell
uv run --frozen python -m scripts.demo_sandbox
docker compose restart postgres api
uv run --frozen python -m scripts.demo_sandbox --verify-existing
```

Если база ещё стартует, дождитесь healthy и повторите retrieval.

## Тестирование

```powershell
uv sync --frozen
# Указать URL отдельной disposable PostgreSQL БД antidrop_test*:
$env:TEST_DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@127.0.0.1:PORT/antidrop_test_local'
uv run --frozen pytest -q
cd frontend
npm ci
npm run lint
npm run typecheck
npm run build
# API должен работать, frontend/.env.local настроен:
$env:APP_ORIGIN = 'http://127.0.0.1:3001'
npm run test:e2e
npm audit --omit=dev
```

Для Chromium: `$env:PLAYWRIGHT_CHANNEL='chromium'`, `npx playwright install chromium`. Браузерные тесты сами запускают production Next на3001. Без `TEST_DATABASE_URL` PG-проверки пропускаются; это не подтверждение persistence. Нельзя использовать основную demo/общую БД как тестовую. CI содержит пример полностью изолированной PostgreSQL-конфигурации.

Результаты и ограничения — [QUALITY_REPORT](docs/integration/QUALITY_REPORT.md). Исторические fixture reports не доказывают банковскую accuracy. P1 ablation сейчас явно NOT RUN, а не поддельный результат.

## Структура

`frontend/` — Next UI, server BFF и Playwright; `main.py`, `models.py`, `src/` — FastAPI/domain/storage/learning; `anti_drop_ml/` — строгие rule contracts и offline evaluation, без inference; `migrations/` — Alembic; `data/learning/course.json` — versioned draft content; `scripts/` — безопасная локальная настройка и проверки; `infra/` — runtime database role; `docs/integration/` — аудит, решения, QA и cleanup plan.

## Резервная копия

Не менять существующую БД без backup и проверенного восстановления. Пример binary backup без перенаправления binary stdout через PowerShell:

```powershell
New-Item -ItemType Directory -Force backups
docker compose exec postgres pg_dump -U antidrop -d antidrop -Fc -f /tmp/antidrop.dump
docker compose cp postgres:/tmp/antidrop.dump backups/antidrop.dump
```

Проверять restore в новой отдельной БД, не поверх действующих данных. `backups/` игнорируется Git.

## Troubleshooting

- Заняты3000/8010: остановите предыдущий локальный процесс или измените port mapping и `APP_ORIGIN` вместе.
- Docker не отвечает: запустите Desktop/Engine, проверьте `docker info`.
- API503: `docker compose ps`, `docker compose logs --tail 80 migrate api`; readiness проверяет схему/БД, health — процесс.
- Migration failure: не делайте `stamp head` и не удаляйте данные; проверьте наличие старой несовместимой схемы и permissions.
- Нет конфигурации: генератор запускать из root; он не перезаписывает существующий `.env`.
- Browser403 при POST: origin должен точно совпасть с `APP_ORIGIN`; localhost и127.0.0.1 различаются.
- Frontend не видит backend: проверьте `BACKEND_URL`, server credentials и совпадение `SANDBOX_WEB_SUBJECT` с token mapping.
- Установка: `uv sync --frozen` / `npm ci`; не смешивайте package managers и не используйте force-upgrade для обхода ошибок.

## Безопасность, ограничения и развитие

Материалы с source-needed flags остаются черновыми; юридическая и native-language проверка не заявляется. Нет гарантии предотвращения мошенничества. Известны synthetic false positives. Optional P1 operator runtime отложен до authenticated PostgreSQL adaptation; старое небезопасное хранилище не активировано. Demo credential не подходит для банковского production gateway.

Пять связанных HIGH advisories находятся в dev-цепочке ESLint/braces; совместимого исправленного релиза на дату проверки не найдено. Production dependency audit отдельно чистый. Не выполняйте lint по недоверенным внешним glob-паттернам. Подробности и остальные риски — quality report.

Для банковского пилота нужны персональная server identity, data/security agreements, legal/native review, представительские размеченные данные, наблюдаемость, нагрузочные проверки и отдельно согласованная бонусная программа. Реальные rewards, SMS и банковские ограничения не входят в этот MVP.
