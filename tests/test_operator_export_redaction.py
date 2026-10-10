"""Operator export redaction: pseudonymous by construction, masked as a backstop."""
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from src.cases import reset_operator_store  # noqa: E402
from src.operator import EXPORT_COLUMNS, PII_SHAPED, redact_row  # noqa: E402

CASE = {
    'subject_pseudonym': 'sub_00000000cafe0001',
    'scenario_code': 'demo_attack',
    'level': 'RED',
    'score': 70,
    'locale': 'ru-RU',
    'template_id': 'warning_ru_control_v1',
    'evaluation_id': 'a' * 64,
    'rule_version': '2026-10-08.p1',
    'threshold_version': 'thresholds-2026.10.08-red50-yellow25',
    'episode_class': 'risk',
    'reason_codes': ['multiple_small_inbound'],
    'experiment_id': 'exp-warning-language-2026.10',
    'experiment_arm': 'control',
}


class TestRedactRow(unittest.TestCase):
    def test_only_allowlisted_columns_survive(self):
        row = redact_row({**CASE, 'summary': 'подозрительный транзит', 'created_at': '2026-10-08T12:00:00Z'})
        self.assertTrue(set(row) <= set(EXPORT_COLUMNS))
        self.assertNotIn('summary', row)
        self.assertEqual(row['subject_pseudonym'], 'sub_00000000cafe0001')

    def test_pii_shaped_columns_are_blanked(self):
        for field in PII_SHAPED:
            with self.subTest(field=field):
                row = redact_row({**CASE, field: '+79990000000'})
                if field in EXPORT_COLUMNS:
                    self.assertEqual(row[field], '[REDACTED]')
                self.assertNotIn(field, set(row) - set(EXPORT_COLUMNS))

    def test_digit_runs_are_masked_in_free_text_only(self):
        row = redact_row({**CASE, 'scenario_code': 'demo_manual +7 999 000 00 00'})
        self.assertNotIn('999000', row['scenario_code'])
        self.assertIn('[REDACTED]', row['scenario_code'])
        # Structured values must survive the mask intact.
        kept = redact_row({**CASE, 'created_at': '2026-10-08T14:53:40Z',
                           'rule_version': '2026-10-08.p1',
                           'threshold_version': 'thresholds-2026.10.08-red50-yellow25'})
        self.assertEqual(kept['created_at'], '2026-10-08T14:53:40Z')
        self.assertEqual(kept['rule_version'], '2026-10-08.p1')
        self.assertEqual(kept['threshold_version'], 'thresholds-2026.10.08-red50-yellow25')
        self.assertEqual(redact_row({**CASE, 'score': 70})['score'], '70')

    def test_sandbox_notice_is_always_present(self):
        row = redact_row(CASE)
        self.assertIn('песочница', row['sandbox_notice'])

    def test_score_is_exported_with_its_not_probability_marker(self):
        self.assertIn('score_is_not_probability', EXPORT_COLUMNS)
        row = redact_row({**CASE, 'score_is_not_probability': True})
        self.assertEqual(row['score_is_not_probability'], 'True')


class TestExportEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['ANTI_DROP_OPERATOR_UI_ENABLED'] = 'true'
        os.environ['ANTI_DROP_OPERATOR_EXPORT_ENABLED'] = 'true'
        cls.app = __import__('main').app

    @classmethod
    def tearDownClass(cls):
        os.environ.pop('ANTI_DROP_OPERATOR_UI_ENABLED', None)
        os.environ.pop('ANTI_DROP_OPERATOR_EXPORT_ENABLED', None)

    def setUp(self):
        reset_operator_store()
        self.client = TestClient(self.app, client=('127.0.0.1', 51234))
        self.client.post('/api/operator/cases', json=CASE, headers={'Idempotency-Key': 'c1'})

    def test_json_export_shape_and_content(self):
        response = self.client.get('/api/operator/export?format=json')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['schema_version'], 'OperatorExportV1')
        self.assertEqual(body['columns'], list(EXPORT_COLUMNS))
        self.assertEqual(body['count'], 1)
        self.assertIn('pseudonymous', body['security_note'])
        row = body['cases'][0]
        self.assertEqual(row['case_id'].startswith('case_'), True)
        self.assertIn('[REDACTED]', json.dumps(body['redaction']))

    def test_csv_export_has_the_allowlisted_header_only(self):
        response = self.client.get('/api/operator/export?format=csv')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers['content-type'].startswith('text/csv'))
        header = response.text.splitlines()[0]
        self.assertEqual(header, ','.join(EXPORT_COLUMNS))

    def test_export_carries_no_contact_shaped_data(self):
        body = self.client.get('/api/operator/export?format=json').json()
        rows_only = json.dumps(body['cases'], ensure_ascii=False).lower()
        for token in ('+7999', '4276', 'passport', 'otp', 'full_name', '@'):
            with self.subTest(token=token):
                self.assertNotIn(token, rows_only)
        # The redaction metadata deliberately names what it drops.
        self.assertIn('otp', json.dumps(body['redaction']).lower())

    def test_export_lists_are_csv_safe(self):
        self.client.post('/api/operator/cases', json={**CASE, 'subject_pseudonym': 'sub_00000000cafe0002',
                                                        'reason_codes': ['multiple_small_inbound', 'cashout_ratio']},
                         headers={'Idempotency-Key': 'c2'})
        csv_text = self.client.get('/api/operator/export?format=csv').text
        self.assertIn('cashout_ratio,multiple_small_inbound', csv_text.replace('"', ''))

    def test_unknown_format_is_refused(self):
        self.assertEqual(self.client.get('/api/operator/export?format=xlsx').status_code, 422)


if __name__ == '__main__':
    unittest.main()