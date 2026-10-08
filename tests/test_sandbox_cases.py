"""MVP-слой sandbox-кейсов: persistency, trusted subject, idempotency, errors, reason codes.

Запуск: python -m unittest discover -s tests -v

Каждый тест работает на временной SQLite-БД, чтобы проверять поведение
хранилища независимо от остальных тестов.
"""
import json
import logging
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

import src.db as db_module
from main import app
from src.reason_codes import ALL_CODES

client = TestClient(app, raise_server_exceptions=False)

SUBJECT = "demo-user-1"
OTHER_SUBJECT = "demo-user-2"

VALID_BODY = {
    "evaluation_id": "eval-001",
    "selected_language": "ru",
    "contact_reason": "suspicious_transfer_request",
}

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


_boom_route = None


def setUpModule():
    """Включаем логи и временный маршрут /__boom, который поднимает необработанное исключение.

    Маршрут добавляется только на время тестов и удаляется в tearDownModule:
    production-код не должен содержать эндпоинт, который всегда падает.
    """
    logging.getLogger("anti_drop").setLevel(logging.INFO)

    @app.get("/__boom", include_in_schema=False)
    def boom():
        raise RuntimeError("boom-secret-marker")

    global _boom_route
    for route in app.router.routes:
        if getattr(route, "path", None) == "/__boom":
            _boom_route = route


def tearDownModule():
    if _boom_route is not None:
        app.router.routes.remove(_boom_route)


