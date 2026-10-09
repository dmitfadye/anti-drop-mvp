"""Доверенный для демо субъект из заголовка `X-Sandbox-Subject`.

НЕ production auth. В реальном контуре субъект обязан приходить из банковского
gateway/SSO/mTLS. Здесь заголовок — сознательная sandbox-подмена, помеченная
в документации, чтобы граница доверия была явной.
"""
from __future__ import annotations

import hashlib
import re

from fastapi import Header, Request

from src.config import MAX_SUBJECT_LENGTH
from src.errors import ApiError

HEADER_NAME = "X-Sandbox-Subject"

SUBJECT_PATTERN = r"[A-Za-z0-9._:-]{1,128}"

# Принимаем сырой заголовок, чтобы 404/405 и прочие ошибки тоже попадали в OpenAPI.
SUBJECT_DESCRIPTION = (
    "TEST-ONLY sandbox identity. Не является production auth. "
    "В реальном пилоте субъект должен приходить из банковского gateway/SSO/mTLS, "
    "а не из заголовка браузера."
)


def is_valid_subject(value: str) -> bool:
    if not value or len(value) > MAX_SUBJECT_LENGTH:
        return False
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        return False
    return bool(re.fullmatch(SUBJECT_PATTERN, value))


def _from_header(raw: str | None) -> str:
    if raw is None or not raw.strip():
        raise ApiError(
            401,
            "SUBJECT_REQUIRED",
            f"Не передан заголовок {HEADER_NAME} (sandbox-идентификация для демо, не production auth).",
            field=HEADER_NAME,
        )
    subject = raw.strip()
    if not is_valid_subject(subject):
        raise ApiError(
            401,
            "INVALID_SUBJECT_HEADER",
            "Недопустимое значение заголовка субъекта: допустимы латинские буквы, цифры и символы . _ - : , длина 1-128.",
            field=HEADER_NAME,
        )
    return subject


def get_sandbox_subject(
    request: Request,
    x_sandbox_subject: str | None = Header(
        default=None, alias=HEADER_NAME, description=SUBJECT_DESCRIPTION, examples=["demo-user-1"]
    ),
) -> str:
    """Dependency FastAPI. Объявлен и через Request, и через Header:
    Request читает фактическое значение, Header — чтобы параметр был виден в OpenAPI."""
    header_value = request.headers.get(HEADER_NAME)
    return _from_header(header_value if header_value is not None else x_sandbox_subject)


# Поля, которые клиент не должен присылать: субъект и идентификаторы устройства
# определяются доверенным контекстом, иначе границу доверия можно обойти телом запроса.
FORBIDDEN_BODY_FIELDS = frozenset({
    "subject", "subject_ref", "user_id", "client_id", "customer_id",
    "phone", "msisdn", "device_id", "device_ref",
    "otp", "passport", "card", "pan",
})


def find_forbidden_fields(body: object) -> list[str]:
    """Регистронезависимая проверка: Subject и User_Id должны ловиться одинаково."""
    if not isinstance(body, dict):
        return []
    return sorted(k for k in body if isinstance(k, str) and k.strip().lower() in FORBIDDEN_BODY_FIELDS)


def reject_untrusted_body_fields(body: object) -> None:
    """Явно отклонить попытку передать субъекта или идентификаторы в теле запроса.

    Молча игнорировать такое поле нельзя: иначе граница доверия остаётся
    невидимой и её можно случайно обойти в следующей версии кода.
    """
    present = find_forbidden_fields(body)
    if present:
        raise ApiError(
            422,
            "UNTRUSTED_SUBJECT_FIELD",
            "Поля идентичности нельзя передавать в теле запроса: субъект и устройство "
            "определяются сервером из доверенного контекста.",
            field=present[0],
        )


def subject_hash_prefix(subject_ref: str) -> str:
    """Короткий необратимый префикс для логов — без возможности восстановить subject."""
    return hashlib.sha256(subject_ref.encode("utf-8")).hexdigest()[:8]