"""Financial model tests: negative margins are computed, payback is conditional."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.finance import (  # noqa: E402
    DISCLAIMERS,
    PARAMETER_NAMES,
    PINNED_ZERO,
    Assumption,
    FinancialModelError,
    break_even,
    compute,
    load_assumptions,
    missing_evidence,
    scenario_table,
    sensitivity,
    write_reports,
)

CONFIG = Path(__file__).resolve().parent.parent / 'configs' / 'financial_assumptions.json'


def assumptions(**overrides) -> dict:
    base = {
        'n_clients': Assumption(1000, 'assumption', 'low'),
        'q_risk_episodes_per_client_year': Assumption(0.01, 'assumption', 'low'),
        'delta_incremental_prevention': Assumption(0.1, 'assumption', 'low'),
        'l_bank_rubles_per_episode': Assumption(50000, 'unknown', 'low'),
        'contacts_per_client_year': Assumption(0.1, 'assumption', 'low'),
        'minutes_saved_per_contact': Assumption(5, 'assumption', 'low'),
        'cost_per_minute_rubles': Assumption(400, 'assumption', 'low'),
        'false_alerts_per_client_year': Assumption(0.05, 'evaluation', 'low'),
        'call_share_after_false_alert': Assumption(0.3, 'assumption', 'low'),
        'handling_cost_per_contact_rubles': Assumption(500, 'assumption', 'low'),
        'k_initial_cost': Assumption(1000, 'assumption', 'low'),
        'opex_annual': Assumption(900, 'assumption', 'low'),
    }
    for name, value in overrides.items():
        base[name] = value if isinstance(value, Assumption) else Assumption(float(value), 'assumption', 'low')
    return base


class TestFormulas(unittest.TestCase):
    def test_annual_margin_matches_the_documented_formula(self):
        params = assumptions()
        result = compute(params)
        expected_fraud = 1000 * 0.01 * 0.1 * 50000
        expected_support = 1000 * 0.1 * 5 * 400
        expected_false_alert = 1000 * 0.05 * 0.3 * 500
        self.assertAlmostEqual(result['fraud_benefit'], expected_fraud)
        self.assertAlmostEqual(result['support_benefit'], expected_support)
        self.assertAlmostEqual(result['false_alert_cost'], expected_false_alert)
        self.assertAlmostEqual(result['annual_margin'],
                               expected_fraud + expected_support - expected_false_alert - 900)
        self.assertAlmostEqual(result['year1_net'], result['annual_margin'] - 1000)

    def test_unproven_money_stays_at_zero(self):
        result = compute(assumptions())
        for name in PINNED_ZERO:
            self.assertEqual(result[name], 0.0, f'{name} must default to zero until proven')

    def test_negative_margin_is_computed_not_hidden(self):
        params = assumptions(opex_annual=10_000_000)
        result = compute(params)
        self.assertLess(result['annual_margin'], 0)
        self.assertLess(result['year1_net'], result['annual_margin'])
        self.assertIsNone(result['simple_payback_months'], 'negative margin must not produce a payback')
        self.assertIsNotNone(result['year1_roi'], 'ROI is still defined when the denominator is positive')
        self.assertLess(result['year1_roi'], 0)

    def test_payback_only_for_positive_margin(self):
        profitable = compute(assumptions(delta_incremental_prevention=0.9))
        self.assertGreater(profitable['annual_margin'], 0)
        self.assertGreater(profitable['simple_payback_months'], 0)
        breakeven = compute(assumptions(opex_annual=2_300_000))
        self.assertIsNone(breakeven['simple_payback_months'])

    def test_division_by_zero_is_protected(self):
        params = assumptions(k_initial_cost=0, opex_annual=0, false_alerts_per_client_year=0)
        result = compute(params)
        self.assertIsNone(result['year1_roi'])
        self.assertEqual(result['year1_net'], result['annual_margin'])

    def test_multipliers_change_only_the_named_parameter(self):
        base = compute(assumptions())
        scaled = compute(assumptions(), {'n_clients': 2.0})
        self.assertAlmostEqual(scaled['fraud_benefit'], base['fraud_benefit'] * 2)
        self.assertAlmostEqual(scaled['support_benefit'], base['support_benefit'] * 2)


class TestScenariosAndSensitivity(unittest.TestCase):
    def test_three_scenarios_with_conservative_never_above_base(self):
        rows = {row['scenario']: row for row in scenario_table(assumptions())}
        self.assertEqual(set(rows), {'conservative', 'base', 'optimistic'})
        self.assertLessEqual(rows['conservative']['annual_margin'], rows['base']['annual_margin'])
        self.assertLessEqual(rows['base']['annual_margin'], rows['optimistic']['annual_margin'])

    def test_shipped_config_base_case_is_not_a_comfortable_profit(self):
        rows = {row['scenario']: row for row in scenario_table(load_assumptions(CONFIG))}
        self.assertLess(rows['base']['annual_margin'], 0, 'the shipped base case must stay near break-even')
        self.assertLess(rows['conservative']['annual_margin'], rows['base']['annual_margin'])
        self.assertIsNone(rows['base']['simple_payback_months'])

    def test_sensitivity_is_ranked_and_never_double_counts(self):
        rows = sensitivity(assumptions())
        swings = [row['swing_rubles'] for row in rows if row['swing_rubles'] is not None]
        self.assertEqual(swings, sorted(swings, reverse=True))
        self.assertEqual(len(rows), len(PARAMETER_NAMES))

    def test_sensitivity_of_a_zero_parameter_is_undefined(self):
        rows = {row['parameter']: row for row in sensitivity(assumptions(q_risk_episodes_per_client_year=0.0))}
        self.assertIsNone(rows['q_risk_episodes_per_client_year']['swing_rubles'])
        self.assertIn('undefined', rows['q_risk_episodes_per_client_year']['note'])

    def test_break_even_moves_in_the_right_direction(self):
        params = assumptions(opex_annual=1_000_000)
        base = compute(params)['annual_margin']
        self.assertLess(base, 0)
        result = break_even(params)
        for key in ('break_even_n_clients_multiplier', 'break_even_delta_multiplier', 'break_even_opex_multiplier'):
            self.assertIsNotNone(result[key], key)
            self.assertGreater(result[key], 0, key)
        self.assertGreater(result['break_even_n_clients_multiplier'], 1)
        self.assertLess(result['break_even_opex_multiplier'], 1)
        # Slightly past break-even N, the margin must be positive.
        nudged = compute(params, {'n_clients': result['break_even_n_clients_multiplier'] * 1.05})
        self.assertGreater(nudged['annual_margin'], 0)


class TestAssumptionValidation(unittest.TestCase):
    def test_shipped_config_declares_source_and_confidence_for_everything(self):
        params = load_assumptions(CONFIG)
        for name in PARAMETER_NAMES:
            self.assertIn(name, params)
            self.assertIsNotNone(params[name].source)
            self.assertIsNotNone(params[name].confidence)
        self.assertTrue(missing_evidence(params), 'assumptions without evidence must be listed')

    def test_missing_source_or_confidence_is_rejected(self):
        raw = json.loads(CONFIG.read_text(encoding='utf-8'))
        for drop in ('source', 'confidence', 'value'):
            with self.subTest(drop=drop):
                broken = json.loads(json.dumps(raw))
                broken['parameters']['n_clients'].pop(drop)
                with tempfile.TemporaryDirectory() as folder:
                    path = Path(folder) / 'assumptions.json'
                    path.write_text(json.dumps(broken), encoding='utf-8')
                    with self.assertRaises(FinancialModelError):
                        load_assumptions(path)

    def test_unknown_parameter_and_bad_enums_are_rejected(self):
        raw = json.loads(CONFIG.read_text(encoding='utf-8'))
        cases = [
            {'parameters': {**raw['parameters'], 'made_up_parameter': {'value': 1, 'source': 'assumption', 'confidence': 'low'}}},
            {'parameters': {**raw['parameters'], 'n_clients': {'value': 1, 'source': 'guess', 'confidence': 'low'}}},
            {'parameters': {**raw['parameters'], 'n_clients': {'value': 1, 'source': 'assumption', 'confidence': 'sure'}}},
        ]
        for index, broken in enumerate(cases):
            with self.subTest(case=index):
                with tempfile.TemporaryDirectory() as folder:
                    path = Path(folder) / 'assumptions.json'
                    path.write_text(json.dumps(broken), encoding='utf-8')
                    with self.assertRaises(FinancialModelError):
                        load_assumptions(path)

    def test_missing_required_parameter_is_rejected(self):
        raw = json.loads(CONFIG.read_text(encoding='utf-8'))
        raw['parameters'].pop('opex_annual')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'assumptions.json'
            path.write_text(json.dumps(raw), encoding='utf-8')
            with self.assertRaises(FinancialModelError) as ctx:
                load_assumptions(path)
            self.assertIn('opex_annual', str(ctx.exception))

    def test_non_finite_values_are_rejected(self):
        for value in (float('inf'), float('nan')):
            with self.subTest(value=value):
                raw = json.loads(CONFIG.read_text(encoding='utf-8'))
                raw['parameters']['n_clients']['value'] = value
                with tempfile.TemporaryDirectory() as folder:
                    path = Path(folder) / 'assumptions.json'
                    path.write_text(json.dumps(raw), encoding='utf-8')
                    with self.assertRaises(FinancialModelError):
                        load_assumptions(path)


class TestArtifacts(unittest.TestCase):
    def test_all_artifacts_are_written_with_disclaimers(self):
        with tempfile.TemporaryDirectory() as folder:
            written = write_reports(load_assumptions(CONFIG), folder)
            for name in ('financial_scenarios.csv', 'sensitivity.csv', 'break_even.md', 'model_assumptions.md',
                         'missing_inputs.md', 'pitch_one_minute.md'):
                self.assertIn(name, written)
                text = Path(written[name]).read_text(encoding='utf-8')
                self.assertTrue(text.strip())
                if name.endswith('.md'):
                    for disclaimer in ('MODELLED ESTIMATE, NOT MEASURED ROI',):
                        self.assertIn(disclaimer, text)

    def test_pitch_states_the_negative_base_and_the_pilot_conditions(self):
        with tempfile.TemporaryDirectory() as folder:
            written = write_reports(load_assumptions(CONFIG), folder)
            pitch = Path(written['pitch_one_minute.md']).read_text(encoding='utf-8')
            self.assertIn('Это не ROI пилота', pitch)
            self.assertIn('дополнительный эффект поверх текущей защиты', pitch)
            self.assertIn('убыточн', pitch.lower())

    def test_model_assumptions_document_the_formulas(self):
        with tempfile.TemporaryDirectory() as folder:
            written = write_reports(load_assumptions(CONFIG), folder)
            text = Path(written['model_assumptions.md']).read_text(encoding='utf-8')
            for formula in ('FraudBenefit = N * q * Delta * L_bank', 'AnnualMargin =',
                            'SimplePaybackMonths = 12*K / AnnualMargin'):
                self.assertIn(formula, text)
            self.assertIn('counted once', text)

    def test_disclaimers_are_present_and_specific(self):
        self.assertTrue(any('RevenueUplift = 0' in line for line in DISCLAIMERS))
        self.assertTrue(any('Rewards = 0' in line for line in DISCLAIMERS))
        self.assertTrue(any('incremental' in line for line in DISCLAIMERS))


if __name__ == '__main__':
    unittest.main()