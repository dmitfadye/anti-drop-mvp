"""Pre-transfer advisory: advisory only, never a payment decision."""
import json
import os
import sys
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from anti_drop_ml.contracts import RiskSnapshotV1  # noqa: E402
from scripts.generate_synthetic_fixtures import BASE_AT, _small_inbound, ref, snapshot, transaction  # noqa: E402
from src.advisory import (  # noqa: E402
    ADVISORY_NOTICE_EN,
    ADVISORY_NOTICE_RU,
    FORBIDDEN_ADVISORY_PHRASES,
    PlannedTransferAdvisoryV1,
    advise,
)

FLAG = 'ANTI_DROP_ADVISORY_ENABLED'


def advisory(history=None, amount=1_400_000, kind='transfer', at=BASE_AT, **overrides) -> dict:
    payload = {
        'schema_version': 'PlannedTransferAdvisoryV1',
        'subject_ref': ref('sub', 'advisory-demo'),
        'analysis_at': at,
        'history': history if history is not None else _small_inbound(5),
        'planned_transfer': {'planned_event_id': 'plan-1', 'requested_at': at, 'direction': 'out',
                             'type': kind, 'amount_minor': amount, 'currency': 'RUB',
                             'counterparty_ref': ref('cp', 'mule'), 'channel': 'mobile_app'},
    }
    payload.update(overrides)
    # The API takes JSON; the model accepts either form.
    return json.loads(json.dumps(payload, default=lambda value: value.isoformat()))


class TestContract(unittest.TestCase):
    def test_planned_event_is_allowed_only_in_advisory_mode(self):
        planned = PlannedTransferAdvisoryV1.model_validate(advisory())
        self.assertEqual(planned.analysis_mode, 'pre_transfer_advisory')
        self.assertEqual(len(planned.history), 5)
        # The ordinary snapshot path still rejects a future event.
        with self.assertRaises(ValidationError):
            RiskSnapshotV1.model_validate({**snapshot(_small_inbound(5), 'advisory-demo'),
                                           'allow_future_events': False,
                                           'transactions': [transaction(0, minutes=-5)]})

    def test_planned_transfer_must_not_appear_in_history(self):
        history = _small_inbound(5)
        history[0]['event_id'] = 'plan-1'
        with self.assertRaises(ValidationError):
            PlannedTransferAdvisoryV1.model_validate(advisory(history=history))

    def test_future_history_and_mixed_subjects_are_refused(self):
        future = _small_inbound(5)
        future[0]['occurred_at'] = (BASE_AT + timedelta(minutes=5)).isoformat()
        with self.subTest(case='future_history'):
            with self.assertRaises(ValidationError):
                PlannedTransferAdvisoryV1.model_validate(advisory(history=future))
        mixed = _small_inbound(5)
        mixed[0]['subject_ref'] = ref('sub', 'somebody-else')
        with self.subTest(case='mixed_subject'):
            with self.assertRaises(ValidationError):
                PlannedTransferAdvisoryV1.model_validate(advisory(history=mixed))

    def test_naive_analysis_at_and_zero_amount_are_refused(self):
        with self.assertRaises(ValidationError):
            PlannedTransferAdvisoryV1.model_validate(advisory(at='2026-10-08T12:00:00'))
        with self.assertRaises(ValidationError):
            PlannedTransferAdvisoryV1.model_validate(advisory(amount=0))

    def test_analysis_mode_is_not_overridable(self):
        with self.assertRaises(ValidationError):
            PlannedTransferAdvisoryV1.model_validate(advisory(analysis_mode='realtime'))


class TestAdvisoryBehaviour(unittest.TestCase):
    def test_result_is_advisory_only_and_does_no_banking_action(self):
        result = advise(advisory())
        self.assertEqual(result.status, 'advisory_only')
        self.assertEqual(result.banking_action, 'none')
        self.assertEqual(result.analysis_mode, 'pre_transfer_advisory')
        self.assertEqual(result.score_interpretation, 'deterministic_rule_score_not_probability')
        self.assertEqual(result.advisory_notice_ru, ADVISORY_NOTICE_RU)
        self.assertEqual(result.advisory_notice_en, ADVISORY_NOTICE_EN)
        self.assertTrue(result.synthetic)

    def test_planned_transfer_contributes_to_the_score(self):
        result = advise(advisory())
        self.assertEqual(result.level, 'RED')
        self.assertIn('large_outbound_after_inbound', result.planned_transfer_contribution)
        self.assertGreater(result.score, result.history_decision.score)

    def test_advisory_does_not_modify_completed_history(self):
        payload = advisory()
        history_before = len(payload['history'])
        result = advise(payload)
        self.assertEqual(len(payload['history']), history_before)
        self.assertEqual(result.history_decision.data_quality.future_events_excluded, 0)
        self.assertEqual(result.history_decision.status, 'ok')

    def test_legitimate_planned_transfer_is_not_red(self):
        history = [transaction(0, minutes=240, kind='salary', amount=6_000_000)]
        result = advise(advisory(history=history, amount=5_000_000, kind='cash_withdrawal'))
        self.assertNotEqual(result.level, 'RED', 'a salary withdrawal must not be warned as a drop pattern')

    def test_family_collection_history_is_not_red(self):
        history = _small_inbound(5, kind='family_collection')
        result = advise(advisory(history=history, amount=200_000))
        self.assertNotEqual(result.level, 'RED')

    def test_quiet_history_is_green(self):
        result = advise(advisory(history=[transaction(0, minutes=300, kind='other', amount=50_000)], amount=100_000))
        self.assertEqual(result.level, 'GREEN')

    def test_text_never_promises_a_block(self):
        for history, amount, kind in ((None, 1_400_000, 'transfer'), ([], 100_000, 'transfer')):
            result = advise(advisory(history=history, amount=amount, kind=kind))
            for field in ('message_ru', 'message_en', 'advisory_notice_ru', 'advisory_notice_en'):
                text = getattr(result, field).lower()
                with self.subTest(field=field, amount=amount):
                    for phrase in FORBIDDEN_ADVISORY_PHRASES:
                        self.assertNotIn(phrase, text)

    def test_advisory_id_is_stable(self):
        first = advise(advisory()).advisory_id
        second = advise(advisory()).advisory_id
        self.assertEqual(first, second)


class TestEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = __import__('main').app

    def setUp(self):
        os.environ.pop(FLAG, None)

    def tearDown(self):
        os.environ.pop(FLAG, None)

    def test_endpoint_is_off_by_default(self):
        client = TestClient(self.app, client=('127.0.0.1', 51234))
        self.assertEqual(client.post('/api/v1/risk/advisory', json=advisory()).status_code, 503)

    def test_endpoint_returns_advisory_only_when_enabled(self):
        os.environ[FLAG] = 'true'
        client = TestClient(self.app, client=('127.0.0.1', 51234))
        response = client.post('/api/v1/risk/advisory', json=advisory())
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['status'], 'advisory_only')
        self.assertEqual(body['banking_action'], 'none')
        self.assertIn('history_decision', body)

    def test_endpoint_validates_the_contract(self):
        os.environ[FLAG] = 'true'
        client = TestClient(self.app, client=('127.0.0.1', 51234))
        self.assertEqual(client.post('/api/v1/risk/advisory', json={}).status_code, 422)


if __name__ == '__main__':
    unittest.main()