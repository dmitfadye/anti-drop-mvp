"""P1 fixture contract: provenance, legitimate negatives, boundaries, rejections."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from anti_drop_ml.adapter import evaluate_snapshot  # noqa: E402
from anti_drop_ml.contracts import RiskSnapshotV1  # noqa: E402
from anti_drop_ml.evaluation.runner import load_episodes  # noqa: E402
from scripts.generate_synthetic_fixtures import (  # noqa: E402
    DATASET_VERSION,
    FIXTURE_SEED,
    GENERATOR_VERSION,
    GROUPS,
    INVALID_GROUP,
    build_episodes,
    build_invalid,
    provenance,
    write_fixtures,
)

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / 'fixtures' / 'episodes'
PRIMARY = ('normal', 'risk', 'legitimate_negative')


class TestGeneration(unittest.TestCase):
    def test_generation_is_deterministic(self):
        first, first_catalog = build_episodes()
        second, second_catalog = build_episodes()
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        self.assertEqual(first_catalog, second_catalog)
        self.assertEqual(build_invalid(), build_invalid())

    def test_written_files_are_byte_identical_on_rerun(self):
        with tempfile.TemporaryDirectory() as folder:
            first = Path(folder) / 'a'
            second = Path(folder) / 'b'
            write_fixtures(first)
            write_fixtures(second)
            for path in sorted(first.rglob('*')):
                if path.is_file():
                    with self.subTest(path=path.name):
                        self.assertEqual(path.read_bytes(), (second / path.relative_to(first)).read_bytes())

    def test_every_group_is_written_with_its_own_catalog(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_fixtures(root)
            for group in GROUPS:
                with self.subTest(group=group):
                    self.assertTrue((root / group / 'episodes.jsonl').is_file())
                    catalog = json.loads((root / group / 'catalog.json').read_text(encoding='utf-8'))
                    self.assertEqual(catalog['group'], group)
                    self.assertEqual(catalog['label_sources'], ['synthetic_placeholder'])
            self.assertTrue((root / INVALID_GROUP / 'invalid.jsonl').is_file())
            self.assertTrue((root / 'provenance.json').is_file())

    def test_provenance_declares_seed_and_no_human_labelling(self):
        record = provenance()
        self.assertEqual(record['random_seed'], FIXTURE_SEED)
        self.assertEqual(record['generator'], GENERATOR_VERSION)
        self.assertEqual(record['dataset_version'], DATASET_VERSION)
        self.assertEqual(record['human_reviewed_count'], 0)
        self.assertEqual(record['bank_adjudicated_count'], 0)
        self.assertEqual(record['label_sources'], ['synthetic_placeholder'])
        self.assertTrue(record['adversarial_cases'])

    def test_no_episode_claims_a_label_source_we_do_not_have(self):
        episodes, catalog = build_episodes()
        for row in episodes:
            with self.subTest(episode=row['episode_id']):
                self.assertEqual(row['label_source'], 'synthetic_placeholder')
                self.assertEqual(row['payload']['metadata']['label_source'], 'synthetic_placeholder')
        self.assertNotIn('human_reviewed', json.dumps(catalog))
        self.assertNotIn('bank_adjudicated', json.dumps(catalog))


class TestShippedFixtureSet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.episodes = load_episodes(FIXTURES / 'all_episodes_p1.jsonl')
        cls.catalog = {row['episode_id']: row for row in
                       json.loads((FIXTURES / 'fixture_catalog_p1.json').read_text(encoding='utf-8'))['episodes']}

    def scenario_of(self, episode_id: str) -> str:
        return self.catalog[episode_id]['scenario']

    def test_dataset_loads_and_covers_every_group(self):
        self.assertGreater(len(self.episodes), 50)
        groups = {self.catalog[row.episode_id]['group'] for row in self.episodes}
        self.assertEqual(groups, set(GROUPS))

    def test_legitimate_negatives_are_never_red(self):
        for row in self.episodes:
            if row.episode_class != 'legitimate_negative':
                continue
            with self.subTest(scenario=self.scenario_of(row.episode_id)):
                decision = evaluate_snapshot(row.payload)
                self.assertNotEqual(decision.level, 'RED',
                                    'the detector must not accuse a legitimate scenario')

    def test_required_legitimate_negative_scenarios_are_present(self):
        required = {'family_collection', 'family_collection_then_small_rent', 'salary_and_cash',
                    'regular_payments', 'night_worker', 'new_device_without_sim',
                    'fresh_sim_without_burst', 'many_inbound_without_outbound', 'outbound_before_inbound'}
        present = {self.scenario_of(row.episode_id) for row in self.episodes}
        self.assertTrue(required <= present, sorted(required - present))

    def test_boundary_fixtures_cover_windows_amounts_counts_and_sim(self):
        present = {self.scenario_of(row.episode_id) for row in self.episodes}
        for name in ('edge_window_59', 'edge_window_60', 'edge_window_61', 'edge_midnight_cross',
                     'edge_date_boundary', 'edge_amount_1', 'edge_amount_499999', 'edge_amount_500000',
                     'edge_amount_500001', 'edge_count_1', 'edge_count_2', 'edge_count_3', 'edge_count_4',
                     'edge_count_5', 'edge_sim_null', 'edge_sim_0', 'edge_sim_1', 'edge_sim_2',
                     'edge_sim_3', 'edge_sim_30'):
            with self.subTest(scenario=name):
                self.assertIn(name, present)

    def test_window_boundary_is_inclusive_at_sixty_minutes(self):
        decisions = {}
        for name in ('edge_window_59', 'edge_window_60', 'edge_window_61'):
            row = next(item for item in self.episodes if self.scenario_of(item.episode_id) == name)
            decisions[name] = evaluate_snapshot(row.payload)
        self.assertEqual(decisions['edge_window_59'].score, 45)
        self.assertEqual(decisions['edge_window_60'].score, 45)
        self.assertEqual(decisions['edge_window_61'].score, 0)

    def test_amount_threshold_is_inclusive_at_five_thousand(self):
        for amount, expected in ((499_999, 45), (500_000, 45), (500_001, 0)):
            row = next(item for item in self.episodes
                       if self.scenario_of(item.episode_id) == f'edge_amount_{amount}')
            with self.subTest(amount=amount):
                self.assertEqual(evaluate_snapshot(row.payload).score, expected)

    def test_sim_null_is_not_sim_zero(self):
        by_name = {self.scenario_of(row.episode_id): evaluate_snapshot(row.payload)
                   for row in self.episodes if self.scenario_of(row.episode_id).startswith('edge_sim_')}
        self.assertNotIn('sim_changed_recently', by_name['edge_sim_null'].reason_codes)
        self.assertIn('sim_changed_recently', by_name['edge_sim_0'].reason_codes)
        self.assertIn('sim_changed_recently', by_name['edge_sim_2'].reason_codes)
        self.assertNotIn('sim_changed_recently', by_name['edge_sim_3'].reason_codes)
        self.assertNotIn('sim_changed_recently', by_name['edge_sim_30'].reason_codes)
        self.assertTrue(by_name['edge_sim_null'].data_quality.has_missing_sim)

    def test_missing_data_never_fabricates_a_level(self):
        for name in ('missing_no_device_id', 'missing_no_counterparty_ref', 'missing_no_sim_field',
                     'missing_no_device_no_sim'):
            row = next(item for item in self.episodes if self.scenario_of(item.episode_id) == name)
            with self.subTest(scenario=name):
                decision = evaluate_snapshot(row.payload)
                self.assertIn(decision.level, ('GREEN', 'YELLOW', 'RED'))
                self.assertEqual(decision.status, 'ok')
        empty = next(item for item in self.episodes if self.scenario_of(item.episode_id) == 'missing_empty_history')
        decision = evaluate_snapshot(empty.payload)
        self.assertEqual(decision.status, 'insufficient_data')
        self.assertEqual(decision.score, 0)
        self.assertIn('insufficient_data', decision.reason_codes)

    def test_counterparty_gap_is_a_documented_blind_spot(self):
        row = next(item for item in self.episodes
                   if self.scenario_of(item.episode_id) == 'missing_no_counterparty_ref')
        decision = evaluate_snapshot(row.payload)
        self.assertEqual(decision.level, 'GREEN', 'sender diversity cannot work without counterparties')
        self.assertIn('counterparty', self.scenario_of(row.episode_id))
        self.assertIn('degrades', self.catalog[row.episode_id]['expected_behavior'])

    def test_adversarial_cases_are_labelled_and_present(self):
        adversarial = [entry for entry in self.catalog.values() if entry['adversarial']]
        self.assertGreaterEqual(len(adversarial), 3)
        for entry in adversarial:
            with self.subTest(scenario=entry['scenario']):
                row = next(item for item in self.episodes if self.scenario_of(item.episode_id) == entry['scenario'])
                self.assertEqual(row.label, 'risk')
        misses = [name for name in ('adversarial_single_counterparty_split', 'adversarial_wait_out_the_window')
                  if evaluate_snapshot(next(item for item in self.episodes
                                             if self.scenario_of(item.episode_id) == name).payload).level != 'RED']
        self.assertTrue(misses, 'the documented blind spots should actually be blind spots')

    def test_risk_episodes_alert_and_repeat_subjects_exist(self):
        risk_rows = [row for row in self.episodes if row.episode_class == 'risk']
        alerted = [row for row in risk_rows if evaluate_snapshot(row.payload).level == 'RED']
        self.assertGreaterEqual(len(alerted) / len(risk_rows), 0.85)
        subjects = {}
        for row in self.episodes:
            subjects.setdefault(row.subject_ref, []).append(row)
        repeated = [rows for rows in subjects.values() if len(rows) > 1]
        self.assertTrue(repeated, 'a repeated subject is needed to exercise the holdout split')
        self.assertTrue(all(len({row.is_holdout for row in rows}) == 1 for rows in repeated))


class TestInvalidContracts(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(__import__('main').app, client=('127.0.0.1', 51234))

    def test_every_invalid_contract_is_rejected_with_422(self):
        for row in build_invalid():
            with self.subTest(scenario=row['scenario']):
                response = self.client.post('/api/v1/risk/evaluate', json=row['payload'])
                self.assertEqual(response.status_code, 422)
                self.assertNotEqual(response.status_code, 500)

    def test_invalid_file_covers_the_documented_scenarios(self):
        rows = build_invalid()
        scenarios = {row['scenario'] for row in rows}
        for name in ('duplicate_event_id', 'duplicate_source_event_id', 'future_occurred_at',
                     'zero_amount_transfer', 'negative_amount', 'mixed_subject_ref', 'naive_occurred_at',
                     'invalid_timezone', 'raw_pii_field', 'raw_pii_top_level', 'foreign_currency',
                     'amount_not_integer', 'amount_as_string', 'bool_amount', 'sim_as_bool',
                     'salary_outbound', 'cash_withdrawal_inbound', 'unknown_top_level_field'):
            with self.subTest(scenario=name):
                self.assertIn(name, scenarios)

    def test_validation_errors_do_not_echo_raw_pii(self):
        for row in build_invalid():
            if row['scenario'] not in ('raw_pii_field', 'raw_pii_top_level'):
                continue
            with self.subTest(scenario=row['scenario']):
                response = self.client.post('/api/v1/risk/evaluate', json=row['payload'])
                self.assertNotIn('+79990000000', response.text)
                self.assertNotIn('SYNTHETIC-NOT-A-PERSON', response.text)

    def test_shipped_invalid_file_matches_the_generator(self):
        shipped = [json.loads(line) for line in
                   (FIXTURES / INVALID_GROUP / 'invalid.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
        self.assertEqual(shipped, build_invalid())

    def test_snapshot_contract_rejects_a_language_field(self):
        row = build_invalid()[0]
        payload = json.loads(json.dumps(row['payload']))
        payload['language'] = 'uz-UZ'
        with self.assertRaises(Exception):
            RiskSnapshotV1.model_validate(payload)


if __name__ == '__main__':
    unittest.main()