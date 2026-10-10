"""Детектор дроп-аномалий: транзитный поток мелких сумм + обнал + веерные P2P.

Только stdlib. Правила прозрачные (важно для объяснения клиенту и комплаенсу).
Исправления по аудиту T03–T09:
- T03: время нормализуется к UTC (наивное = Europe/Moscow), мусор отсекается
  в метрику вместо 500; смешение TZ больше не падает.
- T08: явный now/analysis_at; операции из будущего исключаются (метрика).
- T07: нулевые суммы не считаются «мелкими входящими» (метрика).
- T04: sim_changed_days_ago=0 считается свежей (None = неизвестно).
- Порядок: в сквозной транзит идут выводы ПОСЛЕ первого входящего.
- Новое устройство — только при реальной истории старше окна.
- Формулировки нейтральные: «возможно ограничение», решение — у банка.

Каждая транзакция — dict:
  {id, user_id, ts (ISO str | datetime), type, amount,
   counterparty, device_id, sim_changed_days_ago (int | None)}
Типы: incoming_p2p | outgoing_p2p | cash_withdraw | purchase | incoming_salary
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from src.policy import DEFAULT_POLICY, PROJECT_TZ, UTC, Policy
from src.reason_codes import (
    FUTURE_EVENT_EXCLUDED,
    HIGH_CASHOUT_RATIO,
    INSUFFICIENT_DATA,
    INVALID_TIMESTAMP_EXCLUDED,
    MULTIPLE_SMALL_INBOUND,
    MULTIPLE_SMALL_INBOUND_SUSPICIOUS,
    NEW_DEVICE,
    NIGHT_ACTIVITY,
    NO_RISK_SIGNAL,
    OUTBOUND_AFTER_INBOUND,
    RAPID_OUTFANOUT,
    SIM_CHANGED_RECENTLY,
    ZERO_AMOUNT_EXCLUDED,
)

# Обратная совместимость имён (раньше были модульными константами).
SMALL_TXN_MAX = DEFAULT_POLICY.small_txn_max
TRANSIT_WINDOW_MIN = DEFAULT_POLICY.transit_window_min
TRANSIT_COUNT_RED = DEFAULT_POLICY.transit_count_red
TRANSIT_COUNT_YELLOW = DEFAULT_POLICY.transit_count_yellow
CASHOUT_RATIO_RED = DEFAULT_POLICY.cashout_ratio
FANOUT_COUNT_RED = DEFAULT_POLICY.fanout_count
NIGHT_HOURS = set(DEFAULT_POLICY.night_hours)


def parse_ts(ts: Any) -> datetime | None:
    """str|datetime -> aware UTC. Наивное = Europe/Moscow. None = не разобрать."""
    if isinstance(ts, datetime):
        dt = ts
    elif isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts)
        except ValueError:
            try:
                dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=PROJECT_TZ)
    return dt.astimezone(UTC)


def _is_fresh_sim(value: Any, max_days: int) -> bool:
    """T04: различаем None (неизвестно) и 0 (смена сегодня). bool не считаем днями."""
    if value is None or isinstance(value, bool):
        return False
    try:
        days = int(value)
    except (TypeError, ValueError):
        return False
    return 0 <= days <= max_days


# Имена правил = ключи score_contributions. Используются для ablation-отчёта
# P1 (правило выключается по одному); по умолчанию включены все.
RULE_KEYS = (
    'multiple_small_inbound',
    'large_outbound_after_inbound',
    'cashout_ratio',
    'fanout_transfers',
    'night_activity',
    'sim_changed_recently',
    'device_novelty_with_baseline',
)


def analyze_transactions(
    transactions: list[dict[str, Any]],
    now: datetime | str | None = None,
    policy: Policy = DEFAULT_POLICY,
    disabled_rules: frozenset[str] | set[str] | None = None,
) -> dict[str, Any]:
    """Главная функция. Возвращает {score 0-100, level, reasons[], metrics{}}.

    disabled_rules используется только для ablation-отчёта P1: позволяет
    выключить одно правило и посмотреть, что оно добавляло. Пустое значение —
    обычное поведение, версии правил не меняются.
    """
    disabled = frozenset(disabled_rules or ())
    unknown = disabled - set(RULE_KEYS)
    if unknown:
        raise ValueError(f"unknown rule(s) for ablation: {sorted(unknown)}")
    parsed: list[tuple[datetime, dict[str, Any]]] = []
    bad_ts = 0
    for t in transactions:
        dt = parse_ts(t.get("ts"))
        if dt is None:
            bad_ts += 1
            continue
        parsed.append((dt, t))
    parsed.sort(key=lambda p: p[0])

    reasons: list[str] = []
    reason_codes: list[str] = []  # машиночитаемое отражение тех же правил; score не меняет
    metrics: dict[str, Any] = {"rules_version": policy.version, "score_contributions": {}, "disabled_rules": sorted(disabled)}
    fired = False  # сработало ли хоть одно скоримое правило

    if bad_ts:
        metrics["excluded_bad_ts"] = bad_ts
        reason_codes.append(INVALID_TIMESTAMP_EXCLUDED)
    if not parsed:
        return {"score": 0, "level": "GREEN", "reasons": ["Нет транзакций для анализа."],
                "reason_codes": [INSUFFICIENT_DATA], "metrics": metrics}

    if now is None:
        now_dt = parsed[-1][0]
    else:
        now_dt = parse_ts(now) or parsed[-1][0]

    # T08: будущее относительно точки анализа — не анализируем, а показываем.
    future = [(dt, t) for dt, t in parsed if dt > now_dt]
    txns = [(dt, t) for dt, t in parsed if dt <= now_dt]
    metrics["excluded_future_count"] = len(future)
    if future:
        reasons.append(f"ℹ️ Операций с датой позже точки анализа ({len(future)} шт.) исключено — они не учитывались.")
        reason_codes.append(FUTURE_EVENT_EXCLUDED)

    if not txns:
        return {"score": 0, "level": "GREEN", "reasons": reasons or ["Нет транзакций для анализа."],
                "reason_codes": reason_codes + [INSUFFICIENT_DATA], "metrics": metrics}

    score = 0
    window_start = now_dt - timedelta(minutes=policy.transit_window_min)
    recent = [(dt, t) for dt, t in txns if dt >= window_start]

    def amt(t: dict[str, Any]) -> float:
        try:
            return float(t.get("amount", 0))
        except (TypeError, ValueError):
            return 0.0

    # 1. Транзитный поток (T07: нулевые суммы не считаются переводами).
    small_in = [(dt, t) for dt, t in recent if t.get("type") == "incoming_p2p" and 0 < amt(t) <= policy.small_txn_max]
    zero_n = sum(1 for _, t in recent if t.get("type") in ("incoming_p2p", "outgoing_p2p") and amt(t) <= 0)
    metrics["excluded_zero_count"] = zero_n
    if zero_n:
        reason_codes.append(ZERO_AMOUNT_EXCLUDED)
    senders = {str(t.get("counterparty", "?")) for _, t in small_in}
    metrics["small_incoming_60m_count"] = len(small_in)
    metrics["small_incoming_60m_senders"] = len(senders)
    metrics["small_incoming_60m_sum"] = round(sum(amt(t) for _, t in small_in), 2)

    if 'multiple_small_inbound' not in disabled and len(small_in) >= policy.transit_count_red and len(senders) >= policy.transit_senders_red:
        score += 45
        metrics["score_contributions"]["multiple_small_inbound"] = 45
        fired = True
        reasons.append(
            f"🔴 Транзитный поток: {len(small_in)} мелких входящих от {len(senders)} разных отправителей "
            f"за {policy.transit_window_min} мин на {metrics['small_incoming_60m_sum']} ₽ — похоже на почерк вербовщика в дропы."
        )
        reason_codes.append(MULTIPLE_SMALL_INBOUND)
    elif 'multiple_small_inbound' not in disabled and len(small_in) >= policy.transit_count_yellow and len(senders) >= policy.transit_senders_yellow:
        score += 25
        metrics["score_contributions"]["multiple_small_inbound"] = 25
        fired = True
        reasons.append(
            f"🟡 Подозрительный приток: {len(small_in)} мелких входящих от {len(senders)} отправителей за час. "
            "Если деньги просят переслать дальше — это может быть вербовка."
        )
        reason_codes.append(MULTIPLE_SMALL_INBOUND_SUSPICIOUS)

    # 2. Сквозной транзит: выводы ПОСЛЕ первого мелкого входящего в окне.
    if small_in:
        first_in = min(dt for dt, _ in small_in)
        out_recent = [(dt, t) for dt, t in recent if t.get("type") in ("outgoing_p2p", "cash_withdraw") and dt >= first_in]
        out_sum = sum(amt(t) for _, t in out_recent)
        in_sum = metrics["small_incoming_60m_sum"]
        if in_sum > 0 and out_sum > 0:
            flow_ratio = out_sum / in_sum
            metrics["flow_through_ratio_60m"] = round(flow_ratio, 2)
            if 'large_outbound_after_inbound' not in disabled and flow_ratio >= policy.flow_ratio and len(small_in) >= 3:
                score += 25
                metrics["score_contributions"]["large_outbound_after_inbound"] = 25
                fired = True
                reasons.append(
                    f"🔴 Сквозной транзит: после поступлений выведено {out_sum:.0f} ₽ из {in_sum:.0f} ₽ "
                    f"({flow_ratio:.0%}) за час. Возможно ограничение операций по 115-ФЗ — решение принимает банк."
                )
                reason_codes.append(OUTBOUND_AFTER_INBOUND)

    # 3. Обнал после входящих за 24ч.
    day_start = now_dt - timedelta(hours=policy.cashout_window_h)
    day = [(dt, t) for dt, t in txns if dt >= day_start]
    day_in = sum(amt(t) for _, t in day if t.get("type") in ("incoming_p2p", "incoming_salary") and amt(t) > 0)
    day_cash = sum(amt(t) for _, t in day if t.get("type") == "cash_withdraw" and amt(t) > 0)
    metrics["incoming_24h"] = round(day_in, 2)
    metrics["cash_24h"] = round(day_cash, 2)
    if 'cashout_ratio' not in disabled and day_in > 0 and (day_cash / day_in) >= policy.cashout_ratio and day_in >= policy.cashout_min_in:
        score += 25
        metrics["score_contributions"]["cashout_ratio"] = 25
        fired = True
        reasons.append(
            f"🔴 Обнал: снято наличными {day_cash:.0f} ₽ из {day_in:.0f} ₽ входящих за 24ч "
            f"({day_cash / day_in:.0%}) — похоже на финал дроп-схемы."
        )
        reason_codes.append(HIGH_CASHOUT_RATIO)

    # 4. Веерные исходящие.
    receivers = Counter(str(t.get("counterparty", "?")) for _, t in recent if t.get("type") == "outgoing_p2p" and amt(t) > 0)
    metrics["fanout_60m_receivers"] = len(receivers)
    if 'fanout_transfers' not in disabled and len(receivers) >= policy.fanout_count:
        score += 25
        metrics["score_contributions"]["fanout_transfers"] = 25
        fired = True
        reasons.append(
            f"🔴 Веерная рассылка: {len(receivers)} разных получателей за час — похоже на распыление чужих денег."
        )
        reason_codes.append(RAPID_OUTFANOUT)

    # 5. Ночная активность.
    night_n = sum(1 for dt, _ in recent if dt.astimezone(PROJECT_TZ).hour in policy.night_hours)
    metrics["night_60m_count"] = night_n
    if 'night_activity' not in disabled and night_n >= 3:
        score += 10
        metrics["score_contributions"]["night_activity"] = 10
        fired = True
        reasons.append(f"🟡 Ночная активность: {night_n} операций между 00:00–06:00 по Москве — нетипичное время.")
        reason_codes.append(NIGHT_ACTIVITY)

    # 6. Свежая смена SIM + всплеск (T04: 0 дней = сегодня = свежая).
    sim_fresh = any(_is_fresh_sim(t.get("sim_changed_days_ago"), policy.sim_fresh_days) for _, t in recent)
    metrics["sim_changed_recently"] = sim_fresh
    if 'sim_changed_recently' not in disabled and sim_fresh and (len(small_in) >= 2 or len(receivers) >= 2):
        score += 15
        metrics["score_contributions"]["sim_changed_recently"] = 15
        fired = True
        reasons.append(
            f"🔴 Смена SIM/устройства за последние {policy.sim_fresh_days} дня + всплеск переводов — "
            "возможен перехват SMS-кодов. Проверьте номер в учебном тренажёре смены номера."
        )
        reason_codes.append(SIM_CHANGED_RECENTLY)

    # 7. Новое устройство — только если есть история старше окна.
    history = [(dt, t) for dt, t in txns if dt < window_start]
    if history and len(txns) >= 4:
        metrics["device_baseline"] = True
        old_devices = {str(t.get("device_id", "")) for _, t in history}
        new_devices = {str(t.get("device_id", "")) for _, t in recent} - old_devices - {""}
        if 'device_novelty_with_baseline' not in disabled and new_devices and len(recent) >= 3:
            score += 10
            metrics["score_contributions"]["device_novelty_with_baseline"] = 10
            fired = True
            reasons.append("🟡 Новое устройство + активность — убедитесь, что это вы.")
            reason_codes.append(NEW_DEVICE)
    else:
        metrics["device_baseline"] = bool(history)

    score = min(100, score)
    level = "RED" if score >= policy.score_red else ("YELLOW" if score >= policy.score_yellow else "GREEN")
    if not fired:
        reasons.append("✅ Всё спокойно: транзитных потоков и веерных рассылок не найдено.")
        reason_codes.append(NO_RISK_SIGNAL)

    metrics["score"] = score
    metrics["level"] = level
    metrics["analyzed"] = len(txns)
    return {"score": score, "level": level, "reasons": reasons, "reason_codes": reason_codes,
            "metrics": metrics}


def quick_check(transactions: list[dict[str, Any]]) -> tuple[str, int, list[str]]:
    """Короткий хелпер для демо/квиза: (level, score, reasons)."""
    r = analyze_transactions(transactions)
    return r["level"], r["score"], r["reasons"]
