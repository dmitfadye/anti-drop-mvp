"""Единый error envelope: machine-readable код + текст + request_id.

Причина: «голый» 422 от Pydantic не объясняет клиенту, что именно сломалось,
и не даёт связать ошибку с логами. Все ошибки API проходят через ApiError.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    field: str | None = None
    message: str | None = None


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    request_id: str
    field: str | None = None
    details: list[ErrorDetail] = Field(default_factory=list)


class ApiError(Exception):
    """Ожидаемая ошибка API. Трассировку наружу не отдаём."""

    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        field: str | None = None,
        details: list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.field = field
        self.details = details or []
        self.headers = headers or {}


def error_body(request_id: str, error: ApiError) -> dict:
    return ErrorResponse(
        error_code=error.error_code,
        message=error.message,
        request_id=request_id,
        field=error.field,
        details=error.details,
    ).model_dump(exclude_none=True)


# Роутерные ошибки приходят из Starlette с generic-текстом; конкретный код
# позволяет клиенту отличить «нет такого пути» от «метод не поддерживается».
ROUTER_ERROR_CODES = {
    404: ("NOT_FOUND", "Запрошенный ресурс не найден."),
    405: ("METHOD_NOT_ALLOWED", "Метод не поддерживается для этого ресурса."),
}


def router_error(status_code: int, detail: object = None) -> ApiError:
    """Собирает ApiError для HTTPException, поднятого роутером Starlette."""
    code, message = ROUTER_ERROR_CODES.get(status_code, ("HTTP_ERROR", None))
    if message is None:
        text = str(detail) if detail else "Ошибка запроса."
        message = text if text.strip().lower() != "internal server error" else "Ошибка запроса."
    if isinstance(detail, dict) and "error_code" in detail:
        code = detail["error_code"]
        message = detail.get("message", message)
    return ApiError(status_code, code, message)