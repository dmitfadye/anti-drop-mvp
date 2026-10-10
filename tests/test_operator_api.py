"""Operator sandbox API: flag gates, loopback gate, idempotency, status machine."""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from src.cases import reset_operator_store  # noqa: E402
from src.flags import SANDBOX_BANNER  # noqa: E402

FLAGS = ('ANTI_DROP_DEMO_MODE', 'ANTI_DROP_OPERATOR_UI_ENABLED', 'ANTI_DROP_OPERATOR_EXPORT_ENABLED',
         'ANTI_DROP_EXPERIMENT_ENABLED', 'ANTI_DROP_ADVISORY_ENABLED', 'ANTI_DROP_OPERATOR_LOG')

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
}


def status(client_: TestClient, case_id: str, new_status: str, key: str, **extra) -> dict:
    body = {'status': new_status, 'actor_role': 'demo_operator', **extra}
    return client_.post(f'/api/operator/cases/{case_id}/status', json=body,
                        headers={'Idempotency-Key': key})


class TestFlagGates(unittest.TestCase):
    def setUp(self):
        self.app = __import__('main').app

    def test_operator_surface_is_off_by_default(self):
        for name in FLAGS:
            os.environ.pop(name, None)
        os.environ['ANTI_DROP_DEMO_MODE'] = 'true'
        reset_operator_store()
        try:
            default_client = TestClient(self.app, client=('127.0.0.1', 51234))
            for path in ('/api/operator/cases', '/api/operator/metrics', '/api/operator/status-machine'):
                with self.subTest(path=path):
                    self.assertEqual(default_client.get(path).status_code, 503)
            self.assertEqual(default_client.get('/operator').status_code, 503)
        finally:
            os.environ['ANTI_DROP_DEMO_MODE'] = 'true'

    def test_health_reports_the_flag_state(self):
        default_client = TestClient(self.app, client=('127.0.0.1', 51234))
        features = default_client.get('/api/health').json()['p1_features']
        self.assertFalse(features['operator_ui_enabled'])
        self.assertFalse(features['experiment_enabled'])
        self.assertFalse(features['advisory_enabled'])
        self.assertEqual(features['target_locale'], 'uz-UZ')
        self.assertIn(SANDBOX_BANNER, default_client.get('/api/health').json()['limitations'])

    def test_non_loopback_client_is_refused(self):
        os.environ['ANTI_DROP_OPERATOR_UI_ENABLED'] = 'true'
        reset_operator_store()
        try:
            remote = TestClient(self.app, client=('203.0.113.7', 51234))
            self.assertEqual(remote.get('/api/operator/cases').status_code, 403)
            loopback = TestClient(self.app, client=('127.0.0.1', 51234))
            self.assertEqual(loopback.get('/api/operator/cases').status_code, 200)
        finally:
            os.environ.pop('ANTI_DROP_OPERATOR_UI_ENABLED', None)

    def test_export_is_separately_gated(self):
        os.environ['ANTI_DROP_OPERATOR_UI_ENABLED'] = 'true'
        os.environ.pop('ANTI_DROP_OPERATOR_EXPORT_ENABLED', None)
        reset_operator_store()
        try:
            local = TestClient(self.app, client=('127.0.0.1', 51234))
            self.assertEqual(local.get('/api/operator/export?format=json').status_code, 503)
            os.environ['ANTI_DROP_OPERATOR_EXPORT_ENABLED'] = 'true'
            self.assertEqual(local.get('/api/operator/export?format=json').status_code, 200)
        finally:
            os.environ.pop('ANTI_DROP_OPERATOR_UI_ENABLED', None)
            os.environ.pop('ANTI_DROP_OPERATOR_EXPORT_ENABLED', None)

    def test_bad_flag_value_fails_loudly(self):
        from src.flags import FlagError, env_flag

        os.environ['ANTI_DROP_BROKEN_FLAG'] = 'maybe'
        try:
            with self.assertRaises(FlagError):
                env_flag('ANTI_DROP_BROKEN_FLAG')
        finally:
            os.environ.pop('ANTI_DROP_BROKEN_FLAG', None)


class TestOperatorFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['ANTI_DROP_OPERATOR_UI_ENABLED'] = 'true'
        os.environ['ANTI_DROP_OPERATOR_EXPORT_ENABLED'] = 'true'
        reset_operator_store()
        cls.app = __import__('main').app

    @classmethod
    def tearDownClass(cls):
        os.environ.pop('ANTI_DROP_OPERATOR_UI_ENABLED', None)
        os.environ.pop('ANTI_DROP_OPERATOR_EXPORT_ENABLED', None)

    def setUp(self):
        reset_operator_store()
        self.client = TestClient(self.app, client=('127.0.0.1', 51234))
        self.case_id = self.client.post('/api/operator/cases', json=CASE,
                                        headers={'Idempotency-Key': 'create-1'}).json()['case_id']

    def test_creation_requires_an_idempotency_key(self):
        reset_operator_store()
        self.assertEqual(self.client.post('/api/operator/cases', json=CASE).status_code, 400)

    def test_creation_is_idempotent(self):
        again = self.client.post('/api/operator/cases', json=CASE, headers={'Idempotency-Key': 'create-1'})
        self.assertEqual(again.status_code, 201)
        self.assertTrue(again.json()['idempotent_replay'])
        self.assertEqual(again.json()['case_id'], self.case_id)
        self.assertEqual(self.client.get('/api/operator/cases').json()['count'], 1)

    def test_creation_rejects_out_of_allowlist_and_raw_refs(self):
        for override in ({'scenario_code': 'my_own_scenario'}, {'subject_pseudonym': '+79990000000'},
                         {'score': 500}, {'level': 'PURPLE'}):
            with self.subTest(override=override):
                response = self.client.post('/api/operator/cases', json={**CASE, **override},
                                            headers={'Idempotency-Key': 'x'})
                self.assertEqual(response.status_code, 422)

    def test_full_happy_path_transition(self):
        for new_status, key in (('viewed', 'k1'), ('help_started', 'k2'), ('case_confirmed', 'k3'),
                                ('safe_action_confirmed', 'k4'), ('closed_demo', 'k5')):
            response = status(self.client, self.case_id, new_status, key, note_code='sandbox_confirmation')
            with self.subTest(status=new_status):
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['status'], new_status)
                self.assertFalse(response.json()['idempotent_replay'])
        detail = self.client.get(f'/api/operator/cases/{self.case_id}').json()
        self.assertEqual([event['status'] for event in detail['timeline']],
                         ['created', 'viewed', 'help_started', 'case_confirmed',
                          'safe_action_confirmed', 'closed_demo'])
        self.assertEqual(detail['status'], 'closed_demo')

    def test_idempotent_replay_and_payload_conflict(self):
        first = status(self.client, self.case_id, 'viewed', 'same-key')
        second = status(self.client, self.case_id, 'viewed', 'same-key')
        self.assertTrue(second.json()['idempotent_replay'])
        self.assertEqual(first.json()['updated_at'], second.json()['updated_at'])
        conflict = status(self.client, self.case_id, 'help_started', 'same-key')
        self.assertEqual(conflict.status_code, 409)

    def test_illegal_transition_is_409(self):
        status(self.client, self.case_id, 'viewed', 'a')
        skipped = status(self.client, self.case_id, 'safe_action_confirmed', 'b')
        self.assertEqual(skipped.status_code, 409)
        self.assertIn('not an allowed operator transition', skipped.json()['detail'])
        self.assertEqual(self.client.get(f'/api/operator/cases/{self.case_id}').json()['status'], 'viewed')

    def test_terminal_status_cannot_be_left(self):
        for new_status, key in (('viewed', 'a'), ('closed_demo', 'b')):
            status(self.client, self.case_id, new_status, key)
        self.assertEqual(status(self.client, self.case_id, 'help_started', 'c').status_code, 409)

    def test_free_text_and_bad_vocabulary_are_refused(self):
        for body in ({'note_code': 'money returned'}, {'note_code': 'OTP verified'},
                     {'actor_role': 'admin'}, {'status': 'escalated_to_hq'}):
            with self.subTest(body=body):
                response = self.client.post(f'/api/operator/cases/{self.case_id}/status', json=body,
                                            headers={'Idempotency-Key': 'z'})
                self.assertEqual(response.status_code, 422)

    def test_missing_key_and_unknown_case(self):
        self.assertEqual(self.client.post(f'/api/operator/cases/{self.case_id}/status',
                                          json={'status': 'viewed'}).status_code, 400)
        self.assertEqual(status(self.client, 'case_0000000000000000', 'viewed', 'k').status_code, 404)
        self.assertEqual(self.client.get('/api/operator/cases/case_0000000000000000').status_code, 404)

    def test_filters(self):
        self.client.post('/api/operator/cases', json={**CASE, 'subject_pseudonym': 'sub_00000000cafe0002',
                                                        'scenario_code': 'demo_family_collection',
                                                        'level': 'GREEN', 'episode_class': 'legitimate_negative'},
                         headers={'Idempotency-Key': 'second'})
        for query, expected in (('', 2), ('?level=RED', 1), ('?episode_class=legitimate_negative', 1),
                                ('?status=created', 2), ('?status=closed_demo', 0),
                                ('?experiment_arm=control', 0), ('?created_from=2027-01-01T00:00:00Z', 0)):
            with self.subTest(query=query):
                self.assertEqual(self.client.get(f'/api/operator/cases{query}').json()['count'], expected)
        self.assertEqual(self.client.get('/api/operator/cases?status=bogus').status_code, 422)

    def test_metrics_are_undefined_not_zero_without_denominators(self):
        metrics = self.client.get('/api/operator/metrics').json()
        self.assertEqual(metrics['total_cases'], 1)
        self.assertIsNone(metrics['legitimate_negative_alert_rate'])
        self.assertEqual(metrics['cases_by_arm'], {'control': 0, 'treatment': 0, 'none': 1})
        self.assertEqual(metrics['sandbox_notice'], SANDBOX_BANNER)
        self.assertTrue(metrics['limitations'])
        self.assertIn('sandbox_confirmation', metrics['allowlisted_note_codes'])

    def test_status_machine_is_served(self):
        machine = self.client.get('/api/operator/status-machine').json()
        self.assertEqual(len(machine['statuses']), 8)
        self.assertEqual(machine['transitions']['closed_demo'], [])
        self.assertIn('client accused', machine['forbidden_notes'])

    def test_operator_page_is_served_locally(self):
        page = self.client.get('/operator')
        self.assertEqual(page.status_code, 200)
        self.assertIn('operator.js', page.text)


if __name__ == '__main__':
    unittest.main()