class SandboxCaseTestBase(unittest.TestCase):
    """Изолированная временная БД на каждый тест + откат кэша инициализации."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db_path = Path(self._tmp.name) / "anti_drop_test.db"
        self._patch = mock.patch.object(db_module, "DATABASE_PATH", self.db_path)
        self._patch.start()
        self.addCleanup(self._patch.stop)
        db_module.reset_init_state_for_tests()
        self.addCleanup(db_module.reset_init_state_for_tests)

    def post_case(self, body=None, subject=SUBJECT, key="idem-001", **headers):
        hdrs = {"Content-Type": "application/json"}
        if subject is not None:
            hdrs["X-Sandbox-Subject"] = subject
        if key is not None:
            hdrs["Idempotency-Key"] = key
        hdrs.update(headers)
        return client.post("/sandbox/cases", json=body or VALID_BODY, headers=hdrs)


class TestPersistence(SandboxCaseTestBase):
    def test_case_survives_restart(self):
        created = self.post_case()
        self.assertEqual(created.status_code, 201, created.text)
        case_id = created.json()["case_id"]
        created_at = created.json()["created_at"]

        # Эмулируем перезапуск: новое подключение к тому же файлу БД.
        db_module.reset_init_state_for_tests()
        with self.subTest("кейс читается после пересоздания соединения"):
            got = client.get(f"/sandbox/cases/{case_id}", headers={"X-Sandbox-Subject": SUBJECT})
            self.assertEqual(got.status_code, 200, got.text)
            self.assertEqual(got.json()["case_id"], case_id)
            self.assertEqual(got.json()["created_at"], created_at)
            self.assertEqual(got.json()["status"], "created")

    def test_data_is_on_disk_not_in_memory(self):
        self.post_case()
        self.assertTrue(self.db_path.exists(), "БД должна быть файлом на диске")
        conn = sqlite3.connect(self.db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM sandbox_cases").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(count, 1)

    def test_unique_index_is_composite_subject_idempotency_key(self):
        """Индекс должен быть составным: глобальный unique на ключ блокировал бы чужой субъект."""
        self.post_case()
        conn = sqlite3.connect(self.db_path)
        try:
            indexes = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='sandbox_cases'")}
            conn.execute("SELECT 1")
        finally:
            conn.close()
        self.assertIn("ux_sandbox_cases_subject_idempotency_key", indexes)
        self.assertIn("ix_sandbox_cases_subject_created_at", indexes)
        self.assertNotIn(db_module.LEGACY_INDEX_NAME, indexes)

    def test_old_single_idempotency_index_is_migrated_if_present(self):
        """БД, созданная прошлой версией, не должна остаться с глобальным индексом."""
        legacy = sqlite3.connect(self.db_path)
        try:
            legacy.execute("CREATE TABLE IF NOT EXISTS sandbox_cases ("
                           "case_id TEXT PRIMARY KEY, subject_ref TEXT NOT NULL, "
                           "evaluation_id TEXT NOT NULL, idempotency_key TEXT NOT NULL, "
                           "payload_hash TEXT NOT NULL, status TEXT NOT NULL, "
                           "created_at TEXT NOT NULL, updated_at TEXT, sandbox INTEGER DEFAULT 1, "
                           "selected_language TEXT NOT NULL, contact_reason TEXT NOT NULL)")
            legacy.execute("CREATE UNIQUE INDEX ux_sandbox_cases_idempotency_key "
                           "ON sandbox_cases(idempotency_key)")
            legacy.commit()
        finally:
            legacy.close()
        self.assertIn(db_module.LEGACY_INDEX_NAME, self._index_names())

        # Перезапуск инициализации на существующей БД со старым индексом.
        db_module.reset_init_state_for_tests()
        self.post_case(key="after-migration")
        self.assertNotIn(db_module.LEGACY_INDEX_NAME, self._index_names())
        self.assertIn("ux_sandbox_cases_subject_idempotency_key", self._index_names())

    def _index_names(self) -> set:
        conn = sqlite3.connect(self.db_path)
        try:
            return {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='sandbox_cases'")}
        finally:
            conn.close()

    def test_schema_version_recorded(self):
        self.post_case()
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
        finally:
            conn.close()
        self.assertEqual(int(row[0]), db_module.SCHEMA_VERSION)

    def test_client_comment_not_persisted(self):
        body = {**VALID_BODY, "client_comment": "Просили переслать деньги"}
        r = self.post_case(body)
        self.assertEqual(r.status_code, 201, r.text)
        self.assertNotIn("client_comment", r.json())
        self.assertNotIn("Просили", r.text)
        conn = sqlite3.connect(self.db_path)
        try:
            dumped = " ".join(str(v) for row in conn.execute("SELECT * FROM sandbox_cases")
                               for v in row)
        finally:
            conn.close()
        self.assertNotIn("Просили", dumped)


class TestIdempotency(SandboxCaseTestBase):
    def test_same_key_same_payload_returns_same_case(self):
        first = self.post_case()
        second = self.post_case()
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json()["case_id"], second.json()["case_id"])
        self.assertEqual(first.headers.get("Idempotency-Replayed"), "false")
        self.assertEqual(second.headers.get("Idempotency-Replayed"), "true")

    def test_same_key_different_payload_returns_422_mismatch(self):
        first = self.post_case()
        other = self.post_case({**VALID_BODY, "contact_reason": "other"})
        self.assertEqual(first.status_code, 201)
        self.assertEqual(other.status_code, 422, other.text)
        body = other.json()
        self.assertEqual(body["error_code"], "IDEMPOTENCY_KEY_PAYLOAD_MISMATCH")
        self.assertNotIn("case_id", body)

    def test_comment_whitespace_does_not_break_replay(self):
        first = self.post_case({**VALID_BODY, "client_comment": "  текст  "})
        second = self.post_case({**VALID_BODY, "client_comment": "текст"})
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json()["case_id"], second.json()["case_id"])

    def test_different_keys_create_different_cases(self):
        a = self.post_case(key="idem-a")
        b = self.post_case(key="idem-b")
        self.assertEqual(a.status_code, 201)
        self.assertEqual(b.status_code, 201)
        self.assertNotEqual(a.json()["case_id"], b.json()["case_id"])

    def test_missing_idempotency_key_returns_422(self):
        r = self.post_case(key=None)
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["error_code"], "MISSING_IDEMPOTENCY_KEY")

    def test_invalid_idempotency_key_returns_422(self):
        r = self.post_case(key="bad key!")
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["error_code"], "INVALID_IDEMPOTENCY_KEY")

    def test_concurrent_same_key_does_not_duplicate(self):
        """Гонка на уникальном индексе: все потоки получают один case_id, без 500."""
        import threading

        from src.sandbox_cases import create_case

        results: list = []
        errors: list = []

        def worker() -> None:
            gen = db_module.get_db()
            conn = next(gen)
            try:
                results.append(create_case(
                    conn, subject_ref=SUBJECT, idempotency_key="race-key",
                    evaluation_id="eval-race", selected_language="ru",
                    contact_reason="other", payload_hash="h1"))
            except Exception as exc:  # noqa: BLE001 - фиксируем отказ вместо тихого 500
                errors.append(exc)
            finally:
                with self.assertRaises(StopIteration):
                    next(gen)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(errors, [])
        self.assertEqual(len({case["case_id"] for case, _ in results}), 1)
        self.assertEqual(sum(1 for _, replayed in results if replayed), 3)

    def test_same_key_different_hash_raises_mismatch(self):
        from src.errors import ApiError
        from src.sandbox_cases import create_case

        gen = db_module.get_db()
        conn = next(gen)
        self.addCleanup(lambda: next(gen, None))
        create_case(conn, subject_ref=SUBJECT, idempotency_key="h-key",
                    evaluation_id="eval-x", selected_language="ru",
                    contact_reason="other", payload_hash="h1")
        with self.assertRaises(ApiError) as ctx:
            create_case(conn, subject_ref=SUBJECT, idempotency_key="h-key",
                        evaluation_id="eval-y", selected_language="ru",
                        contact_reason="other", payload_hash="h2")
        self.assertEqual(ctx.exception.error_code, "IDEMPOTENCY_KEY_PAYLOAD_MISMATCH")
        self.assertEqual(ctx.exception.status_code, 422)


class TestTrustedSubject(SandboxCaseTestBase):
    def test_missing_subject_header_returns_401(self):
        r = self.post_case(subject=None)
        self.assertEqual(r.status_code, 401, r.text)
        self.assertEqual(r.json()["error_code"], "SUBJECT_REQUIRED")

    def test_invalid_subject_header_returns_401(self):
        r = self.post_case(subject="bad subject!")
        self.assertEqual(r.status_code, 401, r.text)
        self.assertEqual(r.json()["error_code"], "INVALID_SUBJECT_HEADER")

    def test_subject_in_body_is_rejected(self):
        for field in ("subject_ref", "user_id", "subject", "client_id"):
            with self.subTest(field=field):
                r = self.post_case({**VALID_BODY, field: "attacker"})
                self.assertEqual(r.status_code, 422, r.text)
                self.assertEqual(r.json()["error_code"], "UNTRUSTED_SUBJECT_FIELD")

    def test_user_id_in_body_returns_untrusted_subject_field(self):
        r = self.post_case({**VALID_BODY, "user_id": "u777"})
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["error_code"], "UNTRUSTED_SUBJECT_FIELD")
        self.assertEqual(r.json()["field"], "user_id")

    def test_device_id_in_body_returns_untrusted_subject_field(self):
        r = self.post_case({**VALID_BODY, "device_id": "dev_evil"})
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["error_code"], "UNTRUSTED_SUBJECT_FIELD")

    def test_subject_capitalized_returns_untrusted_subject_field(self):
        """Регистронезависимо: Subject и Subject_Ref не должны проходить как обычные поля."""
        for field in ("Subject", "SUBJECT_REF", "User_Id", "Phone"):
            with self.subTest(field=field):
                r = self.post_case({**VALID_BODY, field: "attacker"})
                self.assertEqual(r.status_code, 422, r.text)
                self.assertEqual(r.json()["error_code"], "UNTRUSTED_SUBJECT_FIELD")

    def test_pii_fields_in_body_rejected(self):
        for field in ("phone", "msisdn", "otp", "passport", "card", "pan"):
            with self.subTest(field=field):
                r = self.post_case({**VALID_BODY, field: "sensitive"})
                self.assertEqual(r.status_code, 422, r.text)
                self.assertEqual(r.json()["error_code"], "UNTRUSTED_SUBJECT_FIELD")

    def test_body_cannot_override_trusted_subject(self):
        r = self.post_case({**VALID_BODY, "subject_ref": "someone-else"})
        self.assertEqual(r.status_code, 422)
        case_id = self.post_case(key="idem-2").json()["case_id"]
        leaked = client.get(f"/sandbox/cases/{case_id}", headers={"X-Sandbox-Subject": OTHER_SUBJECT})
        self.assertEqual(leaked.status_code, 404)

    def test_own_subject_get_returns_200(self):
        case_id = self.post_case().json()["case_id"]
        r = client.get(f"/sandbox/cases/{case_id}", headers={"X-Sandbox-Subject": SUBJECT})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["subject_ref"], SUBJECT)

    def test_cross_subject_get_returns_404_not_403(self):
        case_id = self.post_case().json()["case_id"]
        r = client.get(f"/sandbox/cases/{case_id}", headers={"X-Sandbox-Subject": OTHER_SUBJECT})
        self.assertEqual(r.status_code, 404, r.text)
        self.assertEqual(r.json()["error_code"], "CASE_NOT_FOUND")
        # Чужой кейс не должен утекать ни через id, ни через subject_ref.
        self.assertNotIn(case_id, r.text)

    def test_list_returns_only_own_subject(self):
        mine = self.post_case().json()["case_id"]
        self.post_case(key="idem-other", subject=OTHER_SUBJECT)
        r = client.get("/sandbox/cases", headers={"X-Sandbox-Subject": SUBJECT})
        self.assertEqual(r.status_code, 200, r.text)
        ids = [c["case_id"] for c in r.json()["items"]]
        self.assertEqual(ids, [mine])
        self.assertNotIn(OTHER_SUBJECT, r.text)

    def test_list_requires_subject(self):
        self.assertEqual(client.get("/sandbox/cases").status_code, 401)

    def test_get_requires_subject(self):
        case_id = self.post_case().json()["case_id"]
        self.assertEqual(client.get(f"/sandbox/cases/{case_id}").status_code, 401)


class TestValidation(SandboxCaseTestBase):
    def test_invalid_contact_reason_returns_specific_error_code(self):
        r = self.post_case({**VALID_BODY, "contact_reason": "whatever"})
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["error_code"], "INVALID_CONTACT_REASON")
        self.assertEqual(r.json()["field"], "contact_reason")

    def test_invalid_evaluation_id_returns_specific_error_code(self):
        r = self.post_case({**VALID_BODY, "evaluation_id": "bad id with spaces"})
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["error_code"], "INVALID_EVALUATION_ID")
        self.assertEqual(r.json()["field"], "evaluation_id")

    def test_empty_evaluation_id_returns_422(self):
        r = self.post_case({**VALID_BODY, "evaluation_id": ""})
        self.assertEqual(r.status_code, 422, r.text)
        self.assertIn(r.json()["error_code"], ("INVALID_EVALUATION_ID", "VALIDATION_ERROR"))

    def test_invalid_evaluation_id_chars_returns_422(self):
        r = self.post_case({**VALID_BODY, "evaluation_id": "eval with spaces"})
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["error_code"], "INVALID_EVALUATION_ID")

    def test_unsupported_language_returns_specific_error_code(self):
        r = self.post_case({**VALID_BODY, "selected_language": "xx"})
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["error_code"], "UNSUPPORTED_LANGUAGE")
        self.assertEqual(r.json()["field"], "selected_language")

    def test_client_comment_too_long_returns_422(self):
        r = self.post_case({**VALID_BODY, "client_comment": "x" * 1001})
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["error_code"], "VALIDATION_ERROR")

    def test_unknown_field_rejected(self):
        r = self.post_case({**VALID_BODY, "score": 99})
        self.assertEqual(r.status_code, 422, r.text)

    def test_every_contact_reason_accepted(self):
        from src.sandbox_cases import CONTACT_REASONS
        for reason in CONTACT_REASONS:
            with self.subTest(reason=reason):
                r = self.post_case({**VALID_BODY, "contact_reason": reason},
                                   key=f"key-{reason}")
                self.assertEqual(r.status_code, 201, r.text)


class TestPagination(SandboxCaseTestBase):
    def test_negative_limit_returns_422(self):
        r = client.get("/sandbox/cases?limit=-5", headers={"X-Sandbox-Subject": SUBJECT})
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["error_code"], "VALIDATION_ERROR")

    def test_negative_offset_returns_422(self):
        r = client.get("/sandbox/cases?offset=-3", headers={"X-Sandbox-Subject": SUBJECT})
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["error_code"], "VALIDATION_ERROR")

    def test_limit_above_max_returns_422(self):
        r = client.get("/sandbox/cases?limit=1000", headers={"X-Sandbox-Subject": SUBJECT})
        self.assertEqual(r.status_code, 422, r.text)

    def test_list_cases_returns_total_count(self):
        self.post_case(key="k1")
        self.post_case(key="k2")
        r = client.get("/sandbox/cases", headers={"X-Sandbox-Subject": SUBJECT})
        body = r.json()
        self.assertEqual(body["total_count"], 2)
        self.assertEqual(len(body["items"]), 2)
        self.assertEqual(body["limit"], 20)
        self.assertEqual(body["offset"], 0)

    def test_total_count_excludes_other_subject(self):
        self.post_case(key="k1")
        self.post_case(key="k2", subject=OTHER_SUBJECT)
        body = client.get("/sandbox/cases", headers={"X-Sandbox-Subject": SUBJECT}).json()
        self.assertEqual(body["total_count"], 1)

    def test_offset_paginates(self):
        for i in range(3):
            self.post_case(key=f"k{i}")
        page = client.get("/sandbox/cases?limit=2&offset=2",
                          headers={"X-Sandbox-Subject": SUBJECT}).json()
        self.assertEqual(len(page["items"]), 1)
        self.assertEqual(page["total_count"], 3)


class TestErrorEnvelope(unittest.TestCase):
    def test_error_response_contains_request_id(self):
        r = client.post("/api/analyze", json={"transactions": [{"type": "hacker_stuff"}]})
        body = r.json()
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(body["error_code"], "VALIDATION_ERROR")
        self.assertTrue(body["request_id"])
        self.assertNotIn("detail", body)

    def test_validation_error_has_field_and_details(self):
        r = client.post("/api/analyze", json={"transactions": [{"type": "hacker_stuff"}]})
        body = r.json()
        self.assertTrue(body["details"])
        self.assertIn("field", body["details"][0])

    def test_x_request_id_propagated_in_response_header(self):
        r = client.get("/api/health", headers={"X-Request-ID": "req-mine"})
        self.assertEqual(r.headers.get("X-Request-ID"), "req-mine")

    def test_generated_request_id_present_when_header_missing(self):
        r = client.get("/api/health")
        rid = r.headers.get("X-Request-ID")
        self.assertTrue(rid)
        self.assertTrue(rid.startswith("req_"))

    def test_request_id_in_error_body_matches_header(self):
        r = client.post("/api/analyze", json={"transactions": [{"type": "hacker_stuff"}]},
                        headers={"X-Request-ID": "req-trace"})
        self.assertEqual(r.headers.get("X-Request-ID"), "req-trace")
        self.assertEqual(r.json()["request_id"], "req-trace")

    def test_404_uses_envelope(self):
        r = client.get("/api/cases/NOPE-0000")
        self.assertEqual(r.status_code, 410)
        self.assertEqual(r.json()["error_code"], "LEGACY_CASES_DISABLED")

    def test_unknown_route_returns_structured_404(self):
        r = client.get("/nope")
        self.assertEqual(r.status_code, 404, r.text)
        body = r.json()
        self.assertIn(body["error_code"], {"NOT_FOUND", "HTTP_ERROR"})
        self.assertTrue(body["request_id"])
        self.assertIn("X-Request-ID", r.headers)
        self.assertNotIn("detail", body)

    def test_method_not_allowed_returns_structured_405(self):
        r = client.delete("/sandbox/cases")
        self.assertEqual(r.status_code, 405, r.text)
        body = r.json()
        self.assertIn(body["error_code"], {"METHOD_NOT_ALLOWED", "HTTP_ERROR"})
        self.assertTrue(body["request_id"])
        self.assertNotIn("detail", body)

    def test_invalid_date_in_analyze_returns_422_not_500(self):
        r = client.post("/api/analyze", json={"transactions": [
            {"id": "1", "user_id": "u1", "ts": "bad", "type": "purchase", "amount": 1}]})
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["error_code"], "VALIDATION_ERROR")
        self.assertIn("ts", r.json()["details"][0]["field"])

    def test_mixed_timezone_does_not_500(self):
        r = client.post("/api/analyze", json={"transactions": [
            {"id": "1", "user_id": "u1", "ts": "2026-10-07T14:02:00+03:00", "type": "incoming_p2p", "amount": 100},
            {"id": "2", "user_id": "u1", "ts": "2026-10-07T11:07:00Z", "type": "incoming_p2p", "amount": 100}]})
        self.assertEqual(r.status_code, 200, r.text)


class TestReasonCodes(unittest.TestCase):
    def test_analyze_response_contains_reason_codes(self):
        r = client.post("/api/analyze", json={"transactions": ATTACK, "lang": "ru"})
        body = r.json()
        self.assertEqual(body["level"], "RED")
        self.assertIn("reason_codes", body)
        self.assertIn("MULTIPLE_SMALL_INBOUND", body["reason_codes"])

    def test_reason_codes_are_machine_readable(self):
        body = client.post("/api/analyze", json={"transactions": ATTACK}).json()
        for code in body["reason_codes"]:
            self.assertIn(code, ALL_CODES)
            self.assertRegex(code, r"^[A-Z][A-Z0-9_]*$")

    def test_sim_zero_produces_sim_changed_recently_code(self):
        txns = [{"id": str(i), "user_id": "u1", "ts": f"2026-10-07 14:{m:02d}:00",
                 "type": "incoming_p2p", "amount": 3000, "counterparty": f"s{i}",
                 "device_id": "d", "sim_changed_days_ago": 0}
                for i, m in enumerate([2, 7, 12])]
        body = client.post("/api/analyze", json={"transactions": txns}).json()
        self.assertIn("SIM_CHANGED_RECENTLY", body["reason_codes"])

    def test_future_event_excluded_code(self):
        txns = [
            {"id": "1", "user_id": "u1", "ts": "2026-10-07 14:02:00", "type": "incoming_p2p",
             "amount": 3000, "counterparty": "s1", "device_id": "d"},
            {"id": "2", "user_id": "u1", "ts": "2026-10-08 14:02:00", "type": "incoming_p2p",
             "amount": 3000, "counterparty": "s2", "device_id": "d"},
        ]
        body = client.post("/api/analyze", json={
            "transactions": txns, "analysis_at": "2026-10-07 15:00:00"}).json()
        self.assertIn("FUTURE_EVENT_EXCLUDED", body["reason_codes"])
        self.assertEqual(body["metrics"]["excluded_future_count"], 1)

    def test_empty_transactions_has_insufficient_data(self):
        body = client.post("/api/analyze", json={"transactions": []}).json()
        self.assertEqual(body["level"], "GREEN")
        self.assertEqual(body["score"], 0)
        self.assertIn("INSUFFICIENT_DATA", body["reason_codes"])

    def test_green_scenario_has_no_risk_signal(self):
        txns = [{"id": "1", "user_id": "u1", "ts": "2026-10-07 09:00:00",
                 "type": "incoming_salary", "amount": 60000, "counterparty": "boss"}]
        body = client.post("/api/analyze", json={"transactions": txns}).json()
        self.assertEqual(body["level"], "GREEN")
        self.assertIn("NO_RISK_SIGNAL", body["reason_codes"])

    def test_score_not_changed_by_reason_code_addition(self):
        """Фиксируем score/level детектора после добавления reason_codes."""
        from src.detector import analyze_transactions
        res = analyze_transactions([
            {"id": "0", "user_id": "u1", "ts": "2026-10-07 10:00:00", "type": "incoming_p2p",
             "amount": 20000, "counterparty": "a"},
            {"id": "1", "user_id": "u1", "ts": "2026-10-07 11:00:00", "type": "cash_withdraw",
             "amount": 18000, "counterparty": "atm"}])
        self.assertEqual(res["score"], 25)
        self.assertEqual(res["level"], "YELLOW")

    def test_reason_codes_do_not_change_score_for_sample_normal_and_sample_drop_attack(self):
        """Регрессия демо-сценариев из UI: reason_codes не сдвигают score/level."""
        from src.detector import analyze_transactions

        normal = [
            {"id": str(i), "user_id": "u777", "ts": ts + ":00", "type": tp,
             "amount": a, "counterparty": cp, "device_id": "dev_X", "sim_changed_days_ago": 90}
            for i, (ts, tp, a, cp) in enumerate([
                ("2026-10-06 09:00", "incoming_salary", 60000, "работодатель"),
                ("2026-10-06 12:10", "purchase", 1200, "магнит"),
                ("2026-10-06 18:40", "purchase", 800, "аптека"),
                ("2026-10-07 09:15", "purchase", 1500, "пятёрочка"),
            ])
        ]
        attack = [
            {"id": str(i), "user_id": "u777", "ts": ts + ":00", "type": tp,
             "amount": a, "counterparty": cp, "device_id": "dev_X", "sim_changed_days_ago": 1}
            for i, (ts, tp, a, cp) in enumerate([
                ("2026-10-07 13:00", "incoming_salary", 15000, "стройка"),
                ("2026-10-07 14:02", "incoming_p2p", 3000, "отправитель_1"),
                ("2026-10-07 14:07", "incoming_p2p", 2500, "отправитель_2"),
                ("2026-10-07 14:12", "incoming_p2p", 4000, "отправитель_3"),
                ("2026-10-07 14:20", "incoming_p2p", 1800, "отправитель_4"),
                ("2026-10-07 14:25", "incoming_p2p", 3500, "отправитель_5"),
                ("2026-10-07 14:40", "outgoing_p2p", 9000, "мул"),
                ("2026-10-07 14:45", "cash_withdraw", 5000, "банкомат"),
            ])
        ]

        for name, txns, expected_level in (("normal", normal, "GREEN"), ("attack", attack, "RED")):
            with self.subTest(scenario=name):
                res = analyze_transactions(txns)
                self.assertEqual(res["level"], expected_level)
                # reason_codes не пустое множество кодов поверх тех же правил
                self.assertTrue(res["reason_codes"])
                self.assertTrue(all(c in ALL_CODES for c in res["reason_codes"]))
                body = client.post("/api/analyze", json={"transactions": txns}).json()
                self.assertEqual(body["level"], res["level"])
                self.assertEqual(body["score"], res["score"])
                self.assertEqual(body["reason_codes"], res["reason_codes"])

    def test_score_interpretation_disclaims_probability(self):
        body = client.post("/api/analyze", json={"transactions": ATTACK}).json()
        self.assertEqual(body["score_interpretation"], "deterministic_rule_sum_not_probability")
        self.assertLessEqual(body["score"], 100)

    def test_evaluation_id_present_and_stable_in_response(self):
        body = client.post("/api/analyze", json={"transactions": ATTACK}).json()
        self.assertTrue(body["evaluation_id"])
        self.assertTrue(body["evaluation_id"].startswith("eval_"))

    def test_legacy_fields_preserved(self):
        body = client.post("/api/analyze", json={"transactions": ATTACK}).json()
        for field in ("score", "level", "reasons", "metrics", "rules_version", "alert"):
            self.assertIn(field, body)


class TestIdempotencyScopePerSubject(unittest.TestCase):
    """D-1: ключ идемпотентности действует в пределах одного субъекта.

    Глобальный ключ позволял занять его одному субъекту и заблокировать другому,
    а по коду ответа — узнать, что ключ кем-то уже использован.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db_path = Path(self._tmp.name) / "scope.db"
        self._patch = mock.patch.object(db_module, "DATABASE_PATH", self.db_path)
        self._patch.start()
        self.addCleanup(self._patch.stop)
        db_module.reset_init_state_for_tests()
        self.addCleanup(db_module.reset_init_state_for_tests)

    def post(self, subject: str, key: str, body: dict):
        return client.post("/sandbox/cases", json=body, headers={
            "Content-Type": "application/json",
            "X-Sandbox-Subject": subject,
            "Idempotency-Key": key,
        })

    def test_same_idempotency_key_other_subject_creates_own_case(self):
        alice = self.post("alice", "shared-key-1", VALID_BODY)
        bob = self.post("bob", "shared-key-1", VALID_BODY)

        self.assertEqual(alice.status_code, 201, alice.text)
        self.assertEqual(bob.status_code, 201, bob.text)
        self.assertNotEqual(alice.json()["case_id"], bob.json()["case_id"])
        self.assertEqual(bob.json()["subject_ref"], "bob")
        self.assertNotIn(alice.json()["case_id"], bob.text)

    def test_idempotency_scope_is_per_subject(self):
        same = {**VALID_BODY, "evaluation_id": "eval-same"}
        diff = {**VALID_BODY, "evaluation_id": "eval-diff"}

        # 1. другой субъект + тот же ключ + то же тело -> свой новый кейс
        a1 = self.post("alice", "k", same)
        b1 = self.post("bob", "k", same)
        self.assertEqual(a1.status_code, 201)
        self.assertEqual(b1.status_code, 201)
        self.assertNotEqual(a1.json()["case_id"], b1.json()["case_id"])

        # 2. тот же субъект + тот же ключ + то же тело -> replay того же кейса
        a2 = self.post("alice", "k", same)
        self.assertEqual(a2.status_code, 200, a2.text)
        self.assertEqual(a2.json()["case_id"], a1.json()["case_id"])
        self.assertEqual(a2.headers.get("Idempotency-Replayed"), "true")

        # 3. тот же субъект + тот же ключ + другое тело -> 422
        a3 = self.post("alice", "k", diff)
        self.assertEqual(a3.status_code, 422, a3.text)
        self.assertEqual(a3.json()["error_code"], "IDEMPOTENCY_KEY_PAYLOAD_MISMATCH")

        # 4. субъект, который ключ ещё не использовал, получает свой кейс (201),
        #    несмотря на занятый ключ и чужое расхождение payload.
        c1 = self.post("carol", "k", diff)
        self.assertEqual(c1.status_code, 201, c1.text)
        self.assertEqual(c1.json()["subject_ref"], "carol")

        # 5. и повтор carol с другим телом уже даёт 422 — mismatch в пределах субъекта
        c2 = self.post("carol", "k", same)
        self.assertEqual(c2.status_code, 422, c2.text)
        self.assertEqual(c2.json()["error_code"], "IDEMPOTENCY_KEY_PAYLOAD_MISMATCH")

    def test_mismatch_does_not_reveal_other_subject(self):
        self.post("alice", "k", VALID_BODY)
        bob = self.post("bob", "k", {**VALID_BODY, "evaluation_id": "eval-other"})
        self.assertEqual(bob.status_code, 201)
        self.assertNotIn("alice", bob.text)


