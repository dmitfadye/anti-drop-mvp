"""Идемпотентность POST /sandbox/cases.

Правило: один Idempotency-Key в пределах одного субъекта = один case.
- тот же ключ + то же тело -> тот же case_id, HTTP 200, Idempotency-Replayed: true;
- тот же ключ + другое тело -> 422 IDEMPOTENCY_KEY_PAYLOAD_MISMATCH
  (существующий кейс не возвращаем и не переиспользуем);
- гонка при вставке -> ловим IntegrityError и перечитываем запись.

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
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Header, Request

from src.config import MAX_IDEMPOTENCY_KEY_LENGTH, get_logger
from src.errors import ApiError
from src.identity import subject_hash_prefix

log = get_logger("anti_drop.cases")

HEADER_NAME = "Idempotency-Key"

# fullmatch, а не ^...$: в Python '$' матчится перед завершающим '\n',
# из-за чего ключ "abc\n" проходил бы валидацию.
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
    """Dependency FastAPI. Request даёт фактическое значение, Header — видимость в OpenAPI."""
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


def _row_to_case(row: sqlite3.Row) -> dict:
    return {
        "case_id": row["case_id"],
        "status": row["status"],
        "created_at": row["created_at"],
        "subject_ref": row["subject_ref"],
        "evaluation_id": row["evaluation_id"],
        "selected_language": row["selected_language"],
        "contact_reason": row["contact_reason"],
        "sandbox": bool(row["sandbox"]),
    }


_COLUMNS = (
    "case_id, subject_ref, evaluation_id, idempotency_key, payload_hash, "
    "status, created_at, updated_at, sandbox, selected_language, contact_reason"
)


def find_by_idempotency_key(conn: sqlite3.Connection, key: str, subject_ref: str) -> sqlite3.Row | None:
    """Поиск строго в пределах субъекта: глобальный поиск раскрывал бы чужие кейсы."""
    return conn.execute(
        f"SELECT {_COLUMNS} FROM sandbox_cases WHERE idempotency_key = ? AND subject_ref = ?",
        (key, subject_ref),
    ).fetchone()


def create_case(
    conn: sqlite3.Connection,
    *,
    subject_ref: str,
    idempotency_key: str,
    evaluation_id: str,
    selected_language: str,
    contact_reason: str,
    payload_hash: str,
) -> tuple[dict, bool]:
    """Возвращает (case, replayed). Ошибка БД поднимается наружу как 503."""
    existing = find_by_idempotency_key(conn, idempotency_key, subject_ref)
    if existing is not None:
        return _replay_or_mismatch(existing, payload_hash, subject_ref)

    case_id = "case_" + uuid4().hex
    now = _utc_now()
    try:
        conn.execute(
            "INSERT INTO sandbox_cases ("
            "case_id, subject_ref, evaluation_id, idempotency_key, payload_hash, "
            "status, created_at, updated_at, sandbox, selected_language, contact_reason"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                case_id,
                subject_ref,
                evaluation_id,
                idempotency_key,
                payload_hash,
                "created",
                now,
                None,
                1,
                selected_language,
                contact_reason,
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # Гонка: параллельный запрос с тем же ключом и тем же субъектом вставил раньше нас.
        row = find_by_idempotency_key(conn, idempotency_key, subject_ref)
        if row is None:
            log.exception("case_insert_conflict_without_row subject_hash=%s",
                          subject_hash_prefix(subject_ref))
            raise ApiError(503, "STORAGE_UNAVAILABLE", "Не удалось сохранить обращение. Попробуйте позже.")
        log.info("case_conflict_resolved subject_hash=%s replayed=true",
                 subject_hash_prefix(subject_ref))
        return _replay_or_mismatch(row, payload_hash, subject_ref)

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


def _replay_or_mismatch(row: sqlite3.Row, payload_hash: str, subject_ref: str) -> tuple[dict, bool]:
    if row["payload_hash"] != payload_hash:
        log.info("idempotency_mismatch case_id=%s subject_hash=%s",
                 row["case_id"], subject_hash_prefix(subject_ref))
        raise ApiError(
            422,
            "IDEMPOTENCY_KEY_PAYLOAD_MISMATCH",
            "Idempotency-Key уже использован с другим содержимым запроса.",
            field=HEADER_NAME,
        )
    log.info("case_replayed case_id=%s subject_hash=%s", row["case_id"],
             subject_hash_prefix(subject_ref))
    return _row_to_case(row), True


def get_case_for_subject(conn: sqlite3.Connection, case_id: str, subject_ref: str) -> dict | None:
    """Поиск строго по (case_id, subject_ref).

    Кейс чужого субъекта намеренно неразличим от несуществующего (404, не 403),
    чтобы по коду ответа нельзя было проверить существование чужого кейса.
    """
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM sandbox_cases WHERE case_id = ? AND subject_ref = ?",
        (case_id, subject_ref),
    ).fetchone()
    return _row_to_case(row) if row is not None else None


def list_cases_for_subject(
    conn: sqlite3.Connection, subject_ref: str, limit: int, offset: int
) -> tuple[list[dict], int]:
    """Возвращает (страница кейсов, total_count по субъекту)."""
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM sandbox_cases WHERE subject_ref = ? "
        "ORDER BY created_at DESC, case_id DESC LIMIT ? OFFSET ?",
        (subject_ref, limit, offset),
    ).fetchall()
    total = conn.execute(
        "SELECT COUNT(*) FROM sandbox_cases WHERE subject_ref = ?", (subject_ref,)
    ).fetchone()[0]
    return [_row_to_case(r) for r in rows], int(total)