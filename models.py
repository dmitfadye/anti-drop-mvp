"""Pydantic v2-схемы API Анти-Дроп. Валидация границы вместо ручных проверок."""
from typing import Literal

from pydantic import BaseModel, Field

TxnType = Literal["incoming_p2p", "outgoing_p2p", "cash_withdraw", "purchase", "incoming_salary"]
Level = Literal["GREEN", "YELLOW", "RED"]


class Transaction(BaseModel):
    id: str = "0"
    user_id: str = "anon"
    ts: str = Field(examples=["2026-10-07 14:02:00"], description="Дата-время операции, ISO-формат")
    type: TxnType = "purchase"
    amount: float = Field(ge=0, examples=[3000])
    counterparty: str = ""
    device_id: str = ""
    sim_changed_days_ago: int = 999


class AnalyzeRequest(BaseModel):
    transactions: list[Transaction] = Field(max_length=5000)
    lang: str = Field(default="ru", description="Код языка Стоп-Дроп алерта: ru/en/uz/tg/ky/zh/ar")


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
    message: str
    details: list[QuizDetail]


class SimChangeRequest(BaseModel):
    old_phone: str
    new_phone: str
    otp_ok_old: bool = False
    otp_ok_new: bool = False


class SimChangeResponse(BaseModel):
    ok: bool
    message: str = ""
    errors: list[str] = []
    new_phone: str = ""
    cooldown_until: str = ""
    limits: dict = {}
    checklist: list[str] = []
