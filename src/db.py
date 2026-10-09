"""PostgreSQL/SQLite-хранилище sandbox-кейсов.

Security boundary: клиент не может подменить субъекта — он приходит из
доверенного для демо заголовка. В БД не попадают client_comment, телефоны,
карты и OTP: comment участвует только в payload_hash и не сохраняется.
Все запросы параметризованы.

Поддерживает два режима:
- PostgreSQL (если задан PG_DSN) — пул соединений psycopg2
- SQLite (fallback) — для локальной разработки без Docker
"""
from __future__ import annotations

import contextlib
import os
import sqlite3
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from fastapi.exceptions import RequestValidationError

from src.config import (
    DATABASE_PATH,
    PG_DSN,
    SCHEMA_VERSION,
    SQLITE_TIMEOUT_SECONDS,
    get_logger,
)
from src.errors import ApiError

log = get_logger("anti_drop.db")

SCHEMA_VERSION = 2

# PostgreSQL DDL
PG_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS sandbox_cases (
    case_id           TEXT PRIMARY KEY,
    subject_ref       TEXT NOT NULL,
    evaluation_id     TEXT NOT NULL,
    idempotency_key   TEXT NOT NULL,
    payload_hash      TEXT NOT NULL,
    status            TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL,
    updated_at        TIMESTAMPTZ,
    sandbox           BOOLEAN NOT NULL DEFAULT TRUE,
    selected_language TEXT NOT NULL,
    contact_reason    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

PG_INDEXES_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS ux_sandbox_cases_subject_idempotency_key
    ON sandbox_cases(subject_ref, idempotency_key);

CREATE INDEX IF NOT EXISTS ix_sandbox_cases_subject_created_at
    ON sandbox_cases(subject_ref, created_at DESC);
"""

LEGACY_INDEX_NAME = "ux_sandbox_cases_idempotency_key"

# SQLite DDL (fallback)
SQLITE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS sandbox_cases (
    case_id           TEXT PRIMARY KEY,
    subject_ref       TEXT NOT NULL,
    evaluation_id     TEXT NOT NULL,
    idempotency_key   TEXT NOT NULL,
    payload_hash      TEXT NOT NULL,
    status            TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    updated_at        TEXT,
    sandbox           INTEGER NOT NULL DEFAULT 1,
    selected_language TEXT NOT NULL,
    contact_reason    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

SQLITE_INDEXES_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS ux_sandbox_cases_subject_idempotency_key
    ON sandbox_cases(subject_ref, idempotency_key);

CREATE INDEX IF NOT EXISTS ix_sandbox_cases_subject_created_at
    ON sandbox_cases(subject_ref, created_at DESC);
"""

LEGACY_INDEX_NAME = "ux_sandbox_cases_idempotency_key"

# Thread-safe initialization state
_init_lock = threading.Lock()
_initialized: set[str] = set()

# PostgreSQL connection pool (lazy-initialized)
_pg_pool: Any = None
_pool_lock = threading.Lock()


def _use_postgres() -> bool:
    return bool(PG_DSN)


def _get_pg_pool():
    """Lazy-initialize PostgreSQL connection pool."""
    global _pg_pool
    if _pg_pool is not None:
        return _pg_pool
    with _pool_lock:
        if _pg_pool is not None:
            return _pg_pool
        import psycopg2
        from psycopg2.pool import ThreadedConnectionPool

        dsn = PG_DSN
        if not dsn:
            raise RuntimeError("PG_DSN не задан, но запрошен PostgreSQL пул")

        pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=dsn,
        )
        _pg_pool = pool
        log.info("pg_pool_created minconn=1 maxconn=10")
        return pool


@contextlib.contextmanager
def _pg_connection() -> Iterator[Any]:
    """Context manager для PostgreSQL соединения из пула."""
    pool = _get_pg_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


@contextlib.contextmanager
def _sqlite_connection(path: Path) -> Iterator[Any]:
    """Context manager для SQLite соединения."""
    conn = sqlite3.connect(path, timeout=SQLITE_TIMEOUT_SECONDS)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON;")
        yield conn
        conn.commit()
    except sqlite3.Error as exc:
        log.exception("db_error path=%s", path)
        raise ApiError(503, "STORAGE_UNAVAILABLE", "Хранилище песочницы недоступно. Попробуйте позже.") from exc
    finally:
        conn.close()


