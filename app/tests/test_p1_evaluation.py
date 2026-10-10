"""P1 evaluation evidence: ablation, co-occurrence, thresholds, holdout split."""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from anti_drop_ml.evaluation import quality  # noqa: E402
from anti_drop_ml.evaluation.holdout import episode_row, split_episodes, subject_bucket, write_split  # noqa: E402
from anti_drop_ml.evaluation.runner import load_episodes, run_evaluation  # noqa: E402
from src.detector import RULE_KEYS  # noqa: E402
from scripts.generate_synthetic_fixtures import write_fixtures  # noqa: E402

P1_DATASET = Path(__file__).resolve().parent.parent / 'fixtures' / 'episodes' / 'all_episodes_p1.jsonl'
ARTIFACTS = ('metrics.json', 'evaluation_manifest.json', 'episode_decisions.json', 'report.md', 'warnings.md',
             'confusion_matrix.csv', 'pr_curve.csv', 'segment_breakdown.csv', 'legitimate_negative_report.md',
             'threshold_sensitivity.csv', 'reason_cooccurrence.csv', 'rule_ablation.csv',
             'holdout_manifest.json', 'holdout_development.jsonl', 'holdout_holdout.jsonl')


class TestHoldoutSplit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.episodes = load_episodes(P1_DATASET)

    def test_bucket_is_deterministic_and_bounded(self):
        first = subject_bucket('sub_00000000aaaa0001')
        self.assertEqual(first, subject_bucket('sub_00000000aaaa0001'))
        self.assertNotEqual(first, subject_bucket('sub_00000000aaaa0001', salt='other'))
        self.assertTrue(0 <= first <= 99)
        for percent in (0, 100, -5):
            with self.subTest(percent=percent):
                with self.assertRaises(ValueError):
                    subject_bucket('sub_00000000aaaa0001', percent)

    def test_split_is_subject_disjoint(self):
        split = split_episodes(self.episodes, holdout_percent=30)
        development_subjects = {row.subject_ref for row in split.development}
        holdout_subjects = {row.subject_ref for row in split.holdout}
        self.assertTrue(development_subjects)
        self.assertTrue(holdout_subjects)
        self.assertEqual(development_subjects & holdout_subjects, set())
        self.assertEqual(len(split.development) + len(split.holdout), len(self.episodes))

    def test_split_is_stable_across_runs(self):
        first = split_episodes(self.episodes, holdout_percent=30)
        second = split_episodes(self.episodes, holdout_percent=30)
        self.assertEqual([row.episode_id for row in first.holdout], [row.episode_id for row in second.holdout])

    def test_manifest_records_invariants_time_and_ids(self):
        manifest = split_episodes(self.episodes, holdout_percent=30).manifest
        self.assertEqual(manifest['schema_version'], 'HoldoutManifestV1')
        self.assertTrue(manifest['invariants']['subject_disjoint'])
        self.assertTrue(manifest['invariants']['rules_are_not_trained'])
        self.assertEqual(len(manifest['holdout_episode_ids']), manifest['holdout_episodes'])
        self.assertTrue(manifest['time_range_holdout']['from'])
        self.assertTrue(any('synthetic' in warning for warning in manifest['warnings']))
        self.assertEqual(len(manifest['subjects']), len({row.subject_ref for row in self.episodes}))

    def test_written_rows_carry_the_computed_flag(self):
        split = split_episodes(self.episodes, holdout_percent=30)
        with tempfile.TemporaryDirectory() as folder:
            written = write_split(split, Path(folder))
            development = [json.loads(line) for line in
                           Path(written['holdout_development.jsonl']).read_text(encoding='utf-8').splitlines() if line]
            holdout = [json.loads(line) for line in
                       Path(written['holdout_holdout.jsonl']).read_text(encoding='utf-8').splitlines() if line]
            self.assertTrue(all(row['is_holdout'] is False for row in development))
            self.assertTrue(all(row['is_holdout'] is True for row in holdout))
            # The written files must load back through the normal dataset reader.
            self.assertTrue(load_episodes(Path(written['holdout_holdout.jsonl'])))
            self.assertTrue(load_episodes(Path(written['holdout_development.jsonl'])))
            # An episode row carries the split flag in both the envelope and the
            # snapshot metadata, otherwise the reader rejects the file.
            rebuilt = episode_row(split.holdout[0], True)
            self.assertTrue(rebuilt['is_holdout'])
            self.assertTrue(rebuilt['payload']['metadata']['is_holdout'])
            self.assertFalse(episode_row(split.development[0], False)['payload']['metadata']['is_holdout'])


class TestQualityEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.episodes = load_episodes(P1_DATASET)

    def rows(self):
        return [{'label': episode.label, 'episode_class': episode.episode_class,
                 'predicted_positive': episode.label == 'risk', 'score': 50 if episode.label == 'risk' else 10,
                 'reason_codes': ['multiple_small_inbound'] if episode.label == 'risk' else [],
                 'is_holdout': episode.is_holdout}
                for episode in self.episodes]

    def test_ablation_covers_every_rule(self):
        table = quality.rule_ablation(self.episodes, self.rows())
        self.assertEqual(table[0]['configuration'], 'baseline_all_rules')
        disabled = [row['rule'] for row in table[1:]]
        self.assertEqual(sorted(disabled), sorted(RULE_KEYS))
        for row in table[1:]:
            with self.subTest(rule=row['rule']):
                self.assertIsNotNone(row['delta_recall'])
                self.assertIsNotNone(row['delta_fpr'])
                self.assertIsNotNone(row['delta_alert_rate'])

    def test_ablation_shows_the_load_bearing_rules(self):
        table = {row['rule']: row for row in quality.rule_ablation(self.episodes, self.rows())}
        self.assertLess(table['multiple_small_inbound']['delta_recall'], 0)
        self.assertLess(table['large_outbound_after_inbound']['delta_recall'], 0)

    def test_reason_cooccurrence_is_a_consistent_matrix(self):
        pairs = quality.reason_cooccurrence(self.rows())
        self.assertTrue(pairs)
        for pair in pairs:
            with self.subTest(pair=(pair['reason_code_a'], pair['reason_code_b'])):
                self.assertLessEqual(pair['episodes_with_both'], pair['episodes_with_a'])
                self.assertLessEqual(pair['episodes_with_both'], pair['episodes_with_both' and 'episodes_with_b'])
                if pair['jaccard'] is not None:
                    self.assertTrue(0 <= pair['jaccard'] <= 1)
        diagonals = [pair for pair in pairs if pair['reason_code_a'] == pair['reason_code_b']]
        for pair in diagonals:
            self.assertEqual(pair['jaccard'], 1.0)

    def test_threshold_sensitivity_sweeps_and_ends_conservative(self):
        table = quality.threshold_sensitivity(self.rows())
        self.assertEqual(len(table), 21)
        self.assertEqual(table[0]['score_threshold'], 0)
        self.assertEqual(table[-1]['score_threshold'], 100)
        alerts = [row['alerts'] if 'alerts' in row else row['TP'] + row['FP'] for row in table]
        self.assertEqual(alerts, sorted(alerts, reverse=True))

    def test_business_thresholds_are_labelled_assumptions(self):
        result = quality.business_thresholds(self.rows(), cost_false_alert=650, cost_missed_risk=45000,
                                             prevalence=0.002)
        self.assertEqual(result['status'], 'ASSUMPTION_DRIVEN')
        self.assertIn('ASSUMPTIONS', result['inputs']['note'])
        self.assertTrue(result['rows'])
        for row in result['rows']:
            with self.subTest(threshold=row['score_threshold']):
                self.assertGreaterEqual(row['expected_cost'], 0)
        best = result['best_threshold_by_cost']
        cheapest = min(result['rows'], key=lambda row: row['expected_cost'])
        self.assertEqual(best, cheapest['score_threshold'])
        self.assertTrue(any('assumptions' in warning for warning in result['warnings']))

    def test_business_thresholds_undefined_without_positives(self):
        rows = [{'label': 'normal', 'episode_class': 'normal', 'predicted_positive': False, 'score': 0,
                 'reason_codes': []}]
        result = quality.business_thresholds(rows, 650, 45000, 0.1)
        self.assertEqual(result['status'], 'UNDEFINED')
        self.assertEqual(result['rows'], [])

    def test_language_invariance_check_actually_injects(self):
        result = quality.language_invariance_check(self.episodes)
        self.assertGreater(result['attempts'], 0)
        self.assertTrue(result['all_rejected'])
        self.assertEqual(result['accepted'], 0)

    def test_missing_data_summary_is_rate_based(self):
        # Row 1 has missing SIM and a known device; row 2 carries no flags at all,
        # so it must not dilute either denominator.
        rows = [{'has_missing_sim': True, 'has_missing_device': False, 'status': 'ok'},
                {'has_missing_sim': None, 'has_missing_device': None, 'status': 'ok'}]
        summary = quality.missing_data_summary(rows)
        self.assertEqual(summary['missing_sim']['observed_episodes'], 1)
        self.assertEqual(summary['missing_sim']['rate'], 1.0)
        self.assertEqual(summary['missing_device']['rate'], 0.0)
        self.assertEqual(summary['any_missing']['rate'], 1.0)
        self.assertEqual(summary['insufficient_data_status'], 0)
        mixed = quality.missing_data_summary([
            {'has_missing_sim': True, 'has_missing_device': False, 'status': 'ok'},
            {'has_missing_sim': False, 'has_missing_device': True, 'status': 'insufficient_data'}])
        self.assertEqual(mixed['missing_sim']['rate'], 0.5)
        self.assertEqual(mixed['missing_device']['rate'], 0.5)
        self.assertEqual(mixed['insufficient_data_status'], 1)

    def test_missing_data_summary_of_empty_input(self):
        summary = quality.missing_data_summary([])
        self.assertIsNone(summary['missing_sim']['rate'])
        self.assertIsNone(summary['missing_device']['rate'])
        self.assertEqual(summary['episodes'], 0)


