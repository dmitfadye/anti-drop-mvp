"""Версионированная политика правил детектора.

Пороги отделены от кода: меняются в одном месте, версия уходит в API/метрики.
Наивные метки времени считаем московскими (Europe/Moscow), внутрь — UTC.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from zoneinfo import ZoneInfo

RULES_VERSION = "2026-10-08.p1"
PROJECT_TZ = ZoneInfo("Europe/Moscow")
UTC = timezone.utc


@dataclass(frozen=True)
class Policy:
    version: str = RULES_VERSION
    small_txn_max: float = 5000       # «мелкая сумма» транзита, ₽
    transit_window_min: int = 60      # окно транзита, мин
    transit_count_red: int = 5        # мелких входящих за окно = RED-сигнал
    transit_senders_red: int = 3      # ...от стольких разных отправителей
    transit_count_yellow: int = 3
    transit_senders_yellow: int = 2
    flow_ratio: float = 0.8           # доля быстрого вывода из входящих
    cashout_ratio: float = 0.8        # доля обнала за 24ч
    cashout_min_in: float = 10000     # ...при входящих не меньше, ₽
    cashout_window_h: int = 24
    fanout_count: int = 4             # разных получателей за час = веер
    night_hours: frozenset = frozenset(range(0, 6))
    sim_fresh_days: int = 2           # смена SIM не старше, дней
    score_red: int = 50
    score_yellow: int = 25


DEFAULT_POLICY = Policy()
