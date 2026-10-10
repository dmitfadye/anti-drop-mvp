"""Идемпотентность POST /sandbox/cases.

Правило: один Idempotency-Key в пределах одного субъекта = один case.
- тот же ключ + то же тело -> тот же case_id, HTTP 200, Idempotency-Replayed: true;
- тот же ключ + другое тело -> 422 IDEMPOTENCY_KEY_PAYLOAD_MISMATCH
  (существующий кейс не возвращаем и не переиспользуем);
- гонка при вставке -> ловим конфликт уникальности и перечитываем запись.

Область действия ключа — (subject_ref, idempotency_key), а не глобальный ключ:
иначе субъект A мог бы занять ключ и заблокировать им субъекта B, а по коду
ответа B узнавал бы, что ключ кем-то уже использован.

В payload_hash входят только поля тела: заголовки, subject, request_id и время
сервера исключены, иначе повтор с тем же ключом ломался бы ложно.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Tuple

from fastapi import Header, Request
from psycopg2.extras import RealDictCursor

from src.config import MAX_IDEMPOTENCY_KEY_LENGTH, get_logger
from src.db import _use_postgres
from src.errors import ApiError
from src.identity import subject_hash_prefix

log = get_logger("anti_drop.cases")


def _pg_cursor(conn: Any):
    """Dict-курсор для PostgreSQL: строки как отображения колонка->значение,
    аналогично sqlite3.Row. Дефолтный курсор отдаёт кортежи, с которыми
    _row_to_case (доступ по именам) не работает."""
    return conn.cursor(cursor_factory=RealDictCursor)

HEADER_NAME = "Idempotency-Key"

IDEMPOTENCY_KEY_PATTERN = r"[A-Za-z0-9._:-]{1,128}"
KEY_RE = re.compile(IDEMPOTENCY_KEY_PATTERN)

IDEMPOTENCY_KEY_DESCRIPTION = (
    "Ключ идемпотентности запроса в пределах одного субъекта "
    "(scope: X-Sandbox-Subject + Idempotency-Key). "
    "Повтор с тем же ключом и тем же телом вернёт тот же case_id; "
    "с другим телом — 422 IDEMPOTENCY_KEY_PAYLOAD_MISMATCH."
)

CONTACT_REASONS = (
    "suspicious_transfer_request",
    "unexpected_incoming_funds",
    "asked_to_forward_money",
    "other",
)

CASE_STATUSES = ("created", "failed")


def get_idempotency_key(
    request: Request,
    idempotency_key: str | None = Header(
        default=None, alias=HEADER_NAME, description=IDEMPOTENCY_KEY_DESCRIPTION, examples=["idem-001"]
    ),
) -> str:
    header_value = request.headers.get(HEADER_NAME)
    raw = header_value if header_value is not None else idempotency_key
    if raw is None or not raw.strip():
        raise ApiError(
            422,
            "MISSING_IDEMPOTENCY_KEY",
            f"Обязательный заголовок {HEADER_NAME} не передан.",
            field=HEADER_NAME,
        )
    key = raw.strip()
    if len(key) > MAX_IDEMPOTENCY_KEY_LENGTH or not KEY_RE.fullmatch(key):
        raise ApiError(
            422,
            "INVALID_IDEMPOTENCY_KEY",
            "Недопустимый формат Idempotency-Key: допустимы латинские буквы, цифры и символы . _ - :, длина 1-128.",
            field=HEADER_NAME,
        )
    return key


def compute_payload_hash(payload: dict) -> str:
    canonical = {
        "evaluation_id": payload["evaluation_id"],
        "selected_language": payload["selected_language"],
        "contact_reason": payload["contact_reason"],
        "client_comment": (payload.get("client_comment") or "").strip() or None,
    }
    raw = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Column list for SELECT queries
_COLUMNS = (
    "case_id, subject_ref, evaluation_id, idempotency_key, payload_hash, "
    "status, created_at, updated_at, sandbox, selected_language, contact_reason"
)


def _row_to_case(row: Any) -> dict:
    """Convert DB row to case dict (works for both psycopg2 and sqlite3 rows).

    PostgreSQL возвращает TIMESTAMPTZ как datetime, SQLite — как TEXT:
    приводим к ISO-строке здесь, чтобы контракт ответа был одинаковым.
    """
    return {
        "case_id": row["case_id"],
        "subject_ref": row["subject_ref"],
        "evaluation_id": row["evaluation_id"],
        "idempotency_key": row["idempotency_key"],
        "payload_hash": row["payload_hash"],
        "status": row["status"],
        "created_at": _as_iso(row["created_at"]),
        "updated_at": _as_iso(row["updated_at"]),
        "sandbox": bool(row["sandbox"]),
        "selected_language": row["selected_language"],
        "contact_reason": row["contact_reason"],
    }


def _as_iso(value: Any) -> Any:
    """datetime из PostgreSQL -> ISO-строка; остальное без изменений."""
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _use_postgres() -> bool:
    from src.config import PG_DSN
    return bool(PG_DSN)


def _get_dialect(conn: Any) -> str:
    if hasattr(conn, 'cursor') and hasattr(conn, 'dsn'):
        return "pg"
    return "sqlite"


def find_by_idempotency_key(conn: Any, key: str, subject_ref: str) -> Any:
    """Поиск строго в пределах субъекта: глобальный поиск раскрывал бы чужие кейсы."""
    if _use_postgres():
        with _pg_cursor(conn) as cur:
            cur.execute(
                "SELECT case_id, subject_ref, evaluation_id, idempotency_key, payload_hash, "
                "status, created_at, updated_at, sandbox, selected_language, contact_reason "
                "FROM sandbox_cases WHERE idempotency_key = %s AND subject_ref = %s",
                (key, subject_ref)
            )
            return cur.fetchone()
    else:
        return conn.execute(
            "SELECT case_id, subject_ref, evaluation_id, idempotency_key, payload_hash, "
            "status, created_at, updated_at, sandbox, selected_language, contact_reason "
            "FROM sandbox_cases WHERE idempotency_key = ? AND subject_ref = ?",
            (key, subject_ref)
        ).fetchone()


def create_case(
    conn: Any,
    *,
    subject_ref: str,
    idempotency_key: str,
    evaluation_id: str,
    selected_language: str,
    contact_reason: str,
    payload_hash: str,
) -> tuple[dict, bool]:
    existing = find_by_idempotency_key(conn, idempotency_key, subject_ref)
    if existing is not None:
        return _replay_or_mismatch(existing, payload_hash, subject_ref)

    case_id = "case_" + uuid.uuid4().hex
    now = _utc_now()

    if _use_postgres():
        with _pg_cursor(conn) as cur:
            try:
                cur.execute("""
                    INSERT INTO sandbox_cases (
                        case_id, subject_ref, evaluation_id, idempotency_key, payload_hash,
                        status, created_at, updated_at, sandbox, selected_language, contact_reason
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (subject_ref, idempotency_key) DO UPDATE SET
                        payload_hash = EXCLUDED.payload_hash
                    RETURNING case_id, subject_ref, evaluation_id, idempotency_key, payload_hash,
                              status, created_at, updated_at, sandbox, selected_language, contact_reason
                """, (
                    case_id, subject_ref, evaluation_id, idempotency_key, payload_hash,
                    "created", now, None, True, selected_language, contact_reason
                ))
                row = cur.fetchone()
                conn.commit()
                if row:
                    return _row_to_case(dict(row)), False
            except Exception:
                conn.rollback()
                raise
    else:
        # SQLite path
        existing = find_by_idempotency_key(conn, idempotency_key, subject_ref)
        if existing is not None:
            return _replay_or_mismatch(existing, payload_hash, subject_ref)

        try:
            conn.execute(
                """INSERT INTO sandbox_cases (
                    case_id, subject_ref, evaluation_id, idempotency_key, payload_hash,
                    status, created_at, updated_at, sandbox, selected_language, contact_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (case_id, subject_ref, evaluation_id, idempotency_key, payload_hash,
                 "created", now, None, 1, selected_language, contact_reason)
            )
            conn.commit()
        except Exception as exc:
            if "UNIQUE constraint failed" in str(exc) or "unique constraint" in str(exc).lower():
                row = find_by_idempotency_key(conn, idempotency_key, subject_ref)
                if row is None:
                    raise ApiError(503, "STORAGE_UNAVAILABLE", "Не удалось сохранить обращение. Попробуйте позже.")
                return _replay_or_mismatch(row, payload_hash, subject_ref)
            raise

    log.info("case_created case_id=%s subject_hash=%s evaluation_id=%s language=%s reason=%s",
             case_id, subject_hash_prefix(subject_ref), evaluation_id, selected_language, contact_reason)
    return {
        "case_id": case_id,
        "status": "created",
        "created_at": now,
        "subject_ref": subject_ref,
        "evaluation_id": evaluation_id,
        "selected_language": selected_language,
        "contact_reason": contact_reason,
        "sandbox": True,
    }, False


def _replay_or_mismatch(row: Any, payload_hash: str, subject_ref: str) -> tuple[dict, bool]:
    case = _row_to_case(row)
    if case["payload_hash"] != payload_hash:
        log.info("idempotency_mismatch case_id=%s subject_hash=%s",
                 case["case_id"], subject_hash_prefix(subject_ref))
        raise ApiError(
            422,
            "IDEMPOTENCY_KEY_PAYLOAD_MISMATCH",
            "Idempotency-Key уже использован с другим содержимым запроса.",
            field="Idempotency-Key",
        )
    log.info("case_replayed case_id=%s subject_hash=%s",
             case["case_id"], subject_hash_prefix(subject_ref))
    return case, True


def get_case_for_subject(conn: Any, case_id: str, subject_ref: str) -> dict | None:
    if _use_postgres():
        with _pg_cursor(conn) as cur:
            cur.execute(
                "SELECT case_id, subject_ref, evaluation_id, idempotency_key, payload_hash, "
                "status, created_at, updated_at, sandbox, selected_language, contact_reason "
                "FROM sandbox_cases WHERE case_id = %s AND subject_ref = %s",
                (case_id, subject_ref)
            )
            row = cur.fetchone()
            return _row_to_case(row) if row else None
    else:
        row = conn.execute(
            "SELECT case_id, subject_ref, evaluation_id, idempotency_key, payload_hash, "
            "status, created_at, updated_at, sandbox, selected_language, contact_reason "
            "FROM sandbox_cases WHERE case_id = ? AND subject_ref = ?",
            (case_id, subject_ref)
        ).fetchone()
        return _row_to_case(row) if row else None


def list_cases_for_subject(
    conn: Any, subject_ref: str, limit: int, offset: int
) -> tuple[list[dict], int]:
    if _use_postgres():
        with _pg_cursor(conn) as cur:
            cur.execute(
                "SELECT case_id, subject_ref, evaluation_id, idempotency_key, payload_hash, "
                "status, created_at, updated_at, sandbox, selected_language, contact_reason "
                "FROM sandbox_cases WHERE subject_ref = %s "
                "ORDER BY created_at DESC, case_id DESC LIMIT %s OFFSET %s",
                (subject_ref, limit, offset)
            )
            rows = cur.fetchall()
            cur.execute(
                "SELECT COUNT(*) AS total FROM sandbox_cases WHERE subject_ref = %s",
                (subject_ref,)
            )
            total = cur.fetchone()["total"]
            return [_row_to_case(dict(row)) for row in rows], int(total)
    else:
        rows = conn.execute(
            "SELECT case_id, subject_ref, evaluation_id, idempotency_key, payload_hash, "
            "status, created_at, updated_at, sandbox, selected_language, contact_reason "
            "FROM sandbox_cases WHERE subject_ref = ? "
            "ORDER BY created_at DESC, case_id DESC LIMIT ? OFFSET ?",
            (subject_ref, limit, offset)
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM sandbox_cases WHERE subject_ref = ?",
            (subject_ref,)
        ).fetchone()[0]
        return [_row_to_case(row) for row in rows], int(total)