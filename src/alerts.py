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

TEMPLATE_VERSION = "warning-templates-2026.10.08.p2"

SUPPORTED_LANGS = {
    "ru": "Русский",
    "en": "English",
    "uz": "O'zbekcha",
    "tg": "Тоҷикӣ",
    "ky": "Кыргызча",
    "zh": "中文",
    "ar": "العربية",
}

# Draft translations; native-speaker and bank review are required before a pilot.
_LEAD = {
    'ru': 'ВНИМАНИЕ! Обнаружены сигналы, которые стоит проверить.',
    'en': 'WARNING! Some activity signals need your attention.',
    'uz': 'DIQQAT! Tekshirish kerak bo‘lgan belgilar aniqlandi.',
    'tg': 'ДИҚҚАТ! Аломатҳое ошкор шуданд, ки бояд санҷида шаванд.',
    'ky': 'КӨҢҮЛ БУРГУЛА! Текшерүүнү талап кылган белгилер аныкталды.',
    'zh': '注意！发现需要核实的交易信号。',
    'ar': 'تنبيه! ظهرت مؤشرات تستحق التحقق.',
}
_TRANSIT = {
    'ru': 'Несколько поступлений: {in_sum} ₽ от {senders} отправителей. Проверьте их назначение.',
    'en': 'Multiple incoming payments: {in_sum} RUB from {senders} senders. Verify their purpose.',
    'uz': '{senders} yuboruvchidan {in_sum} ₽ tushdi. Maqsadini tekshiring.',
    'tg': 'Аз {senders} фиристанда {in_sum} ₽ ворид шуд. Мақсади онҳоро санҷед.',
    'ky': '{senders} жөнөтүүчүдөн {in_sum} ₽ түштү. Максатын текшериңиз.',
    'zh': '收到 {senders} 位付款人共 {in_sum} 卢布，请核实用途。',
    'ar': 'ورد {in_sum} روبل من {senders} مرسلين. تحقق من الغرض.',
}
_GENERIC = {
    'ru': 'Последние операции похожи на рискованную схему по настроенным правилам. Это не доказательство мошенничества.',
    'en': 'Configured rules flagged recent activity for review. This is not proof of fraud.',
    'uz': 'Qoidalar so‘nggi operatsiyalarni tekshirishni tavsiya qiladi. Bu firibgarlik isboti emas.',
    'tg': 'Қоидаҳо санҷиши амалиёти охиринро тавсия медиҳанд. Ин далели қаллобӣ нест.',
    'ky': 'Эрежелер акыркы операцияларды текшерүүнү сунуштайт. Бул алдамчылыктын далили эмес.',
    'zh': '规则提示应核实近期交易，这并非诈骗证据。',
    'ar': 'تشير القواعد إلى ضرورة مراجعة العمليات الأخيرة. هذا ليس دليل احتيال.',
}
_LEGAL = {
    'ru': 'Учебное предупреждение: банк не уведомлён, операции не блокировались.',
    'en': 'Sandbox warning: the bank was not contacted and no transactions were blocked.',
    'uz': 'O‘quv ogohlantirishi: bankka xabar yuborilmadi, operatsiyalar bloklanmadi.',
    'tg': 'Огоҳии таълимӣ: бонк огоҳ нашудааст, амалиёт баста нашудааст.',
    'ky': 'Окуу эскертүүсү: банкка билдирүү жөнөтүлгөн жок, операциялар бөгөттөлгөн жок.',
    'zh': '教学演示：未通知银行，也未拦截任何交易。',
    'ar': 'تنبيه تجريبي: لم يُتصل بالبنك ولم تُحظر أي عملية.',
}
_CTA = {
    'ru': 'Если вас торопят: проверьте просьбу другим способом, не сообщайте коды. При сомнениях свяжитесь с банком через официальный канал. Здесь можно зарегистрировать только тестовое обращение.',
    'en': 'If pressured, verify the request independently and never share codes. Contact your bank through its official channel. This app creates test cases only.',
    'uz': 'Shoshiltirishsa, so‘rovni boshqa yo‘l bilan tekshiring, kodlarni bermang. Bankning rasmiy kanaliga murojaat qiling. Bu yerda faqat test murojaati yaratiladi.',
    'tg': 'Агар шитобонанд, дархостро бо роҳи дигар санҷед, рамзҳоро надиҳед. Бо канали расмии бонк тамос гиред. Ин ҷо танҳо муроҷиати санҷишӣ сохта мешавад.',
    'ky': 'Шаштырышса, өтүнүчтү башка жол менен текшериңиз, коддорду бербеңиз. Банктын расмий каналына кайрылыңыз. Бул жерде тесттик кайрылуу гана түзүлөт.',
    'zh': '如被催促，请通过其他渠道核实，切勿透露验证码。有疑问请联系银行官方渠道。此处仅创建测试工单。',
    'ar': 'إذا تعرضت للضغط فتحقق بطريقة مستقلة ولا تشارك الرموز. اتصل بالقناة الرسمية للبنك. هنا تُنشأ طلبات تجريبية فقط.',
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
