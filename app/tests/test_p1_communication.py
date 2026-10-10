"""Communication layer: one decision, then a language. Integration level."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from anti_drop_ml.evaluation.runner import load_episodes  # noqa: E402
from scripts.generate_synthetic_fixtures import BASE_AT, _small_inbound, ref, transaction  # noqa: E402

FLAGS = ('ANTI_DROP_DEMO_MODE', 'ANTI_DROP_EXPERIMENT_ENABLED', 'ANTI_DROP_EXPERIMENT_ALLOW_DRAFT_TREATMENT',
         'ANTI_DROP_OPERATOR_LOG')
P1_DATASET = Path(__file__).resolve().parent.parent / 'fixtures' / 'episodes' / 'all_episodes_p1.jsonl'
SUBJECT = 'sub_00000000cafe0001'


def risk_snapshot() -> dict:
    return {
        'schema_version': 'RiskSnapshotV1',
        'subject_ref': SUBJECT,
        'analysis_at': BASE_AT.isoformat(),
        'timezone_policy': 'normalize_to_utc',
        'transactions': _small_inbound(5) + [transaction(9, minutes=2, direction='out', amount=1_400_000)],
        'metadata': {'dataset_version': 'demo', 'label_source': 'synthetic_placeholder',
                     'episode_class': 'risk', 'is_holdout': False},
    }


def quiet_snapshot() -> dict:
    return {
        'schema_version': 'RiskSnapshotV1',
        'subject_ref': SUBJECT,
        'analysis_at': BASE_AT.isoformat(),
        'timezone_policy': 'normalize_to_utc',
        'transactions': [transaction(0, minutes=300, kind='other', amount=50_000)],
        'metadata': {'dataset_version': 'demo', 'label_source': 'synthetic_placeholder',
                     'episode_class': 'normal', 'is_holdout': False},
    }


class CommunicationTestCase(unittest.TestCase):
    def setUp(self):
        for name in FLAGS:
            os.environ.pop(name, None)
        os.environ['ANTI_DROP_DEMO_MODE'] = 'true'
        self.app = __import__('main').app
        self.client = TestClient(self.app, client=('127.0.0.1', 51234))

    def tearDown(self):
        for name in FLAGS:
            os.environ.pop(name, None)

    def evaluate(self, locale='ru-RU', snapshot=None, **extra):
        body = {'snapshot': snapshot or risk_snapshot(), 'preferred_locale': locale,
                'subject_pseudonym': SUBJECT, **extra}
        return self.client.post('/api/v1/communication/evaluate', json=body)


class TestDecideThenTranslate(CommunicationTestCase):
    def test_locale_never_changes_the_score(self):
        ru = self.evaluate('ru-RU').json()
        uz = self.evaluate('uz-UZ').json()
        self.assertEqual(ru['decision']['score'], uz['decision']['score'])
        self.assertEqual(ru['decision']['level'], uz['decision']['level'])
        self.assertEqual(ru['decision']['evaluation_id'], uz['decision']['evaluation_id'])
        self.assertEqual(ru['decision']['rule_version'], uz['decision']['rule_version'])
        self.assertEqual(uz['warning']['locale'], 'uz-UZ')

    def test_response_states_that_language_does_not_affect_the_score(self):
        for locale in ('ru-RU', 'uz-UZ'):
            note = self.evaluate(locale).json()['language_note']
            with self.subTest(locale=locale):
                self.assertFalse(note['language_affects_score'])
                self.assertEqual(note['requested_locale'], locale)

    def test_fallback_is_reported_for_the_target_locale(self):
        ru = self.evaluate('ru-RU').json()['warning']
        uz = self.evaluate('uz-UZ').json()['warning']
        self.assertEqual(ru['used_fallback_keys'], [])
        self.assertIn('privacy.notice', uz['used_fallback_keys'])
        self.assertIsNotNone(uz['draft_badge'])
        self.assertEqual(ru['template_status'], 'draft')

    def test_green_decision_produces_no_warning(self):
        body = self.evaluate(snapshot=quiet_snapshot()).json()
        self.assertEqual(body['decision']['level'], 'GREEN')
        self.assertIsNone(body['warning'])

    def test_warning_carries_every_disclaimer(self):
        warning = self.evaluate().json()['warning']
        for field in ('title', 'body', 'cta', 'sandbox_notice', 'legal_disclaimer', 'privacy_notice'):
            with self.subTest(field=field):
                self.assertTrue(warning[field])
        self.assertTrue(warning['score_is_not_probability'])

    def test_response_is_marked_synthetic_and_non_banking(self):
        body = self.evaluate().json()
        self.assertTrue(body['sandbox'])
        self.assertTrue(body['not_a_banking_action'])

    def test_unknown_locale_and_bad_subject_are_refused(self):
        self.assertEqual(self.evaluate('xx-XX').status_code, 422)
        self.assertEqual(self.client.post('/api/v1/communication/evaluate',
                                          json={'snapshot': risk_snapshot(), 'preferred_locale': 'ru-RU',
                                                'subject_pseudonym': '+79990000000'}).status_code, 422)

    def test_language_cannot_be_smuggled_into_the_snapshot(self):
        payload = risk_snapshot()
        payload['language'] = 'uz-UZ'
        self.assertEqual(self.evaluate('ru-RU', snapshot=payload).status_code, 422)


class TestExperimentIntegration(CommunicationTestCase):
    def test_experiment_is_off_by_default(self):
        body = self.evaluate().json()
        self.assertFalse(body['experiment']['enabled'])
        self.assertIsNone(body['experiment']['assignment'])
        self.assertEqual(body['warning']['locale'], 'ru-RU')

    def test_treatment_stays_control_while_the_translation_is_draft(self):
        os.environ['ANTI_DROP_EXPERIMENT_ENABLED'] = 'true'
        body = self.evaluate().json()
        self.assertTrue(body['experiment']['enabled'])
        self.assertFalse(body['experiment']['treatment_available'])
        self.assertIn('draft', body['experiment']['blocked_reason'])
        self.assertEqual(body['experiment']['assignment']['arm'], 'control')
        self.assertEqual(body['warning']['locale'], 'ru-RU')

    def test_draft_override_still_requires_the_explicit_flag(self):
        os.environ['ANTI_DROP_EXPERIMENT_ENABLED'] = 'true'
        os.environ['ANTI_DROP_EXPERIMENT_ALLOW_DRAFT_TREATMENT'] = 'true'
        treatment = self.evaluate().json()
        self.assertIsNotNone(treatment['experiment']['assignment'])
        self.assertFalse(treatment['experiment']['treatment_available'])
        self.assertEqual(treatment['warning']['score_is_not_probability'], True)
        # Whether the arm is control or treatment, the score must be identical.
        self.assertEqual(treatment['decision']['score'],
                         self.evaluate('ru-RU').json()['decision']['score'])

    def test_assignment_events_reach_the_local_sink(self):
        with tempfile.TemporaryDirectory() as folder:
            os.environ['ANTI_DROP_EXPERIMENT_ENABLED'] = 'true'
            os.environ['ANTI_DROP_OPERATOR_LOG'] = str(Path(folder) / 'events.jsonl')
            body = self.evaluate().json()
            self.assertEqual(body['event_log']['sink'], 'local_jsonl')
            self.assertGreater(body['event_log']['event_count'], 0)
            types = {event['event_type'] for event in body['event_log']['events']}
            self.assertIn('experiment_assigned', types)
            self.assertIn('template_rendered', types)
            self.assertIn('alert_delivered', types)
            for event in body['event_log']['events']:
                with self.subTest(event=event['event_type']):
                    self.assertEqual(event['rule_version'], body['decision']['rule_version'])
                    self.assertEqual(event['evaluation_id'], body['decision']['evaluation_id'])

    def test_no_sink_configured_is_reported_not_hidden(self):
        os.environ['ANTI_DROP_EXPERIMENT_ENABLED'] = 'true'
        body = self.evaluate().json()
        self.assertEqual(body['event_log']['sink'], 'disabled')
        self.assertEqual(body['event_log']['event_count'], 0)


class TestCatalogsAndPreview(CommunicationTestCase):
    def test_locales_endpoint_is_honest(self):
        body = self.client.get('/api/locales').json()
        self.assertEqual(body['schema_version'], 'LocaleCatalogV1')
        self.assertEqual(body['control_locale'], 'ru-RU')
        self.assertEqual(body['target_locale'], 'uz-UZ')
        self.assertEqual({row['locale'] for row in body['locales']}, {'ru-RU', 'uz-UZ'})
        for pack in body['locales']:
            with self.subTest(locale=pack['locale']):
                self.assertEqual(pack['status'], 'draft')
                self.assertIsNotNone(pack['draft_badge'])
                self.assertTrue(pack['synthetic'])
        self.assertEqual(body['load_errors'], {})

    def test_templates_endpoint_lists_approval_state(self):
        body = self.client.get('/api/v1/communication/templates').json()
        self.assertTrue(body['language_does_not_change_score'])
        templates = {row['template_id']: row for row in body['templates']}
        self.assertIn('warning_ru_control_v1', templates)
        self.assertIn('warning_uz_treatment_v1', templates)
        for template in templates.values():
            with self.subTest(template=template['template_id']):
                self.assertFalse(template['is_approved'])
                self.assertIsNone(template['approved_at'])

    def test_preview_is_badged_and_assigns_nothing(self):
        body = self.client.post('/api/v1/communication/preview', params={'level': 'RED'}).json()
        self.assertTrue(body['preview'])
        self.assertEqual(body['warning']['template_id'], 'warning_uz_treatment_v1')
        self.assertEqual(body['warning']['template_status'], 'draft')
        self.assertIsNotNone(body['warning']['draft_badge'])
        self.assertTrue(body['language_does_not_change_score'])
        self.assertNotIn('assignment', body)

    def test_preview_of_an_unbound_locale_is_refused(self):
        self.assertEqual(self.client.post('/api/v1/communication/preview',
                                          params={'level': 'RED', 'template_id': 'warning_tg_v1'}).status_code, 422)

    def test_event_endpoint_requires_a_sink_and_a_valid_event(self):
        self.assertEqual(self.client.post('/api/v1/communication/events', json={}).status_code, 503)
        with tempfile.TemporaryDirectory() as folder:
            os.environ['ANTI_DROP_OPERATOR_LOG'] = str(Path(folder) / 'events.jsonl')
            good = {
                'event_type': 'alert_viewed',
                'timestamp': '2026-10-08T12:00:00Z',
                'evaluation_id': 'a' * 64,
                'rule_version': '2026-10-08.p1',
                'threshold_version': 'thresholds-2026.10.08-red50-yellow25',
            }
            self.assertEqual(self.client.post('/api/v1/communication/events', json=good).status_code, 202)
            bad = {**good, 'phone': '+79990000000'}
            self.assertEqual(self.client.post('/api/v1/communication/events', json=bad).status_code, 422)


class TestNoFeatureFlagLeaksIntoRisk(CommunicationTestCase):
    def test_risk_endpoint_is_unaffected_by_the_communication_layer(self):
        os.environ['ANTI_DROP_EXPERIMENT_ENABLED'] = 'true'
        os.environ['ANTI_DROP_ADVISORY_ENABLED'] = 'true'
        first = self.client.post('/api/v1/risk/evaluate', json=risk_snapshot()).json()
        self.evaluate('uz-UZ')
        self.client.post('/api/v1/communication/preview', params={'level': 'RED'})
        second = self.client.post('/api/v1/risk/evaluate', json=risk_snapshot()).json()
        self.assertEqual(first, second)
        self.assertEqual(first['score_interpretation'], 'deterministic_rule_score_not_probability')

    def test_evaluation_pipeline_is_still_green_with_the_p1_dataset(self):
        from anti_drop_ml.evaluation.runner import run_evaluation

        episodes = load_episodes(P1_DATASET)
        self.assertGreater(len(episodes), 50)
        with tempfile.TemporaryDirectory() as folder:
            metrics = run_evaluation(P1_DATASET, Path(folder), skip_ablation=True, write_holdout=False)
            self.assertTrue(metrics['language_invariance']['all_rejected'])
            self.assertTrue(metrics['overall']['total_episodes'] > 0)
            self.assertIsNotNone(json.dumps(metrics)[:10])


if __name__ == '__main__':
    unittest.main()