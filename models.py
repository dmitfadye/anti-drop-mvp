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
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from src.policy import PROJECT_TZ, UTC

TxnType = Literal["incoming_p2p", "outgoing_p2p", "cash_withdraw", "purchase", "incoming_salary"]
Level = Literal["GREEN", "YELLOW", "RED"]


def _normalize_ts(v: object) -> datetime:
    if isinstance(v, datetime):
        dt = v
    else:
        try:
            dt = datetime.fromisoformat(str(v))
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
    metrics: dict
    alert: StopDropAlert | None = None
    rules_version: str = ""


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


class CaseCreateRequest(BaseModel):
    summary: str = Field(max_length=500, description="Краткое описание ситуации со слов клиента")
    lang: str = Field(default="ru", min_length=2, max_length=5)
    score: int = Field(default=0, ge=0, le=100)
    idempotency_key: str | None = Field(default=None, max_length=128)


class SupportCase(BaseModel):
    case_id: str
    status: str = "open-sandbox"
    demo: bool = True
    created_at: str = ""
    summary: str = ""
    lang: str = "ru"
    score: int = 0
    note: str = ""
