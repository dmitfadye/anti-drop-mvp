"""Pydantic v2-схемы API Анти-Дроп. Валидация границы вместо ручных проверок.

Исправления по аудиту:
- T03: ts — настоящий datetime; мусор -> 422, а не 500. Наивные метки считаем
  московскими (Europe/Moscow), внутрь всё приводим к UTC. Смешение TZ нормализуется.
- T05: контракт одного субъекта — смешение user_id отклоняется (422).
- T06: дубликаты id в одном снапшоте отклоняются (422).
- Длина строк ограничена (защита от раздувания тела).
- Деньги: float допустим для классификатора (T19 — не дефект списаний),
  но бесконечности/NaN запрещены.
"""
from datetime import datetime
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.alerts import SUPPORTED_LANGS
from src.config import MAX_CLIENT_COMMENT_LENGTH, MAX_EVALUATION_ID_LENGTH
from src.errors import ApiError
from src.identity import reject_untrusted_body_fields
from src.policy import PROJECT_TZ, UTC
from src.sandbox_cases import CONTACT_REASONS

TxnType = Literal["incoming_p2p", "outgoing_p2p", "cash_withdraw", "purchase", "incoming_salary"]
Level = Literal["GREEN", "YELLOW", "RED"]

# Literal, а не str: OpenAPI показывает перечисление, и неверное значение
# отсекается на границе схемы, а не в коде роута.
ContactReason = Literal[
    "suspicious_transfer_request",
    "unexpected_incoming_funds",
    "asked_to_forward_money",
    "other",
]
LanguageCode = Literal["ru", "en", "uz", "tg", "ky", "zh", "ar"]

ID_PATTERN = r"[A-Za-z0-9._:-]{1,128}"
_ID_RE = re.compile(ID_PATTERN)


def _valid_id(value: str) -> bool:
    # fullmatch, а не match с ^...$: в Python '$' матчится перед завершающим '\n',
    # и ключ вида "abc\n" прошёл бы проверку как "abc".
    return bool(_ID_RE.fullmatch(value))


def _normalize_ts(v: object) -> datetime:
    if isinstance(v, datetime):
        dt = v
    else:
        text = str(v).strip()
        # 'Z' is only understood by fromisoformat from Python 3.11; the project
        # declares 3.10 support, so normalise it here instead of rejecting UTC.
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            raise ValueError("ts: ожидаю ISO дату-время, например '2026-10-07 14:02:00'") from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=PROJECT_TZ)
    return dt.astimezone(UTC)


class Transaction(BaseModel):
    id: str = Field(default="0", max_length=64)
    user_id: str = Field(default="anon", max_length=64)
    ts: datetime = Field(description="ISO дата-время. Наивные метки считаются московским временем.")
    type: TxnType = "purchase"
    amount: float = Field(ge=0, allow_inf_nan=False, examples=[3000])
    counterparty: str = Field(default="", max_length=256)
    device_id: str = Field(default="", max_length=256)
    sim_changed_days_ago: int | None = Field(default=None, ge=0, description="Дней с замены SIM; null = неизвестно")

    @field_validator("ts", mode="before")
    @classmethod
    def _parse_ts(cls, v: object) -> datetime:
        return _normalize_ts(v)


class AnalyzeRequest(BaseModel):
    transactions: list[Transaction] = Field(max_length=5000)
    lang: str = Field(default="ru", min_length=2, max_length=5)
    subject_id: str | None = Field(default=None, max_length=64, description="Проверяемый клиент; чужие user_id отклоняются")
    analysis_at: datetime | None = Field(default=None, description="Точка анализа; операции позже неё исключаются")

    @field_validator("analysis_at", mode="before")
    @classmethod
    def _parse_at(cls, v: object) -> datetime | None:
        return None if v is None else _normalize_ts(v)

    @model_validator(mode="after")
    def _single_subject_no_dupes(self) -> "AnalyzeRequest":
        ids = [t.id for t in self.transactions]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate transaction id: id операций в одном снапшоте должны быть уникальны")
        users = {t.user_id for t in self.transactions}
        if self.subject_id is not None:
            alien = sorted(users - {self.subject_id})
            if alien:
                raise ValueError(f"смешение субъектов: subject_id={self.subject_id!r}, чужие user_id={alien}")
        elif len(users) > 1:
            raise ValueError(f"несколько user_id в одном запросе {sorted(users)}: укажите subject_id")
        return self


class StopDropAlert(BaseModel):
    lang: str
    lang_name: str
    title: str
    body: str
    score: int


class AnalyzeResponse(BaseModel):
    score: int = Field(ge=0, le=100)
    level: Level
    reasons: list[str]
    reason_codes: list[str] = Field(default_factory=list,
                                   description="Машиночитаемые коды тех же причин; score не вероятность.")
    metrics: dict
    alert: StopDropAlert | None = None
    rules_version: str = ""
    evaluation_id: str = Field(default="", description="Ссылка для последующего создания sandbox-кейса.")
    score_interpretation: str = "deterministic_rule_sum_not_probability"


