"""P1 event contract: the closed allowlist is the PII boundary."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import ValidationError  # noqa: E402

from anti_drop_ml.adapter import RULE_VERSION, THRESHOLD_VERSION  # noqa: E402
from anti_drop_ml.event_log import append_event, read_events  # noqa: E402
from anti_drop_ml.events import ProductEventV1  # noqa: E402
from src.experiments import EXPERIMENT_EVENT_TYPES, ExperimentConfigError, build_event  # noqa: E402

EVALUATION_ID = 'a' * 64
AT = '2026-10-08T12:00:00Z'

PII_FIELDS = ['phone', 'full_name', 'passport', 'card_number', 'otp', 'counterparty_name',
              'transaction_text', 'location', 'biometrics', 'email', 'address', 'inn', 'snils']


def base_event(**overrides) -> dict:
    payload = {
        'event_id': '00000000-0000-4000-8000-000000000001',
        'event_type': 'template_rendered',
        'timestamp': AT,
        'evaluation_id': EVALUATION_ID,
        'rule_version': RULE_VERSION,
        'threshold_version': THRESHOLD_VERSION,
    }
    payload.update(overrides)
    return payload


class TestEventAllowlist(unittest.TestCase):
    def test_every_documented_event_type_is_allowed(self):
        for kind in EXPERIMENT_EVENT_TYPES:
            with self.subTest(kind=kind):
                ProductEventV1.model_validate(base_event(event_type=kind))

    def test_unknown_event_type_is_refused(self):
        for kind in ('alert_sms_sent', 'payment_blocked', 'otp_verified', 'cashback_granted'):
            with self.subTest(kind=kind):
                with self.assertRaises(ValidationError):
                    ProductEventV1.model_validate(base_event(event_type=kind))

    def test_pii_fields_are_refused_at_top_level_and_nested(self):
        for field in PII_FIELDS:
            for nested in (False, True):
                with self.subTest(field=field, nested=nested):
                    payload = base_event()
                    if nested:
                        payload['metadata'] = {field: 'forbidden'}
                    else:
                        payload[field] = 'forbidden'
                    with self.assertRaises(ValidationError):
                        ProductEventV1.model_validate(payload)

    def test_raw_contact_values_cannot_ride_in_as_refs(self):
        for value in ('+79990000000', '79990000000', 'ivan@example.com'):
            with self.subTest(value=value):
                for field in ('subject_pseudonym', 'case_id'):
                    with self.assertRaises(ValidationError):
                        ProductEventV1.model_validate(base_event(**{field: value}))

    def test_outcome_and_metadata_vocabularies_are_closed(self):
        ProductEventV1.model_validate(base_event(outcome_code='rendered_draft_translation'))
        with self.assertRaises(ValidationError):
            ProductEventV1.model_validate(base_event(outcome_code='client_is_a_scammer'))
        ProductEventV1.model_validate(base_event(metadata={'template_status': 'draft', 'latency_ms': 12}))
        with self.assertRaises(ValidationError):
            ProductEventV1.model_validate(base_event(metadata={'template_status': 'blessed_by_legal'}))

    def test_experiment_and_template_vocabulary(self):
        ProductEventV1.model_validate(base_event(experiment_id='exp-warning-language-2026.10',
                                                  experiment_arm='treatment',
                                                  template_id='warning_uz_treatment_v1',
                                                  locale='uz-UZ', language='uz'))
        with self.assertRaises(ValidationError):
            ProductEventV1.model_validate(base_event(experiment_id='random-experiment'))
        with self.assertRaises(ValidationError):
            ProductEventV1.model_validate(base_event(experiment_arm='holdout'))
        with self.assertRaises(ValidationError):
            ProductEventV1.model_validate(base_event(template_id='Warning RU Control'))

    def test_naive_timestamp_is_refused(self):
        for value in ('2026-10-08T12:00:00', 'bad', 1764000000):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    ProductEventV1.model_validate(base_event(timestamp=value))


class TestEventBuilder(unittest.TestCase):
    def test_builder_enforces_the_experiment_vocabulary(self):
        event = build_event(event_type='experiment_assigned', evaluation_id=EVALUATION_ID,
                            rule_version=RULE_VERSION, threshold_version=THRESHOLD_VERSION,
                            experiment_id='exp-warning-language-2026.10', arm='control',
                            subject_pseudonym='sub_00000000aaaa0001', outcome_code='arm_control')
        self.assertEqual(event.experiment_arm, 'control')
        self.assertEqual(event.locale, None)
        with self.assertRaises(ExperimentConfigError):
            build_event(event_type='alert_sms_sent', evaluation_id=EVALUATION_ID,
                        rule_version=RULE_VERSION, threshold_version=THRESHOLD_VERSION)

    def test_locale_maps_to_the_legacy_language_code(self):
        event = build_event(event_type='language_selected', evaluation_id=EVALUATION_ID,
                            rule_version=RULE_VERSION, threshold_version=THRESHOLD_VERSION, locale='uz-UZ')
        self.assertEqual(event.locale, 'uz-UZ')
        self.assertEqual(event.language, 'uz')
        unknown = build_event(event_type='language_selected', evaluation_id=EVALUATION_ID,
                              rule_version=RULE_VERSION, threshold_version=THRESHOLD_VERSION, locale='de-DE')
        self.assertIsNone(unknown.language)


class TestLocalSink(unittest.TestCase):
    def test_valid_event_is_appended_and_readable(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'nested' / 'events.jsonl'
            stored = append_event(base_event(), path)
            self.assertIsNotNone(stored)
            self.assertTrue(path.is_file())
            rows = read_events(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['event_type'], 'template_rendered')

    def test_invalid_event_is_not_written(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'events.jsonl'
            self.assertIsNone(append_event(base_event(phone='+79990000000'), path))
            self.assertIsNone(append_event({'not': 'an event'}, path))
            self.assertIsNone(append_event(base_event(), None))
            self.assertFalse(path.exists())

    def test_truncated_final_line_is_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'events.jsonl'
            append_event(base_event(), path)
            with path.open('a', encoding='utf-8') as stream:
                stream.write('{"event_type": "trunc')
            rows = read_events(path)
            self.assertEqual(len(rows), 1)


if __name__ == '__main__':
    unittest.main()