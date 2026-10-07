"""Безопасная смена номера: защита от перехвата SMS-кодов."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

COOLDOWN_HOURS = 24
COOLDOWN_P2P_LIMIT = 5000  # лимит исходящих P2P в кулдаун, ₽

PHONE_RE = re.compile(r"^\+?\d{10,15}$")


def validate_phone(phone: str) -> bool:
    return bool(PHONE_RE.match(phone.strip().replace(" ", "").replace("-", "")))


def start_number_change(old_phone: str, new_phone: str, otp_ok_old: bool, otp_ok_new: bool) -> dict:
    """Пошаговая проверка смены номера. Возвращает статус и ограничения."""
    errors: list[str] = []
    if not validate_phone(old_phone):
        errors.append("Старый номер в неверном формате (пример: +79161234567).")
    if not validate_phone(new_phone):
        errors.append("Новый номер в неверном формате (пример: +79161234567).")
    if old_phone.strip() == new_phone.strip():
        errors.append("Номера совпадают — менять нечего.")
    if not otp_ok_old:
        errors.append("Не подтверждён SMS-код со СТАРОГО номера. Без этого смену запрещаем (защита от угона).")
    if not otp_ok_new:
        errors.append("Не подтверждён SMS-код с НОВОГО номера.")
    if errors:
        return {"ok": False, "errors": errors}

    until = datetime.now() + timedelta(hours=COOLDOWN_HOURS)
    return {
        "ok": True,
        "new_phone": new_phone.strip(),
        "cooldown_until": until.strftime("%Y-%m-%d %H:%M"),
        "limits": {
            "p2p_per_transfer": COOLDOWN_P2P_LIMIT,
            "note": f"24 часа: исходящие P2P до {COOLDOWN_P2P_LIMIT} ₽, смена номера только через поддержку с паспортом.",
        },
        "checklist": [
            "✅ Проверьте, что к старому номеру нет доступа у посторонних",
            "✅ Включите двухфакторную аутентификацию в приложении",
            "✅ Позвоните оператору и запретите перевыпуск SIM без паспорта",
            "✅ Если коды приходят с задержкой — сразу в поддержку",
        ],
        "message": f"Номер изменён на {new_phone.strip()}. Кулдаун до {until.strftime('%d.%m %H:%M')}.",
    }
