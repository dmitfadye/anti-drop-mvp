# db — PostgreSQL для песочницы

Официальный образ `postgres:16-alpine`, своих init-скриптов нет:
схема БД создаётся приложением при старте (`app/src/db.py::init_db`
через lifespan в `app/main.py`), поэтому папка держит только этот README.

## Топология (см. корневой `docker-compose.yml`)

| Что | Где |
|---|---|
| Сервис | `postgres` |
| Порт наружу | `127.0.0.1:5433` → `5432` (5433 чтобы не clash с локальным PG) |
| Внутри compose-сети | `postgres:5432`, `PG_DSN=postgresql://anti_drop:anti_drop@postgres:5432/anti_drop` |
| Данные | именованный volume `pgdata` (переживает пересоздание контейнеров) |
| Health | `pg_isready`, `api` стартует только после `service_healthy` |

Учётка `anti_drop/anti_drop` — демо-only, только синтетика.
Локальный SQLite-fallback (`./data/anti_drop_mvp.db`) используется,
когда `PG_DSN` не задан (см. `.env.example`).
