"""Тесты FastAPI-слоя. Запуск из корня проекта:
.venv/bin/python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from main import app
from src.db import get_db, reset_init_state_for_tests

client = TestClient(app)

# Setup test user in database
reset_init_state_for_tests()
for db in get_db():
    db.execute("INSERT OR REPLACE INTO users (user_id, phone, created_at) VALUES ('test_user', '+79160000001', datetime('now'))")
    db.commit()
    break

HEADERS = {"X-Sandbox-Subject": "test_user"}


ATTACK = [
    {"id": str(i), "user_id": "u777", "ts": ts, "type": tp, "amount": a,
     "counterparty": cp, "device_id": "dev_X", "sim_changed_days_ago": 1}
    for i, (ts, tp, a, cp) in enumerate([
        ("2026-10-07 14:02:00", "incoming_p2p", 3000, "s1"),
        ("2026-10-07 14:07:00", "incoming_p2p", 2500, "s2"),
        ("2026-10-07 14:12:00", "incoming_p2p", 4000, "s3"),
        ("2026-10-07 14:20:00", "incoming_p2p", 1800, "s4"),
        ("2026-10-07 14:25:00", "incoming_p2p", 3500, "s5"),
        ("2026-10-07 14:40:00", "outgoing_p2p", 9000, "mule"),
    ])
]


class TestAPI(unittest.TestCase):
    def test_health(self):
        self.assertEqual(client.get("/api/health").json()["status"], "ok")

    def test_index_serves_tailwind_page(self):
        r = client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("/static/tailwind.css", r.text)
        self.assertIn("Анти-Дроп", r.text)

    def test_content_hides_answers(self):
        c = client.get("/api/content").json()
        self.assertEqual(len(c["quiz"]), 5)
        self.assertNotIn("correct", str(c))

    def test_analyze_red_with_alert(self):
        r = client.post("/api/analyze", json={"transactions": ATTACK, "lang": "tg"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["level"], "RED")
        self.assertIsNotNone(body["alert"])
        self.assertIn("ДИҚҚАТ", body["alert"]["body"])

    def test_analyze_green_no_alert(self):
        txns = [{"id": "1", "user_id": "u1", "ts": "2026-10-07 09:00:00",
                 "type": "incoming_salary", "amount": 60000, "counterparty": "boss"}]
        body = client.post("/api/analyze", json={"transactions": txns}).json()
        self.assertEqual(body["level"], "GREEN")
        self.assertIsNone(body["alert"])

    def test_analyze_validation_422(self):
        r = client.post("/api/analyze", json={"transactions": [{"type": "hacker_stuff"}]})
        self.assertEqual(r.status_code, 422)  # Pydantic отклоняет мусор

    def test_quiz_cashback(self):
        body = client.post("/api/quiz", json={"answers": [1, 1, 1, 1, 0]}).json()
        self.assertTrue(body["passed"] and body["cashback"] == 100)

    def test_sim_requires_both_otp(self):
        bad = client.post("/api/sim", json={"old_phone": "+79160000001", "new_phone": "+79160000002",
                                             "otp_ok_old": False, "otp_ok_new": True}, headers=HEADERS).json()
        self.assertFalse(bad["ok"])
        ok = client.post("/api/sim", json={"old_phone": "+79160000001", "new_phone": "+79160000002",
                                            "otp_ok_old": True, "otp_ok_new": True}, headers=HEADERS).json()
        self.assertTrue(ok["ok"] and "cooldown_until" in ok)


if __name__ == "__main__":
    unittest.main()