"""Конфигурация MVP-слоя через env. Без pydantic-settings: только stdlib.

Sandbox-режим не является production-контур��м. `X-Sandbox-Subject` и `SANDBOX_MODE`
существуют для локального демо; для реальных данных субъект должен приходить
из банковского gateway/SSO, а не из браузера.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

APP_ENV = os.getenv("APP_ENV", "sandbox")
SANDBOX_MODE = os.getenv("SANDBOX_MODE", "true").strip().lower() in ("1", "true", "yes")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()

# Относительный путь зависит от текущего каталога запуска: молча можно получить
# другую БД. Поэтому разрешаем его один раз при старте относительно корня репозитория.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_RAW_DB_PATH = Path(os.getenv("DATABASE_PATH", "./data/anti_drop_mvp.db"))
DATABASE_PATH = _RAW_DB_PATH if _RAW_DB_PATH.is_absolute() else (_REPO_ROOT / _RAW_DB_PATH)

MAX_CLIENT_COMMENT_LENGTH = int(os.getenv("MAX_CLIENT_COMMENT_LENGTH", "1000"))
MAX_IDEMPOTENCY_KEY_LENGTH = 128
MAX_SUBJECT_LENGTH = 128
MAX_EVALUATION_ID_LENGTH = 128
MAX_LIST_LIMIT = 100
DEFAULT_LIST_LIMIT = 20
SQLITE_TIMEOUT_SECONDS = 5.0

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def configure_logging() -> None:
    """Настройка логов при старте. Идемпотентна: повторный вызов не дублирует handler."""
    root = logging.getLogger()
    if any(getattr(h, "_anti_drop_handler", False) for h in root.handlers):
        root.setLevel(LOG_LEVEL)
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler._anti_drop_handler = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(LOG_LEVEL)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


SANDBOX_NOTICE = (
    "Песочница: обращение зарегистрировано только в демо-хранилище. "
    "Реальная банковская блокировка переводов, SMS, выплата кешбэка и обращение "
    "в production-поддержку не выполнялись. Срок ответа поддержки не гарантируется."
)

SANDBOX_NOTICE_EN = (
    "Sandbox: the request is registered in demo storage only. No real bank blocking, "
    "no SMS, no cashback and no production support ticket were created. "
    "No support response time is guaranteed."
)

NOTICES = {"ru": SANDBOX_NOTICE, "en": SANDBOX_NOTICE_EN}