"""Blinded scoring: the participant-facing export must not reveal the arm."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import ValidationError  # noqa: E402

from src.experiments import (  # noqa: E402
    BLINDED_COLUMNS,
    UNBLINDED_COLUMNS,
    BlindedScoringRecordV1,
    ExperimentConfigError,
    analyze_experiment,
    analyze_arm,
    blind_record,
    build_blinding_map,
    power_plan,
    read_csv,
    unblind,
    write_csv,
)

EXPERIMENT_ID = 'exp-warning-language-2026.10'
TEMPLATES = [
    ('warning_ru_control_v1', 'ru-RU', 'control', 'transit_red'),
    ('warning_uz_treatment_v1', 'uz-UZ', 'treatment', 'transit_red'),
    ('warning_ru_control_yellow_v1', 'ru-RU', 'control', 'salary_cash_yellow'),
    ('warning_uz_treatment_yellow_v1', 'uz-UZ', 'treatment', 'salary_cash_yellow'),
]
AT = '2026-10-20T09:00:00Z'


def raw(index: int, template_id: str, arm: str, *, action: str = 'safe_action_chosen',
        understood: bool = True, accused: bool = False, ms: int = 12000, risk_level: str = 'RED') -> dict:
    return {
        'template_id': template_id,
        'participant_pseudonym': f'sub_{index:016x}',
        'scenario_id': 'transit_red' if risk_level == 'RED' else 'salary_cash_yellow',
        'presentation_order': 1,
        'risk_level': risk_level,
        'action_choice': action,
        'time_to_action_ms': ms,
        'confidence': 4,
        'felt_accused': accused,
        'understood_next_step': understood,
        'comments_no_pii': '',
        'collected_at': AT,
        '_arm': arm,
    }


class TestBlinding(unittest.TestCase):
    def setUp(self):
        self.mapping = build_blinding_map(TEMPLATES)

    def test_display_ids_do_not_leak_arm_or_locale(self):
        for key, entry in self.mapping.items():
            with self.subTest(key=key):
                self.assertTrue(key.startswith('blin_'))
                self.assertNotIn(entry['arm'], key)
                self.assertNotIn(entry['locale'], key)

    def test_blinded_record_hides_arm_template_and_locale(self):
        blinded = blind_record(raw(1, 'warning_uz_treatment_v1', 'treatment'), self.mapping)
        for forbidden in ('arm', 'template_id', 'locale', 'treatment', 'uz-UZ'):
            self.assertNotIn(forbidden, blinded)
        self.assertEqual(set(blinded) - set(BLINDED_COLUMNS), set())
        record = BlindedScoringRecordV1.model_validate(blinded)
        self.assertTrue(record.display_template_id.startswith('blin_'))

    def test_map_is_stable_across_runs(self):
        self.assertEqual(build_blinding_map(TEMPLATES), self.mapping)

    def test_unblind_restores_arm_and_locale(self):
        blinded = blind_record(raw(1, 'warning_uz_treatment_v1', 'treatment'), self.mapping)
        rows = unblind([blinded], list(self.mapping.values()))
        self.assertEqual(rows[0]['arm'], 'treatment')
        self.assertEqual(rows[0]['locale'], 'uz-UZ')
        self.assertEqual(set(UNBLINDED_COLUMNS) - set(rows[0]), set())

    def test_unknown_template_or_display_id_is_refused(self):
        with self.assertRaises(ExperimentConfigError):
            blind_record(raw(1, 'warning_unknown_v1', 'control'), self.mapping)
        broken = dict(blind_record(raw(1, 'warning_ru_control_v1', 'control'), self.mapping))
        broken['display_template_id'] = 'blin_ffffffffffffffff'
        with self.assertRaises(ExperimentConfigError):
            unblind([broken], list(self.mapping.values()))

    def test_comments_cannot_carry_phone_shaped_digits(self):
        for comment in ('позвоните +7 999 000 00 00', 'карта 4276380012345678', '89161234567'):
            with self.subTest(comment=comment):
                blinded = blind_record(raw(1, 'warning_ru_control_v1', 'control'), self.mapping)
                with self.assertRaises(ValidationError):
                    BlindedScoringRecordV1.model_validate({**blinded, 'comments_no_pii': comment})
        blinded = blind_record(raw(1, 'warning_ru_control_v1', 'control'), self.mapping)
        BlindedScoringRecordV1.model_validate({**blinded, 'comments_no_pii': 'не понял текст, нужен перевод'})


class TestAnalysisRefusesClaims(unittest.TestCase):
    def build_rows(self, per_arm: int = 5) -> list[dict]:
        mapping = build_blinding_map(TEMPLATES)
        blinded = []
        for index in range(per_arm):
            blinded.append(blind_record(raw(
                index + 1, 'warning_ru_control_v1', 'control',
                action='safe_action_chosen' if index % 2 == 0 else 'unsafe_action_chosen',
                understood=index % 2 == 0, accused=index % 3 == 0, ms=20000 + index * 1000), mapping))
            blinded.append(blind_record(raw(index + 101, 'warning_uz_treatment_v1', 'treatment',
                                           understood=True, ms=9000 + index * 500), mapping))
        return unblind(blinded, list(mapping.values()))

    def test_analysis_reports_intervals_and_refuses_the_claim(self):
        rows = self.build_rows()
        analysis = analyze_experiment(rows, declared_powered_n=0)
        self.assertFalse(analysis['claim_permitted'])
        self.assertIn('No uplift claim', analysis['claim_text'])
        self.assertTrue(any('NOT POWERED' in warning for warning in analysis['warnings']))
        self.assertTrue(any('exploratory' in warning.lower() for warning in analysis['warnings']))
        for arm in ('control', 'treatment'):
            with self.subTest(arm=arm):
                stats = analysis['arms'][arm]
                self.assertEqual(stats['n'], 5)
                self.assertIsNotNone(stats['understanding_rate']['wilson_95_ci'])
                self.assertIsNotNone(stats['time_to_action_ms']['p90'])
        self.assertGreater(analysis['arm_difference']['difference_pp'], 0)

    def test_powered_declaration_is_honoured_and_reflected(self):
        rows = self.build_rows(per_arm=2)
        analysis = analyze_experiment(rows, declared_powered_n=400)
        self.assertEqual(analysis['declared_powered_n_per_arm'], 400)
        self.assertTrue(any('NOT POWERED' in warning for warning in analysis['warnings']))

    def test_empty_arm_yields_undefined_not_zero(self):
        rows = [row for row in self.build_rows() if row['arm'] == 'control']
        analysis = analyze_experiment(rows)
        self.assertEqual(analysis['arms']['treatment']['n'], 0)
        self.assertIsNone(analysis['arms']['treatment']['safe_action_rate']['value'])
        self.assertIsNone(analysis['arm_difference']['difference_pp'])
        self.assertIn('undefined', analysis['arm_difference']['interpretation'])

    def test_empty_input_is_handled(self):
        stats = analyze_arm([])
        self.assertEqual(stats['n'], 0)
        self.assertIsNone(stats['safe_action_rate']['value'])
        self.assertIsNone(stats['time_to_action_ms']['p90'])

    def test_unsafe_and_declined_actions_are_distinguished(self):
        mapping = build_blinding_map(TEMPLATES)
        blinded = [
            blind_record(raw(1, 'warning_uz_treatment_v1', 'treatment', action='unsafe_action_chosen'), mapping),
            blind_record(raw(2, 'warning_uz_treatment_v1', 'treatment', action='declined_advisory'), mapping),
            blind_record(raw(3, 'warning_uz_treatment_v1', 'treatment', action='accepted_advisory'), mapping),
        ]
        stats = analyze_arm(unblind(blinded, list(mapping.values())))
        self.assertEqual(stats['safe_action_rate']['value'], 1 / 3)
        self.assertEqual(stats['safe_action_rate']['numerator'], 1)


class TestPowerPlan(unittest.TestCase):
    def test_plan_is_labelled_planning_only(self):
        plan = power_plan(0.30, 8)
        self.assertEqual(plan['status'], 'PLANNING_ONLY_NOT_A_PILOT_SAMPLE_SIZE')
        self.assertGreater(plan['required_n_per_arm'], 0)
        self.assertEqual(plan['required_n_total'], plan['required_n_per_arm'] * 2)
        self.assertTrue(any('ASSUMPTION' in note for note in plan['assumptions']))

    def test_dropout_increases_the_requirement(self):
        self.assertGreater(power_plan(0.30, 8, dropout_rate=0.2)['required_n_per_arm'],
                           power_plan(0.30, 8)['required_n_per_arm'])


class TestExportShape(unittest.TestCase):
    def test_blank_template_has_header_only(self):
        mapping = build_blinding_map(TEMPLATES)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'blinded.csv'
            write_csv(path, [], BLINDED_COLUMNS)
            self.assertEqual(path.read_text(encoding='utf-8').strip(),
                             ','.join(BLINDED_COLUMNS))
            self.assertEqual(read_csv(path), [])
        self.assertEqual(len(mapping), 4)

    def test_csv_roundtrip_keeps_blinded_fields(self):
        mapping = build_blinding_map(TEMPLATES)
        blinded = [blind_record(raw(index, 'warning_ru_control_v1', 'control'), mapping) for index in range(3)]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'blinded.csv'
            write_csv(path, blinded, BLINDED_COLUMNS)
            with path.open(encoding='utf-8', newline='') as stream:
                header = next(csv.reader(stream))
            self.assertEqual(header, BLINDED_COLUMNS)
            rows = read_csv(path)
            self.assertEqual(len(rows), 3)
            self.assertNotIn('arm', rows[0])


if __name__ == '__main__':
    unittest.main()