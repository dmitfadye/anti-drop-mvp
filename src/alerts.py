"""Многоязычные шаблоны экстренного алерта «Стоп-Дроп».

Исправления по аудиту:
- T21: нейтральный язык риска. Не утверждаем вину, автоматическую блокировку
  и конкретный срок: «возможны ограничение операций и проверка», решение — у банка.
  Юридические формулировки требуют review банка перед пилотом.
- Стратегия аудита: RED без транзитного потока получает общее объяснение,
  а не ложный текст «поступления X ₽ от 0 человек».

Идея киллер-фичи: не молча блокируем карту, а объясняем риск
на родном языке + даём CTA в поддержку.
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

_LEAD = {
    "ru": "⛔ ВНИМАНИЕ! Похоже, вашу карту используют мошенники.",
    "en": "⛔ WARNING! Your card appears to be used by scammers.",
    "uz": "⛔ DIQQAT! Kartangizdan firibgarlar foydalanayotganga o'xshaydi.",
    "tg": "⛔ ДИҚҚАТ! Ба назар мерасад, кортатонро қаллобон истифода доранд.",
    "ky": "⛔ КӨҢҮЛ БУРГУЛА! Картаңызды шылуундар пайдаланып жаткандай.",
    "zh": "⛔ 注意！您的银行卡疑似被诈骗分子利用。",
    "ar": "⛔ تنبيه! يبدو أن المحتالين يستخدمون بطاقتك.",
}

_TRANSIT = {
    "ru": "Поступления {in_sum} ₽ от {senders} человек с переводом дальше похожи на схему «дроп».",
    "en": "Incoming {in_sum} RUB from {senders} people with onward transfers looks like a 'money-mule' pattern.",
    "uz": "{senders} kishidan {in_sum} ₽ tushum va mablag'ning nari o'tkazilishi 'drop' sxemasiga o'xshaydi.",
    "tg": "Аз {senders} нафар {in_sum} ₽ воридот ва интиқоли минбаъда ба нақшаи «дроп» монанд аст.",
    "ky": "{senders} кишиден {in_sum} ₽ түшүм жана акчанын ары кетиши «дроп» схемасына окшош.",
    "zh": "来自 {senders} 人的 {in_sum} 卢布入账并继续转出，疑似“跑分”模式。",
    "ar": "استلام {in_sum} روبل من {senders} أشخاص مع تحويلها لاحقًا يشبه مخطط 'الدروب'.",
}

_GENERIC = {
    "ru": "Последние операции похожи на рискованную схему: деньги приходят и быстро уходят дальше.",
    "en": "Recent activity looks like a risky pattern: money arrives and quickly leaves.",
    "uz": "So'nggi operatsiyalar xavfli sxemaga o'xshaydi: pul keladi va tezda nari o'tadi.",
    "tg": "Амалиётҳои охирин ба нақшаи хатарнок монанданд: пул меояд ва зуд меравад.",
    "ky": "Акыркы операциялар кооптуу схемага окшош: акча келет жана бат эле кетет.",
    "zh": "近期交易疑似存在风险：资金快进快出。",
    "ar": "العمليات الأخيرة تشبه مخططًا محفوفًا بالمخاطر: أموال تصل وتغادر بسرعة.",
}

_LEGAL = {
    "ru": "Возможны ограничение операций по 115-ФЗ и проверка по ст. 187 УК РФ. Точное решение принимает банк.",
    "en": "Account restrictions under 115-FZ and a review under Art. 187 of the Criminal Code are possible. The bank makes the final decision.",
    "uz": "115-FZ bo'yicha cheklovlar va JK 187-moddasi bo'yicha tekshiruv bo'lishi mumkin. Yakuniy qarorni bank qabul qiladi.",
    "tg": "Маҳдудиятҳо аз рӯи 115-ФЗ ва санҷиш аз рӯи моддаи 187-и КҶ имконпазир аст. Қарори ниҳоӣ бо бонк аст.",
    "ky": "115-ФЗ боюнча чектөөлөр жана КЖ 187-беренеси боюнча текшерүү болушу мүмкүн. Акыркы чечимди банк кабыл алат.",
    "zh": "账户可能依据 115-ФЗ 被限制，并可能接受刑法第187条审查，最终由银行决定。",
    "ar": "قد تُفرض قيود بموجب القانون 115-FZ ومراجعة بموجب المادة 187. القرار النهائي للبنك.",
}

_CTA = {
    "ru": "Сейчас: 1) никому не переводите, 2) создайте обращение кнопкой ниже, 3) не отдавайте карту и коды.",
    "en": "Right now: 1) stop all transfers, 2) open a support case with the button below, 3) never share your card or codes.",
    "uz": "Hozir: 1) hech qayerga o'tkazmang, 2) pastdagi tugma orqali murojaat oching, 3) karta va kodlarni bermang.",
    "tg": "Ҳозир: 1) интиқол накунед, 2) бо тугмаи зер муроҷиат кушоед, 3) корт ва рамзҳоро надиҳед.",
    "ky": "Азыр: 1) эч жакка которбоңуз, 2) төмөндөгү баскыч менен кайрылуу ачыңыз, 3) картаны жана коддорду бербеңиз.",
    "zh": "请立即：1）停止一切转账，2）点击下方按钮创建工单，3）切勿交出银行卡和验证码。",
    "ar": "الآن: 1) أوقف كل التحويلات، 2) افتح تذكرة دعم بالزر أدناه، 3) لا تعطِ بطاقتك أو رموزك لأحد.",
}

_TITLES = {"ru": "🛑 СТОП-ДРОП: предупреждение о риске"}


def build_stop_drop_alert(lang: str, in_sum: float, senders: int, score: int) -> dict[str, str]:
    """Собрать алерт. Без транзита — общее объяснение, а не «0 ₽ от 0 человек»."""
    lang = lang if lang in _LEAD else "ru"
    if senders >= 2 and in_sum > 0:
        fact = _TRANSIT[lang].format(in_sum=f"{in_sum:,.0f}".replace(",", " "), senders=senders)
    else:
        fact = _GENERIC[lang]
    body = f"{_LEAD[lang]}\n{fact}\n{_LEGAL[lang]}\n{_CTA[lang]}"
    return {
        "lang": lang,
        "lang_name": SUPPORTED_LANGS[lang],
        "title": _TITLES.get(lang, "🛑 STOP-DROP: risk warning"),
        "body": body,
        "score": str(score),
    }


def support_script_ru() -> str:
    return (
        "Скрипт поддержки (RU, учебный): 1) Успокоить и зафиксировать обращение. "
        "2) Спросить: кто просил принять/переслать деньги? 3) Подсказать официальный канал банка, "
        "не обещать блокировку/разблокировку от имени банка. 4) Направить микро-сторис "
        "«Почему нельзя отдавать карту». Точные формулировки — по согласованию с банком."
    )