class TestInternalErrorEnvelope(unittest.TestCase):
    """Необработанное исключение: 500 + envelope + X-Request-ID, без внутренних деталей."""

    def test_500_response_contains_request_id_header(self):
        r = client.get("/__boom", headers={"X-Request-ID": "req-trace-500"})
        self.assertEqual(r.status_code, 500, r.text)
        self.assertEqual(r.headers.get("X-Request-ID"), "req-trace-500")
        body = r.json()
        self.assertEqual(body["error_code"], "INTERNAL_ERROR")
        self.assertEqual(body["request_id"], "req-trace-500")

    def test_500_does_not_leak_internals(self):
        r = client.get("/__boom")
        self.assertEqual(r.status_code, 500)
        text = r.text.lower()
        for leak in ("traceback", "boom-secret-marker", "runtimeerror", "file \""):
            self.assertNotIn(leak, text, f"500 раскрывает {leak}")

    def test_500_generates_request_id_when_missing(self):
        r = client.get("/__boom")
        self.assertTrue(r.headers.get("X-Request-ID", "").startswith("req_"))
        self.assertEqual(r.json()["request_id"], r.headers.get("X-Request-ID"))


class TestOpenApiContract(unittest.TestCase):
    """D-5: жюри на /docs должно видеть sandbox-заголовки и перечисления."""

    def setUp(self):
        self.schema = client.get("/openapi.json").json()

    def _params(self, path: str, method: str) -> dict:
        return {p["name"]: p for p in self.schema["paths"][path][method].get("parameters", [])}

    def test_openapi_documents_sandbox_headers(self):
        params = self._params("/sandbox/cases", "post")
        self.assertIn("X-Sandbox-Subject", params)
        self.assertIn("Idempotency-Key", params)

    def test_openapi_documents_idempotency_key(self):
        p = self._params("/sandbox/cases", "post")["Idempotency-Key"]
        self.assertEqual(p["in"], "header")
        self.assertTrue(p["required"])
        self.assertIn("subject", p["description"].lower())

    def test_openapi_marks_subject_header_as_test_only(self):
        p = self._params("/sandbox/cases", "post")["X-Sandbox-Subject"]
        self.assertIn("TEST-ONLY", p["description"])
        self.assertIn("gateway", p["description"].lower())
        self.assertTrue(p["required"])

    def test_openapi_headers_present_on_get_endpoints(self):
        for path in ("/sandbox/cases", "/sandbox/cases/{case_id}"):
            params = self._params(path, "get")
            self.assertIn("X-Sandbox-Subject", params, path)

    def test_contact_reason_schema_is_enum_or_literal(self):
        ref = self.schema["components"]["schemas"]["SandboxCaseCreate"]["properties"]["contact_reason"]
        self.assertIn("enum", ref, "contact_reason должен быть перечислением в OpenAPI")
        self.assertIn("suspicious_transfer_request", ref["enum"])

    def test_selected_language_schema_is_enum(self):
        ref = self.schema["components"]["schemas"]["SandboxCaseCreate"]["properties"]["selected_language"]
        self.assertIn("enum", ref)
        self.assertIn("ru", ref["enum"])

    def test_list_response_documents_total_count(self):
        props = self.schema["components"]["schemas"]["SandboxCaseListResponse"]["properties"]
        self.assertIn("total_count", props)

    def test_legacy_cases_not_in_openapi(self):
        self.assertNotIn("/api/cases", self.schema["paths"])

    def test_language_literal_matches_alert_templates(self):
        """Два источника правды об языках разъедутся, если их не связать тестом:
        роут проверит SUPPORTED_LANGS, а Pydantic — Literal, и клиент получил бы
        VALIDATION_ERROR вместо внятного UNSUPPORTED_LANGUAGE (или наоборот)."""
        from typing import get_args

        from models import LanguageCode
        from src.alerts import SUPPORTED_LANGS
        self.assertEqual(set(get_args(LanguageCode)), set(SUPPORTED_LANGS))

    def test_contact_reason_literal_matches_allowlist(self):
        from typing import get_args

        from models import ContactReason
        from src.sandbox_cases import CONTACT_REASONS
        self.assertEqual(set(get_args(ContactReason)), set(CONTACT_REASONS))


