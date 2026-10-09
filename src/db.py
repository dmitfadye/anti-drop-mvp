"""SQLite-хранилище sandbox-кейсов (stdlib sqlite3, без ORM).

Security boundary: клиент не может подменить субъекта — он приходит из
доверенного для демо заголовка. В БД не попадают client_comment, телефоны,
карты и OTP: comment участвует только в payload_hash и не сохраняется.
Все запросы параметризованы.
"""
from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from pathlib import Path

from src.config import DATABASE_PATH, SQLITE_TIMEOUT_SECONDS, get_logger
from src.errors import ApiError

log = get_logger("anti_drop.db")

SCHEMA_VERSION = 2

TABLES_SQL = """
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

# Составной индекс: идемпотентность действует в пределах одного субъекта.
# Глобальный unique на idempotency_key позволял бы одному субъекту занять ключ,
# заблокировав им другого, и подсказывал бы факт занятости ключа.
INDEXES_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS ux_sandbox_cases_subject_idempotency_key
    ON sandbox_cases(subject_ref, idempotency_key);

CREATE INDEX IF NOT EXISTS ix_sandbox_cases_subject_created_at
    ON sandbox_cases(subject_ref, created_at DESC);
"""

LEGACY_INDEX_NAME = "ux_sandbox_cases_idempotency_key"

_init_lock = threading.Lock()
_initialized: set[str] = set()


def _db_path() -> Path:
    return DATABASE_PATH


def _index_names(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='sandbox_cases'")}


def _migrate(conn: sqlite3.Connection) -> None:
    """Удалить устаревший глобальный индекс идемпотентности, если он остался в БД.

    CREATE INDEX IF NOT EXISTS не удалил бы старый индекс, поэтому на существующей
    демо-БД он продолжал бы делать ключ глобально уникальным. DROP INDEX идемпотентен
    и не трогает данные.
    """
    names = _index_names(conn)
    if LEGACY_INDEX_NAME in names:
        conn.execute(f"DROP INDEX IF EXISTS {LEGACY_INDEX_NAME}")
        log.info("db_migration action=drop_legacy_index index=%s", LEGACY_INDEX_NAME)
    if "ux_sandbox_cases_subject_idempotency_key" not in names:
        log.info("db_migration action=create_composite_index index=%s",
                 "ux_sandbox_cases_subject_idempotency_key")


def init_db(path: Path | None = None) -> None:
    """Идемпотентная инициализация схемы. Вызывается на startup приложения."""
    target = path or _db_path()
    with _init_lock:
        if str(target) in _initialized:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(target, timeout=SQLITE_TIMEOUT_SECONDS)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.executescript(TABLES_SQL)
            _migrate(conn)
            conn.executescript(INDEXES_SQL)
            conn.execute(
                "INSERT INTO schema_meta (key, value) VALUES ('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(SCHEMA_VERSION),),
            )
            conn.commit()
        finally:
            conn.close()
        _initialized.add(str(target))
        log.info("db_ready path=%s schema_version=%s", target.resolve(), SCHEMA_VERSION)


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: соединение на запрос, закрытие в finally.

    При недоступности хранилища отдаём 503 STORAGE_UNAVAILABLE, а не создаём
    имитацию успеха.
    """
    path = _db_path()
    try:
        init_db(path)
        conn = sqlite3.connect(path, timeout=SQLITE_TIMEOUT_SECONDS)
    except sqlite3.Error as exc:
        log.exception("db_unavailable path=%s", path)
        raise ApiError(503, "STORAGE_UNAVAILABLE", "Хранилище песочницы недоступно. Попробуйте позже.") from exc
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON;")
        yield conn
    except sqlite3.Error as exc:
        log.exception("db_error path=%s", path)
        raise ApiError(503, "STORAGE_UNAVAILABLE", "Хранилище песочницы недоступно. Попробуйте позже.") from exc
    finally:
        conn.close()


def reset_init_state_for_tests() -> None:
    """Сбросить кэш инициализации, чтобы тесты могли менять DATABASE_PATH."""
    with _init_lock:
        _initialized.clear()