class QuizRequest(BaseModel):
    answers: list[int] = Field(max_length=20, description="Индексы выбранных вариантов по каждому вопросу")


class QuizDetail(BaseModel):
    q: str
    ok: bool
    explain: str


class QuizResponse(BaseModel):
    score: int
    total: int
    passed: bool
    cashback: int
    reward_status: str = "simulated"
    message: str
    details: list[QuizDetail]


class SimChangeRequest(BaseModel):
    old_phone: str = Field(max_length=32)
    new_phone: str = Field(max_length=32)
    otp_ok_old: bool = False
    otp_ok_new: bool = False


class SimChangeResponse(BaseModel):
    ok: bool
    demo: bool = True
    message: str = ""
    errors: list[str] = []
    new_phone: str = ""
    cooldown_until: str = ""
    limits: dict = {}
    checklist: list[str] = []


# Модели CaseCreateRequest/SupportCase удалены вместе с legacy /api/cases (D-7c):
# endpoint отключён (410), и оставшаяся схема только создавала ложное впечатление,
# что в API есть второй рабочий путь создания кейсов.


# ---------------------------------------------------------------------------
# Sandbox cases (MVP). Субъект приходит из доверенного для демо заголовка
# X-Sandbox-Subject, поэтому в теле запроса полей идентичности быть не должно.
# ---------------------------------------------------------------------------


class SandboxCaseCreate(BaseModel):
    # extra="forbid" намеренно: иначе subject_ref в теле был бы молча проигнорирован,
    # и граница доверия осталась бы невидимой (см. src/identity.py).
    model_config = ConfigDict(extra="forbid")

    evaluation_id: str = Field(
        ...,
        min_length=1,
        max_length=MAX_EVALUATION_ID_LENGTH,
        description="Идентификатор risk-решения, к которому относится обращение.",
        examples=["eval-001"],
    )
    selected_language: LanguageCode = Field(
        ..., description="Язык предупреждения и обращения. Список ограничен шаблонами."
    )
    contact_reason: ContactReason = Field(
        ..., description="Причина обращения. Значения ограничены allowlist."
    )
    client_comment: str | None = Field(
        default=None,
        max_length=MAX_CLIENT_COMMENT_LENGTH,
        description="Не сохраняется и не логируется; входит только в payload_hash.",
    )

    @model_validator(mode="before")
    @classmethod
    def _explicit_errors(cls, data: object) -> object:
        """Даём машиночитаемый код ошибки вместо общего VALIDATION_ERROR.

        Pydantic v2 пробрасывает не-ValueError исключения из валидатора, поэтому
        ApiError доходит до нашего обработчика с нужным error_code и полем.
        """
        reject_untrusted_body_fields(data)
        if isinstance(data, dict):
            language = data.get("selected_language")
            if isinstance(language, str) and language not in SUPPORTED_LANGS:
                raise ApiError(422, "UNSUPPORTED_LANGUAGE",
                               "Язык не поддерживается. Доступные: " + ", ".join(sorted(SUPPORTED_LANGS)),
                               field="selected_language")
            evaluation_id = data.get("evaluation_id")
            if isinstance(evaluation_id, str) and not _valid_id(evaluation_id):
                raise ApiError(422, "INVALID_EVALUATION_ID",
                               "evaluation_id: допустимы латинские буквы, цифры и символы . _ - :, длина 1-128.",
                               field="evaluation_id")
        return data

    @field_validator("contact_reason", mode="before")
    @classmethod
    def _check_reason(cls, v: object) -> object:
        if isinstance(v, str) and v not in CONTACT_REASONS:
            raise ApiError(422, "INVALID_CONTACT_REASON",
                           "Причина обращения не поддерживается. Доступные: " + ", ".join(CONTACT_REASONS),
                           field="contact_reason")
        return v

    def normalized(self) -> dict:
        """Каноническое представление для payload_hash."""
        return {
            "evaluation_id": self.evaluation_id,
            "selected_language": self.selected_language,
            "contact_reason": self.contact_reason,
            "client_comment": (self.client_comment or "").strip() or None,
        }


class SandboxCaseResponse(BaseModel):
    case_id: str
    status: str
    created_at: str
    subject_ref: str
    evaluation_id: str
    selected_language: str
    contact_reason: str
    next_step: str = "sandbox_review_pending"
    sandbox: bool = True
    notice: str = Field(description="Явное предупреждение: никаких реальных банковских действий не выполнено.")


class SandboxCaseListResponse(BaseModel):
    items: list[SandboxCaseResponse]
    limit: int
    offset: int
    total_count: int = Field(description="Всего кейсов у субъекта — чтобы UI знал, есть ли ещё страницы.")