class TestLegacyEndpointAlwaysGone(unittest.TestCase):
    """Отключённый endpoint обязан отвечать 410 при ЛЮБОМ теле, иначе демо
    выглядит как две рабочие системы создания кейсов."""

    def _headers(self):
        return {"Content-Type": "application/json"}

    def test_legacy_post_returns_410_even_with_invalid_body(self):
        r = client.post("/api/cases", json={"summary": 1, "lang": "xxxxxxx", "score": 999}, headers=self._headers())
        self.assertEqual(r.status_code, 410, r.text)
        self.assertEqual(r.json()["error_code"], "LEGACY_CASES_DISABLED")

    def test_legacy_post_returns_410_with_empty_body(self):
        r = client.post("/api/cases", json={}, headers=self._headers())
        self.assertEqual(r.status_code, 410, r.text)

    def test_legacy_post_returns_410_without_body(self):
        r = client.post("/api/cases", headers=self._headers())
        self.assertEqual(r.status_code, 410, r.text)

    def test_legacy_get_returns_410(self):
        r = client.get("/api/cases/CASE-ANY")
        self.assertEqual(r.status_code, 410, r.text)
        self.assertEqual(r.headers.get("Deprecation"), "true")

    def test_legacy_never_returns_case_id(self):
        r = client.post("/api/cases", json={"summary": "x"}, headers=self._headers())
        self.assertNotIn("case_id", r.text)


