"""Regression checks for selective P1 integration and authenticated boundaries."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from anti_drop_ml.evaluation.holdout import split_episodes, subject_bucket
from anti_drop_ml.evaluation.runner import load_episodes, run_evaluation
from anti_drop_ml.events import ProductEventV1
from src.experiments import build_event
from src.p1 import router

ROOT = Path(__file__).resolve().parent.parent
SUBJECT = 'sub_00000000cafe0001'
TOKEN = 'synthetic-test-credential-with-32-characters'


class TestP1Evaluation(unittest.TestCase):
    def test_multi_episode_subject_cannot_leak(self):
        subject = next(f'sub_{n:016x}' for n in range(100) if subject_bucket(f'sub_{n:016x}') < 30)
        now = datetime(2026, 10, 1, tzinfo=timezone.utc)
        episodes = [SimpleNamespace(subject_ref=subject, episode_id=f'ep_{i:016x}',
                    payload=SimpleNamespace(analysis_at=now + timedelta(days=i))) for i in range(3)]
        split = split_episodes(episodes)
        self.assertEqual(len(split.holdout), 3)
        self.assertEqual(split.development, [])
        self.assertFalse(split.manifest['invariants']['globally_time_disjoint'])

    def test_current_detector_evidence_marks_unsupported_ablation(self):
        with tempfile.TemporaryDirectory() as folder:
            result = run_evaluation(ROOT / 'fixtures/episodes/all_episodes_p1.jsonl', Path(folder))
            self.assertEqual(result['manifest']['number_of_episodes'], 81)
            self.assertIn('NOT RUN', result['manifest']['ablation_status'])
            self.assertFalse((Path(folder) / 'rule_ablation.csv').exists())
            manifest = json.loads((Path(folder) / 'holdout_manifest.json').read_text(encoding='utf-8'))
            development = load_episodes(Path(folder) / 'holdout_development.jsonl')
            holdout = load_episodes(Path(folder) / 'holdout_holdout.jsonl')
            self.assertFalse({e.subject_ref for e in development} & {e.subject_ref for e in holdout})
            self.assertTrue(manifest['invariants']['subject_disjoint'])


class TestP1Authentication(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'SANDBOX_TOKENS': json.dumps({TOKEN: SUBJECT}),
            'ANTI_DROP_EXPERIMENT_ENABLED': 'false', 'ANTI_DROP_OPERATOR_LOG': '',
            'ANTI_DROP_DEMO_MODE': 'true', 'ANTI_DROP_ADVISORY_ENABLED': 'false'})
        self.env.start()
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.headers = {'Authorization': f'Bearer {TOKEN}'}
        self.snapshot = load_episodes(ROOT / 'fixtures/episodes/all_episodes_p1.jsonl')[0].payload.model_dump(mode='json')
        self.snapshot['subject_ref'] = SUBJECT
        for transaction in self.snapshot['transactions']:
            transaction['subject_ref'] = SUBJECT

    def tearDown(self):
        self.env.stop()

    def test_authenticated_subject_is_required_and_cannot_be_forged(self):
        body = {'snapshot': self.snapshot, 'preferred_locale': 'ru-RU'}
        self.assertEqual(self.client.post('/api/v1/communication/evaluate', json=body).status_code, 401)
        body['subject_pseudonym'] = 'sub_aaaaaaaaaaaaaaaa'
        self.assertEqual(self.client.post('/api/v1/communication/evaluate', json=body, headers=self.headers).status_code, 403)

    def test_language_does_not_change_risk(self):
        responses = [self.client.post('/api/v1/communication/evaluate', headers=self.headers,
            json={'snapshot': self.snapshot, 'preferred_locale': locale}) for locale in ('ru-RU', 'uz-UZ')]
        self.assertTrue(all(response.status_code == 200 for response in responses))
        first, second = [response.json() for response in responses]
        self.assertEqual(first['decision']['evaluation_id'], second['decision']['evaluation_id'])
        self.assertEqual(first['decision']['score'], second['decision']['score'])

    def event(self, subject=SUBJECT):
        event = build_event(event_type='alert_viewed', evaluation_id='a' * 64,
            rule_version='test', threshold_version='test', subject_pseudonym=subject,
            outcome_code='ok')
        # Validate the serialized round trip as template versions changed in P2.
        return ProductEventV1.model_validate(event.model_dump(mode='json')).model_dump(mode='json')

    def test_event_write_checks_owner_and_evaluation_and_fails_on_sink_error(self):
        with patch.dict(os.environ, {'ANTI_DROP_OPERATOR_LOG': 'synthetic.jsonl'}):
            response = self.client.post('/api/v1/communication/events', json=self.event('sub_aaaaaaaaaaaaaaaa'), headers=self.headers)
            self.assertEqual(response.status_code, 403)
            with patch('src.communication.read_evaluation') as read, patch('src.communication.append_event', return_value=None):
                response = self.client.post('/api/v1/communication/events', json=self.event(), headers=self.headers)
                self.assertEqual(response.status_code, 503)
                read.assert_called_once_with('a' * 64, SUBJECT)


if __name__ == '__main__':
    unittest.main()
