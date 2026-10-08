"""Sandbox-кейсы обращений (T02): устойчивый case_id + идемпотентность.

Это УЧЕБНАЯ фиксация обращения для демо: поддержка банка НЕ вызывается,
операции НЕ ограничиваются. Повтор запроса с тем же idempotency_key
возвращает тот же кейс, а не создаёт дубликат. Хранилище — в памяти
одного процесса (для пилота нужен PostgreSQL + audit).
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from src.policy import UTC

_STORE: dict[str, dict] = {}

NOTE = "Учебный кейс (демо): поддержка не вызывается, операции не ограничиваются."


def create_case(summary: str, lang: str, score: int, idempotency_key: str | None) -> dict:
    key = (idempotency_key or f"{summary}|{lang}|{score}").strip() or "empty"
    case_id = "CASE-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:8].upper()
    existed = case_id in _STORE
    if not existed:
        _STORE[case_id] = {
            "case_id": case_id,
            "status": "open-sandbox",
            "demo": True,
            "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "summary": summary[:500],
            "lang": lang,
            "score": score,
            "note": NOTE,
        }
    return {**_STORE[case_id], "deduped": existed}


def get_case(case_id: str) -> dict | None:
    return _STORE.get(case_id.upper())