class TestLogging(unittest.TestCase):
    """D-4: логи должны помогать разбору и не содержать ПДн."""

    def test_logs_include_request_id_and_case_id(self):
        with self.assertLogs("anti_drop", level="INFO") as captured:
            client.post("/api/health", headers={"X-Request-ID": "req-log-check"})
        text = "\n".join(captured.output)
        self.assertIn("req-log-check", text)
        self.assertIn("/api/health", text)

    def test_case_logs_include_case_id_and_subject_hash_not_raw_subject(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "log.db"
            with mock.patch.object(db_module, "DATABASE_PATH", db_path):
                db_module.reset_init_state_for_tests()
                try:
                    with self.assertLogs("anti_drop", level="INFO") as captured:
                        client.post("/sandbox/cases", json=VALID_BODY, headers={
                            "Content-Type": "application/json",
                            "X-Sandbox-Subject": "alice",
                            "Idempotency-Key": "log-key-1",
                            "X-Request-ID": "req-log-case",
                        })
                finally:
                    db_module.reset_init_state_for_tests()

        text = "\n".join(captured.output)
        self.assertIn("case_created", text)
        self.assertIn("req-log-case", text)
        self.assertIn("case_", text)
        # Субъект — только как хеш-префикс, сырое значение в логах отсутствует.
        self.assertIn("subject_hash=", text)
        self.assertNotIn("alice", text)

    def test_logs_do_not_include_client_comment(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "log2.db"
            with mock.patch.object(db_module, "DATABASE_PATH", db_path):
                db_module.reset_init_state_for_tests()
                try:
                    with self.assertLogs("anti_drop", level="DEBUG") as captured:
                        client.post("/sandbox/cases", json={
                            **VALID_BODY, "client_comment": "секретный комментарий клиента"},
                            headers={
                                "Content-Type": "application/json",
                                "X-Sandbox-Subject": "alice",
                                "Idempotency-Key": "log-key-2"})
                finally:
                    db_module.reset_init_state_for_tests()

        text = "\n".join(captured.output)
        self.assertNotIn("секретный комментарий клиента", text)

    def test_startup_logs_resolved_database_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "startup.db"
            with mock.patch.object(db_module, "DATABASE_PATH", db_path):
                db_module.reset_init_state_for_tests()
                with self.assertLogs("anti_drop.db", level="INFO") as captured:
                    db_module.init_db()
        text = "\n".join(captured.output)
        self.assertIn("db_ready", text)
        self.assertIn(str(db_path.resolve()), text)
        self.assertIn("schema_version", text)


class TestHttpConcurrency(SandboxCaseTestBase):
    """Параллельные HTTP-запросы: без 500 и без дублей (D-1 плюс гонка на индексе)."""

    def _run_parallel(self, specs: list[tuple[str, str, dict]]) -> list:
        """Каждый поток использует свой TestClient: общий клиент не потокобезопасен."""
        from concurrent.futures import ThreadPoolExecutor

        def call(spec):
            subject, key, body = spec
            local = TestClient(app, raise_server_exceptions=False)
            try:
                return local.post("/sandbox/cases", json=body, headers={
                    "Content-Type": "application/json",
                    "X-Sandbox-Subject": subject,
                    "Idempotency-Key": key,
                })
            finally:
                local.close()

        with ThreadPoolExecutor(max_workers=len(specs)) as pool:
            return list(pool.map(call, specs))

    def test_http_concurrent_same_key_same_subject_creates_one_case(self):
        specs = [(SUBJECT, "same-key", VALID_BODY)] * 5
        responses = self._run_parallel(specs)
        statuses = [r.status_code for r in responses]
        self.assertNotIn(500, statuses, f"гонка дала 500: {statuses}")
        self.assertEqual(statuses.count(201), 1, statuses)
        self.assertEqual(statuses.count(200), 4, statuses)
        self.assertEqual(len({r.json()["case_id"] for r in responses}), 1)

    def test_http_concurrent_same_key_different_subjects_creates_two_cases(self):
        subjects = ["alice", "bob", "carol", "dave", "erin"]
        specs = [(s, "shared-key", VALID_BODY) for s in subjects]
        responses = self._run_parallel(specs)
        statuses = [r.status_code for r in responses]
        self.assertNotIn(500, statuses, f"гонка дала 500: {statuses}")
        self.assertEqual(statuses, [201] * len(subjects))
        self.assertEqual(len({r.json()["case_id"] for r in responses}), len(subjects))
        for subject, r in zip(subjects, responses):
            self.assertEqual(r.json()["subject_ref"], subject)


class TestRestartAcrossProcesses(unittest.TestCase):
    """Перезапуск в отдельном процессе: кейс обязан уцелеть на диске."""

    def _client_env(self, db_path: Path) -> dict:
        env = dict(os.environ)
        env["DATABASE_PATH"] = str(db_path)
        return env

    def _run_script(self, db_path: Path, script: str) -> dict:
        repo_root = Path(__file__).resolve().parent.parent
        proc = subprocess.run(
            [sys.executable, "-c", script],
            cwd=repo_root, env=self._client_env(db_path),
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout.strip().splitlines()[-1])

    def test_real_process_restart_preserves_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "restart.db"

            created = self._run_script(db_path, """
import json, sys
sys.path.insert(0, ".")
from fastapi.testclient import TestClient
from main import app
with TestClient(app) as c:
    r = c.post("/sandbox/cases", json={
        "evaluation_id": "eval-restart",
        "selected_language": "ru",
        "contact_reason": "suspicious_transfer_request",
    }, headers={"X-Sandbox-Subject": "alice", "Idempotency-Key": "restart-key"})
    print(json.dumps({"status": r.status_code, "body": r.json()}))
""")
            self.assertEqual(created["status"], 201, created)
            case_id = created["body"]["case_id"]
            created_at = created["body"]["created_at"]

            # Новый процесс, тот же файл БД.
            fetched = self._run_script(db_path, f"""
import json, sys
sys.path.insert(0, ".")
from fastapi.testclient import TestClient
from main import app
with TestClient(app) as c:
    r = c.get("/sandbox/cases/{case_id}", headers={{"X-Sandbox-Subject": "alice"}})
    leak = c.get("/sandbox/cases/{case_id}", headers={{"X-Sandbox-Subject": "bob"}})
    print(json.dumps({{"status": r.status_code, "body": r.json(), "leak_status": leak.status_code}}))
""")
            self.assertEqual(fetched["status"], 200, fetched)
            self.assertEqual(fetched["body"]["case_id"], case_id)
            self.assertEqual(fetched["body"]["created_at"], created_at)
            self.assertEqual(fetched["body"]["status"], "created")
            self.assertEqual(fetched["leak_status"], 404)


class TestStorageFailure(unittest.TestCase):
    """БД недоступна -> контролируемый 503, а не имитация успеха (никакого 201)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        # Путь указывает на каталог: sqlite3.connect() честно падает "unable to open database file".
        blocked = Path(self._tmp.name) / "blocked_dir"
        blocked.mkdir()
        self._patch = mock.patch.object(db_module, "DATABASE_PATH", blocked)
        self._patch.start()
        self.addCleanup(self._patch.stop)
        db_module.reset_init_state_for_tests()
        self.addCleanup(db_module.reset_init_state_for_tests)

    def _post(self):
        return client.post("/sandbox/cases", json=VALID_BODY, headers={
            "Content-Type": "application/json",
            "X-Sandbox-Subject": SUBJECT,
            "Idempotency-Key": "idem-storage-fail",
        })

    def test_storage_unavailable_returns_503_not_fake_success(self):
        r = self._post()
        self.assertEqual(r.status_code, 503, r.text)
        self.assertEqual(r.json()["error_code"], "STORAGE_UNAVAILABLE")
        self.assertNotIn("case_id", r.json())

    def test_storage_failure_has_no_internal_details(self):
        r = self._post()
        self.assertNotIn("sqlite3", r.text.lower())
        self.assertNotIn("traceback", r.text.lower())

    def test_get_on_broken_storage_returns_503(self):
        r = client.get("/sandbox/cases/case_whatever", headers={"X-Sandbox-Subject": SUBJECT})
        self.assertEqual(r.status_code, 503, r.text)
        self.assertEqual(r.json()["error_code"], "STORAGE_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()