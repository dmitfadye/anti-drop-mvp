"""Стабильные машиночитаемые коды причин риска.

Коды не зависят от языка, не содержат PII и отражают уже существующие правила
детектора. Добавление кодов НЕ меняет score и level — это отражение правил,
а не новые правила. Score остаётся детерминированной суммой баллов правил
и не является вероятностью мошенничества.
"""
from __future__ import annotations

MULTIPLE_SMALL_INBOUND = "MULTIPLE_SMALL_INBOUND"
MULTIPLE_SMALL_INBOUND_SUSPICIOUS = "MULTIPLE_SMALL_INBOUND_SUSPICIOUS"
OUTBOUND_AFTER_INBOUND = "OUTBOUND_AFTER_INBOUND"
HIGH_CASHOUT_RATIO = "HIGH_CASHOUT_RATIO"
RAPID_OUTFANOUT = "RAPID_OUTFANOUT"
NIGHT_ACTIVITY = "NIGHT_ACTIVITY"
SIM_CHANGED_RECENTLY = "SIM_CHANGED_RECENTLY"
NEW_DEVICE = "NEW_DEVICE"
FUTURE_EVENT_EXCLUDED = "FUTURE_EVENT_EXCLUDED"
INVALID_TIMESTAMP_EXCLUDED = "INVALID_TIMESTAMP_EXCLUDED"
ZERO_AMOUNT_EXCLUDED = "ZERO_AMOUNT_EXCLUDED"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
NO_RISK_SIGNAL = "NO_RISK_SIGNAL"

ALL_CODES = frozenset({
    MULTIPLE_SMALL_INBOUND,
    MULTIPLE_SMALL_INBOUND_SUSPICIOUS,
    OUTBOUND_AFTER_INBOUND,
    HIGH_CASHOUT_RATIO,
    RAPID_OUTFANOUT,
    NIGHT_ACTIVITY,
    SIM_CHANGED_RECENTLY,
    NEW_DEVICE,
    FUTURE_EVENT_EXCLUDED,
    INVALID_TIMESTAMP_EXCLUDED,
    ZERO_AMOUNT_EXCLUDED,
    INSUFFICIENT_DATA,
    NO_RISK_SIGNAL,
})

DESCRIPTIONS = {
    MULTIPLE_SMALL_INBOUND: "Несколько мелких входящих операций от разных отправителей за короткий срок",
    MULTIPLE_SMALL_INBOUND_SUSPICIOUS: "Подозрительный приток мелких входящих операций",
    OUTBOUND_AFTER_INBOUND: "Исходящие переводы после поступлений (сквозной транзит)",
    HIGH_CASHOUT_RATIO: "Высокая доля снятия наличными от поступивших сумм за 24 часа",
    RAPID_OUTFANOUT: "Веерная рассылка исходящих переводов многим получателям",
    NIGHT_ACTIVITY: "Нетипичное время операций",
    SIM_CHANGED_RECENTLY: "Свежая смена SIM/устройства вместе со всплеском операций",
    NEW_DEVICE: "Новое устройство при наличии истории",
    FUTURE_EVENT_EXCLUDED: "Операции позже точки анализа исключены",
    INVALID_TIMESTAMP_EXCLUDED: "Операции с нечитаемой датой исключены",
    ZERO_AMOUNT_EXCLUDED: "Нулевые суммы не учитывались как переводы",
    INSUFFICIENT_DATA: "Недостаточно данных для анализа",
    NO_RISK_SIGNAL: "Скоримые признаки не сработали",
}