"""Многоязычные шаблоны экстренного алерта «Стоп-Дроп».

Идея киллер-фичи: не молча блокируем карту, а объясняем риск
(115-ФЗ, ст. 187 УК РФ) на родном языке + даём CTA в поддержку.
"""
from __future__ import annotations

SUPPORTED_LANGS = {
    "ru": "Русский",
    "en": "English",
    "uz": "O'zbekcha",
    "tg": "Тоҷикӣ",
    "ky": "Кыргызча",
    "zh": "中文",
    "ar": "العربية",
}

_TEMPLATES = {
    "ru": "⛔ ВНИМАНИЕ! Кажется, вашу карту используют мошенники.\nПоступления {in_sum} ₽ от {senders} человек и переводы дальше — это схема «дроп». Вам грозит блокировка по 115-ФЗ и суд по ст. 187 УК РФ (до 6 лет).\nНемедленно: 1) никому не переводите, 2) нажмите «Связаться с поддержкой», 3) не отдавайте карту и коды.",
    "en": "⛔ WARNING! Your card looks like it is being used by scammers.\nIncoming {in_sum} RUB from {senders} people with onward transfers is a classic 'money-mule' scheme. You face a 115-FZ account block and criminal liability under Art. 187 of the Criminal Code (up to 6 years).\nDo this now: 1) stop all transfers, 2) tap 'Contact support', 3) never share your card or codes.",
    "uz": "⛔ DIQQAT! Kartangizdan firibgarlar foydalanayotganga o'xshaydi.\n{senders} kishidan {in_sum} ₽ tushum va mablag'ni nari o'tkazish — bu 'drop' sxemasi. 115-FZ bo'yicha blokirovka va JK 187-moddasi bo'yicha sud (6 yilgacha) tahdidi bor.\nHozir: 1) hech qayerga o'tkazmang, 2) 'Yordam' tugmasini bosing, 3) karta va kodlarni bermang.",
    "tg": "⛔ ДИҚҚАТ! Ба назар мерасад, кортатонро қаллобон истифода доранд.\nАз {senders} нафар {in_sum} ₽ воридот ва интиқоли минбаъда — ин нақшаи «дроп» аст. Ба шумо басташавӣ аз рӯи 115-ФЗ ва ҷавобгарии ҷиноӣ (моддаи 187, то 6 сол) таҳдид мекунад.\nҲозир: 1) интиқол накунед, 2) «Дастгирӣ»-ро пахш кунед, 3) корт ва рамзҳоро надиҳед.",
    "ky": "⛔ КӨҢҮЛ БУРГУЛА! Картаңызды шылуундар пайдаланып жаткандай.\n{senders} кишиден {in_sum} ₽ түшүм жана акчаны ары которуу — бул «дроп» схемасы. 115-ФЗ боюнча бөгөт жана КЖ 187-беренеси боюнча сот (6 жылга чейин) коркунучу бар.\nАзыр: 1) которбоңуз, 2) «Колдоо» баскычын басыңыз, 3) картаны жана коддорду бербеңиз.",
    "zh": "⛔ 注意！您的银行卡疑似被诈骗分子利用。\n来自 {senders} 人的 {in_sum} 卢布入账并继续转出——这是典型的“跑分/卡农”骗局。根据 115-ФЗ 您的账户将被冻结，并可能触犯刑法第187条（最高6年）。\n请立即：1）停止一切转账，2）点击“联系客服”，3）切勿交出银行卡和验证码。",
    "ar": "⛔ تنبيه! يبدو أن المحتالين يستخدمون بطاقتك.\nاستلام {in_sum} روبل من {senders} أشخاص مع تحويلها لاحقًا هو مخطط 'الدروب' الاحتيالي. تواجه حظرًا بموجب القانون 115-FZ ومسؤولية جنائية (المادة 187، حتى 6 سنوات).\nالآن: 1) أوقف كل التحويلات، 2) اضغط 'تواصل مع الدعم'، 3) لا تعطِ بطاقتك أو رموزك لأحد.",
}


def build_stop_drop_alert(lang: str, in_sum: float, senders: int, score: int) -> dict[str, str]:
    """Собрать алерт. Возвращает {lang, lang_name, title, body}."""
    lang = lang if lang in _TEMPLATES else "ru"
    body = _TEMPLATES[lang].format(in_sum=f"{in_sum:,.0f}".replace(",", " "), senders=senders)
    title = {"ru": "🛑 СТОП-ДРОП: срочное предупреждение"}.get(lang, "🛑 STOP-DROP: urgent warning")
    return {"lang": lang, "lang_name": SUPPORTED_LANGS[lang], "title": title, "body": body, "score": str(score)}


def support_script_ru() -> str:
    return (
        "Скрипт поддержки (RU): 1) Успокоить и зафиксировать обращение. "
        "2) Спросить: кто просил принять/переслать деньги? 3) Заблокировать исходящие, "
        "оставить входящие для возврата. 4) Составить объяснение для комплаенс по 115-ФЗ. "
        "5) Направить микро-сторис «Почему нельзя отдавать карту»."
    )