@contextlib.contextmanager
def _use_connection() -> Iterator[Any]:
    """Единая точка входа: PostgreSQL если есть PG_DSN, иначе SQLite."""
    if _use_postgres():
        with _pg_connection() as conn:
            yield conn
    else:
        path = DATABASE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        with _sqlite_connection(path) as conn:
            yield conn


def _index_names_pg(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'sandbox_cases'
        """)
        return {row[0] for row in cur.fetchall()}


def _index_names_sqlite(conn) -> set[str]:
    return {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='sandbox_cases'")}


def _migrate_pg(conn) -> None:
    """Удалить устаревший глобальный индекс идемпотентности, если он остался в БД."""
    names = _index_names_pg(conn)
    with conn.cursor() as cur:
        if LEGACY_INDEX_NAME in names:
            cur.execute(f"DROP INDEX IF EXISTS {LEGACY_INDEX_NAME}")
            log.info("db_migration action=drop_legacy_index index=%s", LEGACY_INDEX_NAME)
        if "ux_sandbox_cases_subject_idempotency_key" not in names:
            log.info("db_migration action=create_composite_index index=%s",
                     "ux_sandbox_cases_subject_idempotency_key")


def _migrate_sqlite(conn) -> None:
    """Удалить устаревший глобальный индекс идемпотентности в SQLite."""
    names = _index_names_sqlite(conn)
    if LEGACY_INDEX_NAME in names:
        conn.execute(f"DROP INDEX IF EXISTS {LEGACY_INDEX_NAME}")
        log.info("db_migration action=drop_legacy_index index=%s", LEGACY_INDEX_NAME)
    if "ux_sandbox_cases_subject_idempotency_key" not in names:
        log.info("db_migration action=create_composite_index index=%s",
                 "ux_sandbox_cases_subject_idempotency_key")


def init_db(path: Path | None = None) -> None:
    """Идемпотентная инициализация схемы. Вызывается на startup приложения."""
    target = path or DATABASE_PATH
    with _init_lock:
        key = "pg" if _use_postgres() else str(target)
        if key in _initialized:
            return

        if _use_postgres():
            with _pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")  # test connection
                with conn.cursor() as cur:
                    cur.execute(PG_TABLES_SQL)
                    _migrate_pg(conn)
                    cur.execute(PG_INDEXES_SQL)
                    cur.execute(
                        "INSERT INTO schema_meta (key, value) VALUES ('schema_version', %s) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (str(SCHEMA_VERSION),),
                    )
                conn.commit()
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with _sqlite_connection(DATABASE_PATH) as conn:
                conn.executescript(SQLITE_TABLES_SQL)
                _migrate_sqlite(conn)
                conn.executescript(SQLITE_INDEXES_SQL)
                conn.execute(
                    "INSERT INTO schema_meta (key, value) VALUES ('schema_version', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (str(SCHEMA_VERSION),),
                )
                conn.commit()

        _initialized.add(key)
        mode = "postgres" if _use_postgres() else "sqlite"
        if _use_postgres():
            # DSN с паролем в логи не пишем.
            log.info("db_ready mode=%s schema_version=%s", mode, SCHEMA_VERSION)
        else:
            log.info("db_ready mode=%s path=%s schema_version=%s",
                     mode, target.resolve(), SCHEMA_VERSION)


def get_db() -> Iterator[Any]:
    """FastAPI dependency: соединение на запрос, закрытие в finally.

    При недоступности хранилища отдаём 503 STORAGE_UNAVAILABLE, а не создаём
    имитацию успеха.

    ApiError эндпоинта (422/404/...) и ошибки валидации запроса пропускаем
    как есть: заворачивать их в 503 нельзя, иначе клиент получит
    «хранилище недоступно» вместо настоящей причины (например,
    IDEMPOTENCY_KEY_PAYLOAD_MISMATCH или VALIDATION_ERROR).
    """
    try:
        init_db()
        with _use_connection() as conn:
            yield conn
    except (ApiError, RequestValidationError):
        raise
    except Exception as exc:
        if _use_postgres():
            log.exception("pg_db_error")
        else:
            log.exception("db_error path=%s", DATABASE_PATH)
        raise ApiError(503, "STORAGE_UNAVAILABLE", "Хранилище песочницы недоступно. Попробуйте позже.") from exc


def reset_init_state_for_tests() -> None:
    """Сбросить кэш инициализации, чтобы тесты могли менять DATABASE_PATH."""
    global _pg_pool
    with _init_lock:
        _initialized.clear()
        if _pg_pool is not None:
            _pg_pool.closeall()
            _pg_pool = None