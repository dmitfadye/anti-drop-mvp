"""CLI-демо для жюри: норма vs дроп-атака. Запуск: python3 src/demo.py"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.alerts import build_stop_drop_alert
from src.detector import analyze_transactions
from src.quiz import STORIES, check_quiz


def load_csv(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def show(name: str, txns: list[dict], lang: str = "ru"):
    print(f"\n{'=' * 60}\n📂 Сценарий: {name} ({len(txns)} операций)")
    res = analyze_transactions(txns)
    print(f"Скоринг: {res['score']}/100  Уровень: {res['level']}")
    for r in res["reasons"]:
        print("  •", r)
    if res["level"] == "RED":
        m = res["metrics"]
        alert = build_stop_drop_alert(lang, m.get("small_incoming_60m_sum", 0), m.get("small_incoming_60m_senders", 0), res["score"])
        print(f"\n{alert['title']} [{alert['lang_name']}]\n{alert['body']}")
    print("Метрики:", res["metrics"])


def main():
    base = Path(__file__).resolve().parent.parent
    show("НОРМА (зарплата + покупки)", load_csv(base / "data/sample_normal.csv"))
    show("АТАКА ВЕРБОВЩИКА (транзит)", load_csv(base / "data/sample_drop_attack.csv"), lang="uz")

    print(f"\n{'=' * 60}\n📚 Микро-сторис онбординга:")
    for s in STORIES:
        print(f"  {s['emoji']} {s['title']}: {s['text'][:80]}...")

    print("\n📝 Квиз (идеальные ответы [1,1,1,1,0]):")
    print(check_quiz([1, 1, 1, 1, 0])["message"])


if __name__ == "__main__":
    main()
