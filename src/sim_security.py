"""Безопасная смена номера: защита от перехвата SMS-кодов."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

COOLDOWN_HOURS = 24
COOLDOWN_P2P_LIMIT = 5000  # лимит исходящих P2P в кулдаун, ₽

PHONE_RE = re.compile(r"^\+?\d{10,15}$")


def canonical_phone(phone: str) -> str:
    """Каноническая форма для сравнения/хранения (T13): без пробелов, дефисов, скобок."""
    p = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if re.fullmatch(r"8\d{10}", p):  # российская «восьмёрка» -> +7
        p = "+7" + p[1:]
    return p


def validate_phone(phone: str) -> bool:
    return bool(PHONE_RE.match(canonical_phone(phone)))


def start_number_change(old_phone: str, new_phone: str, otp_ok_old: bool, otp_ok_new: bool) -> dict:
    """Учебный тренажёр смены номера (T01: это НЕ банковская смена, SMS не отправляется).

    Сравнение — по канонической форме (T13/T16): один номер в разных
    форматах («+7 916...» vs «+7916...») считается совпадением.
    """
    old_c, new_c = canonical_phone(old_phone), canonical_phone(new_phone)
    errors: list[str] = []
    if not validate_phone(old_phone):
        errors.append("Старый номер в неверном формате (пример: +79161234567).")
    if not validate_phone(new_phone):
        errors.append("Новый номер в неверном формате (пример: +79161234567).")
    if old_c == new_c:
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
        "new_phone": new_c,
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
        "message": f"Учебная смена: номер {new_c}. Кулдаун до {until.strftime('%d.%m %H:%M')} (демо, SMS не отправлялись).",
    }
