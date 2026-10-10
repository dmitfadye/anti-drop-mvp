"""Регрессия по дефектам аудита T02–T22. Запуск из корня проекта:
.venv/bin/python -m unittest discover -s tests -v
"""
import sys
import threading
import unittest
import urllib.request
from http.server import HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from main import app
from src.detector import analyze_transactions
from src.db import get_db, reset_init_state_for_tests

client = TestClient(app)

# Setup test user in database
reset_init_state_for_tests()
for db in get_db():
    db.execute("INSERT OR REPLACE INTO users (user_id, phone, created_at) VALUES ('test_user', '+79160000001', datetime('now'))")
    db.commit()
    break

HEADERS = {"X-Sandbox-Subject": "test_user"}


def T(ts, type_, amount, cp="x", dev="dev_A", sim=None, uid="u1", tid="1"):
    return {"id": tid, "user_id": uid, "ts": ts, "type": type_, "amount": amount,
            "counterparty": cp, "device_id": dev, "sim_changed_days_ago": sim}


class TestTimePolicy(unittest.TestCase):
    """T03/T08: время валидируется, мусор — 422, будущее исключается."""

    def test_invalid_ts_is_422_not_500(self):
        r = client.post("/api/analyze", json={"transactions": [T("bad", "purchase", 1)]})
        self.assertEqual(r.status_code, 422)

    def test_mixed_timezones_normalized(self):
        a = [T("2026-10-07 14:02:00", "incoming_p2p", 3000, "s1", tid="1"),
             T("2026-10-07 14:07:00", "incoming_p2p", 3000, "s2", tid="2"),
             T("2026-10-07 14:12:00", "incoming_p2p", 3000, "s3", tid="3")]
        b = [T("2026-10-07T14:02:00+03:00", "incoming_p2p", 3000, "s1", tid="1"),
             T("2026-10-07T11:07:00Z", "incoming_p2p", 3000, "s2", tid="2"),
             T("2026-10-07 14:12:00", "incoming_p2p", 3000, "s3", tid="3")]
        ra = client.post("/api/analyze", json={"transactions": a})
        rb = client.post("/api/analyze", json={"transactions": b})
        self.assertEqual(ra.status_code, 200)
        self.assertEqual(rb.status_code, 200)
        self.assertEqual(ra.json()["score"], rb.json()["score"])  # один и тот же момент

    def test_future_excluded_with_explicit_analysis_at(self):
        txns = [T("2026-10-07 14:02:00", "incoming_p2p", 3000, "s1", tid="1"),
                T("2026-10-08 14:02:00", "incoming_p2p", 3000, "s2", tid="2")]
        body = client.post("/api/analyze", json={
            "transactions": txns, "analysis_at": "2026-10-07 15:00:00"}).json()
        self.assertEqual(body["metrics"]["excluded_future_count"], 1)
        self.assertEqual(body["metrics"]["analyzed"], 1)

    def test_detector_bad_ts_never_crashes(self):
        res = analyze_transactions([T("мусор", "purchase", 100), T(None, "purchase", 50)])  # type: ignore[arg-type]
        self.assertEqual(res["level"], "GREEN")
        self.assertEqual(res["metrics"].get("excluded_bad_ts"), 2)


