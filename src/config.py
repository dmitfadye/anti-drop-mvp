"""Конфигурация MVP-слоя через env. Без pydantic-settings: только stdlib.

Sandbox-режим не является production-контуром. `X-Sandbox-Subject` и `SANDBOX_MODE`
существуют для локального демо; для реальных данных субъект должен приходить
из банковского gateway/SSO, а не из браузера.

Env-файлы `.env` и `.env.example` в корне репозитория подхватываются
автоматически (stdlib-парсер ниже, без зависимостей): `.env` имеет приоритет,
`.env.example` добирает недостающие ключи. Реальное окружение процесса
важнее обоих файлов и никогда не перезаписывается.
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _load_env_file(path: Path) -> None:
    """Загрузить KEY=VALUE из файла, не затирая существующее окружение.

    Понимает пустые строки, `#`-комментарии, префикс `export ` и значения
    в одинарных/двойных кавычках. Вложенных подстановок (`$VAR`) и инлайн-
    комментариев нет — для demo-конфига достаточно.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        if not _ENV_KEY_RE.match(key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key not in os.environ:
            os.environ[key] = value


for _env_name in (".env", ".env.example"):
    _load_env_file(_REPO_ROOT / _env_name)

APP_ENV = os.getenv("APP_ENV", "sandbox")
SANDBOX_MODE = os.getenv("SANDBOX_MODE", "true").strip().lower() in ("1", "true", "yes")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()

# PostgreSQL DSN — если задан, используется PostgreSQL. Иначе — SQLite fallback.
# Формат: postgresql://user:pass@host:port/dbname
PG_DSN = os.getenv("PG_DSN")

# Относительный путь зависит от текущего каталога запуска: молча можно получить
# другую БД. Поэтому разрешаем его один раз при старте относительно корня репозитория.
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

# Версия схемы БД (для миграций)
SCHEMA_VERSION = 2