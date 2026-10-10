"""Тесты детектора + квиза + смены номера. Запуск: python3 -m unittest discover -s tests -v"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.detector import analyze_transactions
from src.quiz import check_quiz
from src.sim_security import start_number_change


def T(ts, type_, amount, cp="x", dev="dev_A", sim=90):
    return {"id": "1", "user_id": "u1", "ts": ts, "type": type_, "amount": amount,
            "counterparty": cp, "device_id": dev, "sim_changed_days_ago": sim}


class TestDetector(unittest.TestCase):
    def test_normal_is_green(self):
        txns = [T("2026-10-07 09:00:00", "incoming_salary", 60000, "boss"),
                T("2026-10-07 12:00:00", "purchase", 1200, "shop")]
        self.assertEqual(analyze_transactions(txns)["level"], "GREEN")

    def test_transit_is_red(self):
        txns = [T(f"2026-10-07 14:{m:02d}:00", "incoming_p2p", 3000, f"s{i}") for i, m in enumerate([2, 7, 12, 20, 25])]
        txns += [T("2026-10-07 14:40:00", "outgoing_p2p", 12000, "mule")]
        res = analyze_transactions(txns)
        self.assertEqual(res["level"], "RED")
        self.assertGreaterEqual(res["score"], 50)

    def test_empty(self):
        self.assertEqual(analyze_transactions([])["level"], "GREEN")

    def test_cashout_alone_is_yellow_exact(self):
        # Изолированный обнал: ровно 25 баллов -> YELLOW (было: слабая проверка в обе стороны).
        txns = [T("2026-10-07 10:00:00", "incoming_p2p", 20000, "a"),
                T("2026-10-07 11:00:00", "cash_withdraw", 18000, "atm")]
        res = analyze_transactions(txns)
        self.assertEqual(res["level"], "YELLOW")
        self.assertEqual(res["score"], 25)

    def test_quiz_cashback(self):
        ok = check_quiz([1, 1, 1, 1, 0])
        self.assertTrue(ok["passed"])
        self.assertEqual(ok["cashback"], 100)
        self.assertEqual(ok["reward_status"], "simulated")  # T18: выплата не производится
        bad = check_quiz([0, 0, 0, 0, 1])
        self.assertFalse(bad["passed"])
        self.assertEqual(bad["cashback"], 0)

    def test_sim_same_number_canonical_formats(self):
        # T13/T16: один номер в разных форматах — совпадение, а не «смена».
        bad = start_number_change("+7 916 000-00-01", "+79160000001", otp_ok_old=True, otp_ok_new=True)
        self.assertFalse(bad["ok"])
        self.assertTrue(any("совпадают" in e for e in bad["errors"]))

    def test_sim_change_requires_both_otp(self):
        bad = start_number_change("+79160000001", "+79160000002", otp_ok_old=False, otp_ok_new=True)
        self.assertFalse(bad["ok"])
        ok = start_number_change("+79160000001", "+79160000002", otp_ok_old=True, otp_ok_new=True)
        self.assertTrue(ok["ok"] and "cooldown_until" in ok)


if __name__ == "__main__":
    unittest.main()
