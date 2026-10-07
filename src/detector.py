"""Детектор дроп-аномалий: транзитный поток мелких сумм + обнал + веерные P2P.

Только stdlib. Правила прозрачные (важно для объяснения клиенту и комплаенсу).
Каждая транзакция — dict:
  {id, user_id, ts (ISO str), type, amount, counterparty, device_id, sim_changed_days_ago}
Типы: incoming_p2p | outgoing_p2p | cash_withdraw | purchase | incoming_salary
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any

SMALL_TXN_MAX = 5000      # «мелкая сумма» для транзита, ₽
TRANSIT_WINDOW_MIN = 60   # окно транзита
TRANSIT_COUNT_RED = 5     # столько разных отправителей мелких входящих за окно = RED
TRANSIT_COUNT_YELLOW = 3
CASHOUT_RATIO_RED = 0.8   # доля обнала от входящих за 24ч
FANOUT_COUNT_RED = 4      # столько разных получателей исходящих за 60 мин = веер
NIGHT_HOURS = set(range(0, 6))  # 00:00-05:59


def parse_ts(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")


def analyze_transactions(transactions: list[dict[str, Any]], now: datetime | None = None) -> dict[str, Any]:
    """Главная функция. Возвращает {score 0-100, level, reasons[], metrics{}}."""
    txns = sorted(transactions, key=lambda t: parse_ts(str(t.get("ts", ""))))
    now = now or (parse_ts(str(txns[-1]["ts"])) if txns else datetime.now())

    reasons: list[str] = []
    score = 0
    metrics: dict[str, Any] = {}

    if not txns:
        return {"score": 0, "level": "GREEN", "reasons": ["Нет транзакций для анализа."], "metrics": metrics}

    window_start = now - timedelta(minutes=TRANSIT_WINDOW_MIN)
    recent = [t for t in txns if parse_ts(str(t["ts"])) >= window_start]

    # 1. Транзитный поток: мелкие входящие от разных отправителей за 60 мин
    small_in = [t for t in recent if t.get("type") == "incoming_p2p" and float(t.get("amount", 0)) <= SMALL_TXN_MAX]
    senders = {str(t.get("counterparty", "?")) for t in small_in}
    metrics["small_incoming_60m_count"] = len(small_in)
    metrics["small_incoming_60m_senders"] = len(senders)
    metrics["small_incoming_60m_sum"] = round(sum(float(t.get("amount", 0)) for t in small_in), 2)

    if len(small_in) >= TRANSIT_COUNT_RED and len(senders) >= 3:
        score += 45
        reasons.append(
            f"🔴 Транзитный поток: {len(small_in)} мелких входящих от {len(senders)} разных отправителей "
            f"за {TRANSIT_WINDOW_MIN} мин на {metrics['small_incoming_60m_sum']} ₽ — классический почерк вербовщика в дропы."
        )
    elif len(small_in) >= TRANSIT_COUNT_YELLOW and len(senders) >= 2:
        score += 25
        reasons.append(
            f"🟡 Подозрительный приток: {len(small_in)} мелких входящих от {len(senders)} отправителей за час. "
            "Если деньги просят переслать дальше — это вербовка."
        )

    # 2. Сквозной транзит: входящие мелкие + быстрые исходящие/обнал в том же окне
    out_recent = [t for t in recent if t.get("type") in ("outgoing_p2p", "cash_withdraw")]
    out_sum = sum(float(t.get("amount", 0)) for t in out_recent)
    in_sum = metrics["small_incoming_60m_sum"]
    if in_sum > 0 and out_sum > 0:
        flow_ratio = out_sum / in_sum
        metrics["flow_through_ratio_60m"] = round(flow_ratio, 2)
        if flow_ratio >= 0.8 and len(small_in) >= 3:
            score += 25
            reasons.append(
                f"🔴 Сквозной транзит: выведено {out_sum:.0f} ₽ из {in_sum:.0f} ₽ входящих ({flow_ratio:.0%}) "
                "за час. Карту используют как «транзитную» — грозит блокировка по 115-ФЗ."
            )

    # 3. Обнал после входящих за 24ч
    day_start = now - timedelta(hours=24)
    day = [t for t in txns if parse_ts(str(t["ts"])) >= day_start]
    day_in = sum(float(t.get("amount", 0)) for t in day if t.get("type") in ("incoming_p2p", "incoming_salary"))
    day_cash = sum(float(t.get("amount", 0)) for t in day if t.get("type") == "cash_withdraw")
    metrics["incoming_24h"] = round(day_in, 2)
    metrics["cash_24h"] = round(day_cash, 2)
    if day_in > 0 and (day_cash / day_in) >= CASHOUT_RATIO_RED and day_in >= 10000:
        score += 25
        reasons.append(
            f"🔴 Обнал: снято наличными {day_cash:.0f} ₽ из {day_in:.0f} ₽ входящих за 24ч "
            f"({day_cash / day_in:.0%}). Типичный финал дроп-схемы."
        )

    # 4. Веерные исходящие: много разных получателей за 60 мин
    receivers = Counter(str(t.get("counterparty", "?")) for t in recent if t.get("type") == "outgoing_p2p")
    metrics["fanout_60m_receivers"] = len(receivers)
    if len(receivers) >= FANOUT_COUNT_RED:
        score += 25
        reasons.append(
            f"🔴 Веерная рассылка: {len(receivers)} разных получателей за час — распыление украденных денег."
        )

    # 5. Ночная активность
    night_n = sum(1 for t in recent if parse_ts(str(t["ts"])).hour in NIGHT_HOURS)
    metrics["night_60m_count"] = night_n
    if night_n >= 3:
        score += 10
        reasons.append(f"🟡 Ночная активность: {night_n} операций между 00:00–06:00 — нетипично для вас.")

    # 6. Смена SIM/устройства + всплеск
    sim_fresh = any(int(t.get("sim_changed_days_ago", 999) or 999) <= 2 for t in recent)
    metrics["sim_changed_recently"] = sim_fresh
    if sim_fresh and (len(small_in) >= 2 or len(receivers) >= 2):
        score += 15
        reasons.append(
            "🔴 Смена SIM/устройства за последние 2 дня + всплеск переводов — возможен перехват SMS-кодов. "
            "Срочно проверьте номер в разделе «Безопасная смена номера»."
        )

    # 7. Новое устройство (эвристика: device_id, которого не было раньше)
    if len(txns) >= 4:
        old_devices = {str(t.get("device_id", "")) for t in txns[:-len(recent)] or txns[:2]}
        new_devices = {str(t.get("device_id", "")) for t in recent} - old_devices - {""}
        if new_devices and len(recent) >= 3:
            score += 10
            reasons.append(f"🟡 Новое устройство {sorted(new_devices)[0][:8]}… + активность — убедитесь, что это вы.")

    score = min(100, score)
    level = "RED" if score >= 50 else ("YELLOW" if score >= 25 else "GREEN")
    if level == "GREEN" and not reasons:
        reasons.append("✅ Всё спокойно: транзитных потоков и веерных рассылок не найдено.")

    metrics["score"] = score
    metrics["level"] = level
    metrics["analyzed"] = len(txns)
    return {"score": score, "level": level, "reasons": reasons, "metrics": metrics}


def quick_check(transactions: list[dict[str, Any]]) -> tuple[str, int, list[str]]:
    """Короткий хелпер для демо/квиза: (level, score, reasons)."""
    r = analyze_transactions(transactions)
    return r["level"], r["score"], r["reasons"]