class TestFullRunArtifacts(unittest.TestCase):
    def test_every_p1_artifact_is_written_and_honest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_fixtures(root / 'fixtures')
            dataset = root / 'fixtures' / 'all_episodes_p1.jsonl'
            metrics = run_evaluation(dataset, root / 'reports',
                                    cost_false_alert=650, cost_missed_risk=45000, prevalence=0.002)
            for name in ARTIFACTS:
                with self.subTest(artifact=name):
                    self.assertTrue((root / 'reports' / name).is_file(), name)

            self.assertEqual(metrics['overall']['total_episodes'],
                             metrics['manifest']['number_of_primary_episodes'])
            self.assertEqual(len(quality.PRIMARY_CLASSES), 3)
            self.assertEqual(metrics['scope']['primary_episode_classes'], list(quality.PRIMARY_CLASSES))
            self.assertTrue(metrics['edge_case_behavior_summary']['episodes'] > 0)
            self.assertTrue(metrics['language_invariance']['all_rejected'])

            warnings = metrics['warnings']
            self.assertTrue(any('UNVALIDATED LABELS' in warning for warning in warnings))
            self.assertTrue(any('SMALL SAMPLE' in warning for warning in warnings))
            self.assertTrue(any('NO BANK ADJUDICATION' in warning for warning in warnings))
            self.assertTrue(any('post-event' in warning for warning in warnings))

            report = (root / 'reports' / 'report.md').read_text(encoding='utf-8')
            for phrase in ('not a probability', 'not validated bank accuracy', 'not measured',
                           'Language is not a risk factor', 'post-event', 'not a real bank support request'):
                with self.subTest(phrase=phrase):
                    self.assertIn(phrase, report)
            warnings_md = (root / 'reports' / 'warnings.md').read_text(encoding='utf-8')
            self.assertIn('NOT validated', warnings_md)
            self.assertIn('Claims this repository does NOT support', warnings_md)

            legitimate = (root / 'reports' / 'legitimate_negative_report.md').read_text(encoding='utf-8')
            self.assertIn('Not validated banking accuracy', legitimate)
            self.assertIn('family_collection', legitimate)

            with (root / 'reports' / 'threshold_sensitivity.csv').open(encoding='utf-8', newline='') as stream:
                self.assertEqual(len(list(csv.DictReader(stream))), 21)
            with (root / 'reports' / 'rule_ablation.csv').open(encoding='utf-8', newline='') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), len(RULE_KEYS) + 1)
            with (root / 'reports' / 'reason_cooccurrence.csv').open(encoding='utf-8', newline='') as stream:
                self.assertTrue(list(csv.DictReader(stream)))
            self.assertTrue((root / 'reports' / 'business_thresholds.csv').is_file())

            manifest = json.loads((root / 'reports' / 'evaluation_manifest.json').read_text(encoding='utf-8'))
            for key in ('dataset_version', 'rule_version', 'threshold_version', 'template_version',
                        'number_of_episodes', 'label_sources', 'holdout_status', 'environment',
                        'holdout_split', 'git_commit', 'timestamp', 'warnings'):
                with self.subTest(manifest_key=key):
                    self.assertIn(key, manifest)
            self.assertIn('python_version', manifest['environment'])
            self.assertIn('packages', manifest['environment'])
            self.assertIsNone(manifest['experiment_id'])
            self.assertIsNone(manifest['random_seed'])

    def test_rejected_dataset_writes_no_reports(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_fixtures(root / 'fixtures')
            dataset = root / 'fixtures' / 'all_episodes_p1.jsonl'
            with self.assertRaises(ValueError):
                run_evaluation(dataset, root / 'reports', rule_version='fictional')
            self.assertFalse((root / 'reports').exists())

    def test_broken_jsonl_writes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            dataset = root / 'broken.jsonl'
            dataset.write_text('{"schema_version":"RiskSnapshotV1"}\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                run_evaluation(dataset, root / 'reports')
            self.assertFalse((root / 'reports').exists())

    def test_skip_ablation_and_no_split_are_honoured(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_fixtures(root / 'fixtures')
            run_evaluation(root / 'fixtures' / 'all_episodes_p1.jsonl', root / 'reports',
                           skip_ablation=True, write_holdout=False)
            self.assertFalse((root / 'reports' / 'rule_ablation.csv').exists())
            self.assertFalse((root / 'reports' / 'holdout_manifest.json').exists())
            self.assertTrue((root / 'reports' / 'report.md').is_file())


if __name__ == '__main__':
    unittest.main()