class TestSubjectContract(unittest.TestCase):
    """T05/T06: один субъект, уникальные id."""

    def _attack_parts(self, uids):
        base = [("2026-10-07 14:02:00", "incoming_p2p", 3000, "s1"),
                ("2026-10-07 14:07:00", "incoming_p2p", 2500, "s2"),
                ("2026-10-07 14:12:00", "incoming_p2p", 4000, "s3"),
                ("2026-10-07 14:20:00", "incoming_p2p", 1800, "s4"),
                ("2026-10-07 14:25:00", "incoming_p2p", 3500, "s5"),
                ("2026-10-07 14:40:00", "outgoing_p2p", 9000, "mule")]
        return [T(ts, tp, a, cp, uid=u, tid=str(i), sim=1) for i, ((ts, tp, a, cp), u) in enumerate(zip(base, uids))]

    def test_mixed_users_rejected(self):
        txns = self._attack_parts(["u1", "u2", "u3", "u4", "u5", "u6"])
        r = client.post("/api/analyze", json={"transactions": txns})
        self.assertEqual(r.status_code, 422)  # было: общий RED/70 (E12)

    def test_subject_id_filters_strangers(self):
        txns = self._attack_parts(["u777"] * 5 + ["u999"])
        r = client.post("/api/analyze", json={"transactions": txns, "subject_id": "u777"})
        self.assertEqual(r.status_code, 422)

    def test_single_subject_ok(self):
        txns = self._attack_parts(["u777"] * 6)
        r = client.post("/api/analyze", json={"transactions": txns, "subject_id": "u777"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["level"], "RED")

    def test_duplicate_ids_rejected(self):
        txns = [T("2026-10-07 14:02:00", "incoming_p2p", 3000, "s1", tid="same"),
                T("2026-10-07 14:07:00", "incoming_p2p", 3000, "s2", tid="same")]
        r = client.post("/api/analyze", json={"transactions": txns})
        self.assertEqual(r.status_code, 422)


class TestCountingHonesty(unittest.TestCase):
    """T04/T07 + порядок выводов + устройство без истории."""

    def test_sim_zero_days_is_fresh(self):
        txns = [T(f"2026-10-07 14:{m:02d}:00", "incoming_p2p", 3000, f"s{i}", sim=0, tid=str(i))
                for i, m in enumerate([2, 7, 12])]
        res = analyze_transactions(txns)
        self.assertTrue(res["metrics"]["sim_changed_recently"])  # было: False (E11)
        self.assertTrue(any("SIM" in r for r in res["reasons"]))

    def test_zero_amounts_not_counted_as_transit(self):
        txns = [T(f"2026-10-07 14:{m:02d}:00", "incoming_p2p", 0, f"s{i}", tid=str(i))
                for i, m in enumerate([2, 7, 12, 20, 25])]
        res = analyze_transactions(txns)
        self.assertEqual(res["level"], "GREEN")  # было: YELLOW/45 (E14)
        self.assertEqual(res["metrics"]["excluded_zero_count"], 5)

    def test_out_before_in_no_flowthrough(self):
        txns = [T("2026-10-07 14:40:00", "outgoing_p2p", 12000, "mule", tid="9"),
                T("2026-10-07 14:50:00", "incoming_p2p", 3000, "s1", tid="1"),
                T("2026-10-07 14:55:00", "incoming_p2p", 3000, "s2", tid="2"),
                T("2026-10-07 14:58:00", "incoming_p2p", 3000, "s3", tid="3")]
        res = analyze_transactions(txns)
        self.assertNotIn("flow_through_ratio_60m", res["metrics"])  # вывод был ДО поступлений

    def test_no_device_rule_without_baseline(self):
        txns = [T("2026-10-07 14:02:00", "purchase", 100, "shop", dev="dev_NEW", tid="1")]
        res = analyze_transactions(txns)
        self.assertFalse(res["metrics"]["device_baseline"])
        self.assertFalse(any("стройств" in r for r in res["reasons"]))

    def test_negative_amount_rejected(self):
        r = client.post("/api/analyze", json={"transactions": [T("2026-10-07 14:00:00", "purchase", -5)]})
        self.assertEqual(r.status_code, 422)

    def test_overlong_strings_rejected(self):
        r = client.post("/api/analyze", json={"transactions": [T("2026-10-07 14:00:00", "purchase", 5, cp="z" * 300)]})
        self.assertEqual(r.status_code, 422)


class TestAlertContract(unittest.TestCase):
    """RED без транзита — общее объяснение; юридика нейтральная (T21)."""

    def test_red_without_transit_uses_generic(self):
        txns = [T("2026-10-07 10:00:00", "incoming_salary", 20000, "boss", tid="0")]
        txns += [T(f"2026-10-07 14:{m:02d}:00", "outgoing_p2p", 1000, f"r{i}", tid=str(i + 1))
                 for i, m in enumerate([2, 7, 12, 20])]
        txns += [T("2026-10-07 14:45:00", "cash_withdraw", 18000, "atm", tid="9")]
        body = client.post("/api/analyze", json={"transactions": txns, "lang": "ru"}).json()
        self.assertEqual(body["level"], "RED")
        self.assertIsNotNone(body["alert"])
        self.assertIn("похожи на рискованную схему", body["alert"]["body"])
        self.assertNotIn("от 0 человек", body["alert"]["body"])  # было бы ложью про транзит
        self.assertNotIn("грозит", body["alert"]["body"])  # T21: без категоричных приговоров

    def test_rules_version_exposed(self):
        body = client.post("/api/analyze", json={"transactions": []}).json()
        self.assertTrue(body["rules_version"])
        self.assertEqual(body["metrics"].get("rules_version"), body["rules_version"])
        self.assertIn("rules_version", client.get("/api/health").json())


class TestHonestMocks(unittest.TestCase):
    """T02/T18: учебные кейсы и призы вместо выдуманных действий.

    Legacy /api/cases отключён (410): он хранил кейсы в памяти процесса и не знал
    про субъекта. Целевой путь — /sandbox/cases с SQLite (см. test_sandbox_cases.py).
    """

    def test_case_idempotent(self):
        payload = {"summary": "тест", "lang": "ru", "score": 85, "idempotency_key": "demo-key-1"}
        r1 = client.post("/api/cases", json=payload)
        r2 = client.post("/api/cases", json=payload)
        for r in (r1, r2):
            self.assertEqual(r.status_code, 410, r.text)
            self.assertEqual(r.json()["error_code"], "LEGACY_CASES_DISABLED")
            self.assertEqual(r.headers.get("Deprecation"), "true")
            self.assertNotIn("case_id", r.json())

    def test_case_status_and_404(self):
        r = client.post("/api/cases", json={"summary": "тест"})
        self.assertEqual(r.status_code, 410, r.text)
        got = client.get("/api/cases/CASE-NOPE1234")
        self.assertEqual(got.status_code, 410)
        self.assertEqual(got.json()["error_code"], "LEGACY_CASES_DISABLED")

    def test_legacy_cases_hidden_from_openapi(self):
        schema = client.get("/openapi.json").json()
        self.assertNotIn("/api/cases", schema.get("paths", {}))
        self.assertIn("/sandbox/cases", schema.get("paths", {}))

    def test_quiz_reward_simulated(self):
        body = client.post("/api/quiz", json={"answers": [1, 1, 1, 1, 0]}).json()
        self.assertEqual(body["reward_status"], "simulated")
        self.assertIn("демо", body["message"].lower())

    def test_sim_response_marked_demo(self):
        body = client.post("/api/sim", json={"old_phone": "+79160000001", "new_phone": "+79160000002",
                                              "otp_ok_old": True, "otp_ok_new": True}, headers=HEADERS).json()
        self.assertTrue(body["demo"])

    def test_request_id_header(self):
        r = client.get("/api/health")
        self.assertTrue(r.headers.get("X-Request-ID"))


class TestOfflineAssets(unittest.TestCase):
    """T17: ни одного внешнего URL в UI и docs."""

    def test_no_cdn_in_index(self):
        html = client.get("/").text
        self.assertIn("/static/tailwind.css", html)
        self.assertNotIn("cdn.jsdelivr.net", html)
        self.assertNotIn("cdn.tailwindcss", html)

    def test_docs_local(self):
        r = client.get("/docs")
        self.assertEqual(r.status_code, 200)
        self.assertIn("/static/swagger/swagger-ui-bundle.js", r.text)
        self.assertNotIn("cdn.jsdelivr.net", r.text)

    def test_openapi_reachable(self):
        self.assertEqual(client.get("/openapi.json").status_code, 200)


class TestStdlibFallback(unittest.TestCase):
    """T10/T11: фолбэк не раскрывает correct и отдаёт 404, а не рвёт соединение."""

    @classmethod
    def setUpClass(cls):
        from app_stdlib import Handler
        cls.srv = HTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.thread.join(timeout=5)

    def test_quiz_answers_not_exposed(self):
        html = urllib.request.urlopen(f"http://127.0.0.1:{self.port}/", timeout=10).read().decode("utf-8")
        self.assertNotIn('"correct"', html)

    def test_unknown_path_is_404(self):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{self.port}/nope", timeout=10)
            self.fail("ожидался 404")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)


if __name__ == "__main__":
    unittest.main()