"""Contract, rule-regression and evaluation acceptance tests, no external services."""
import copy
import csv
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import ValidationError

from main import app
from anti_drop_ml.adapter import RULE_VERSION, THRESHOLD_VERSION, evaluate_snapshot
from anti_drop_ml.contracts import RiskSnapshotV1
from anti_drop_ml.evaluation.runner import load_episodes, run_evaluation
from anti_drop_ml.events import ProductEventV1
from anti_drop_ml.make_labeling_template import AT, build_fixtures, make_snapshot, ref, transaction, write_fixtures
from anti_drop_ml.metrics import pr_curve, summarize, wilson_interval
from anti_drop_ml.power import required_n_two_proportions


class TestStrictSnapshots(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_invalid_contracts_return_422(self):
        for fixture in build_fixtures()[1]:
            with self.subTest(fixture['scenario']):
                self.assertEqual(self.client.post('/api/v1/risk/evaluate', json=fixture['payload']).status_code, 422)

    def test_mixed_timezones_and_stable_id(self):
        first = make_snapshot([transaction()])
        second = copy.deepcopy(first)
        second['transactions'][0]['occurred_at'] = '2026-10-08T14:50:00+03:00'
        a, b = evaluate_snapshot(first), evaluate_snapshot(second)
        self.assertEqual(a, b)
        self.assertEqual(a.analysis_at.utcoffset(), timedelta(0))
        self.assertEqual(a.score_interpretation, 'deterministic_rule_score_not_probability')
        first['metadata']['is_holdout'] = True
        self.assertEqual(a.evaluation_id, evaluate_snapshot(first).evaluation_id)

    def test_analysis_at_naive_invalid_and_numeric_rejected(self):
        for value in ('2026-10-08T12:00:00', 'bad', 123):
            snapshot = make_snapshot([])
            snapshot['analysis_at'] = value
            self.assertEqual(self.client.post('/api/v1/risk/evaluate', json=snapshot).status_code, 422)

    def test_strict_integers_pii_currency_and_unknown_fields(self):
        for field, value in [('amount_minor', 1.2), ('amount_minor', '100'), ('amount_minor', True), ('sim_changed_days_ago', False), ('currency', 'USD'), ('phone', 'forbidden'), ('counterparty_ref', 'full-name'), ('direction', 'transfer')]:
            with self.subTest(field=field, value=value):
                snapshot = make_snapshot([transaction()])
                snapshot['transactions'][0][field] = value
                self.assertEqual(self.client.post('/api/v1/risk/evaluate', json=snapshot).status_code, 422)

    def test_allow_future_excludes_from_risk(self):
        snapshot = make_snapshot([transaction(i, minutes=-1) for i in range(5)])
        snapshot['allow_future_events'] = True
        decision = evaluate_snapshot(snapshot)
        self.assertEqual(decision.score, 0)
        self.assertEqual(decision.data_quality.future_events_excluded, 5)
        self.assertEqual(decision.status, 'insufficient_data')

    def test_revalidation_of_mutated_model(self):
        snapshot = RiskSnapshotV1.model_validate(make_snapshot([transaction()]))
        snapshot.transactions.append(snapshot.transactions[0])
        with self.assertRaises(ValidationError): evaluate_snapshot(snapshot)

    def test_sorting_repeatability(self):
        snapshot = make_snapshot([transaction(i, minutes=40-i*5) for i in range(5)])
        first = evaluate_snapshot(snapshot)
        snapshot['transactions'].reverse()
        self.assertEqual(first, evaluate_snapshot(snapshot))
        self.assertEqual(self.client.post('/api/v1/risk/evaluate', json=snapshot).status_code, 200)

    def test_validation_does_not_echo_raw_pii(self):
        snapshot = make_snapshot([])
        snapshot['phone'] = 'DO_NOT_ECHO_THIS_INPUT'
        response = self.client.post('/api/v1/risk/evaluate', json=snapshot)
        self.assertEqual(response.status_code, 422)
        self.assertNotIn('DO_NOT_ECHO_THIS_INPUT', response.text)

    def test_labels_and_language_do_not_influence_scoring(self):
        snapshot = make_snapshot([transaction()])
        original = evaluate_snapshot(snapshot)
        snapshot['metadata'].update(label='risk', episode_class='risk')
        self.assertEqual(original, evaluate_snapshot(snapshot))
        snapshot['language'] = 'ru'
        with self.assertRaises(ValidationError): evaluate_snapshot(snapshot)

    def test_sim_days(self):
        for sim, fresh in [(None, False), (0, True), (1, True), (2, True), (3, False)]:
            with self.subTest(sim=sim):
                result = evaluate_snapshot(make_snapshot([transaction(i, minutes=20-i*5, sim=sim) for i in range(3)]))
                self.assertEqual('sim_changed_recently' in result.reason_codes, fresh)
                self.assertEqual(result.data_quality.has_missing_sim, sim is None)

    def test_windows_and_amount_boundaries(self):
        for minutes, expected in [(59, 45), (60, 45), (61, 0)]:
            self.assertEqual(evaluate_snapshot(make_snapshot([transaction(i, minutes=minutes) for i in range(5)])).score, expected)
        for amount, expected in [(1, 45), (499999, 45), (500000, 45), (500001, 0)]:
            self.assertEqual(evaluate_snapshot(make_snapshot([transaction(i, amount=amount) for i in range(5)])).score, expected)

    def test_outbound_order_and_no_outbound(self):
        inbound = [transaction(i, minutes=40-i*5) for i in range(5)]
        early = evaluate_snapshot(make_snapshot([transaction(9, minutes=50, direction='out', amount=1400000)]+inbound))
        late = evaluate_snapshot(make_snapshot(inbound+[transaction(9, minutes=1, direction='out', amount=1400000)]))
        self.assertNotIn('large_outbound_after_inbound', early.reason_codes)
        self.assertIn('large_outbound_after_inbound', late.reason_codes)
        self.assertNotIn('large_outbound_after_inbound', evaluate_snapshot(make_snapshot(inbound)).reason_codes)

    def test_legitimate_negatives_measured_not_whitelisted(self):
        episodes, _, catalog = build_fixtures()
        mapping = {row['scenario']: row['episode_id'] for row in catalog}
        for name in ['family_collection', 'salary_and_cash', 'regular_payments', 'night_worker', 'new_device_without_sim']:
            row = next(e for e in episodes if e['episode_id'] == mapping[name])
            self.assertEqual(row['episode_class'], 'legitimate_negative')
            decision = evaluate_snapshot(row['payload'])
            self.assertNotEqual(decision.level, 'RED')
            if name == 'family_collection': self.assertEqual(decision.score, 45)
            if name == 'salary_and_cash': self.assertIn('cashout_ratio', decision.reason_codes)

    def test_score_cap_and_contributions(self):
        txns = [transaction(i, minutes=40-i*5, sim=0) for i in range(5)]
        txns += [transaction(10+i, minutes=2, direction='out', amount=400000, sim=0) for i in range(4)]
        decision = evaluate_snapshot(make_snapshot(txns))
        self.assertEqual(decision.score, min(100, sum(decision.score_contributions.values())))
        self.assertEqual(decision.score, 100)


class TestEvaluation(unittest.TestCase):
    def test_metrics_known_counts_and_wilson(self):
        rows = [{'label': label, 'predicted_positive': pred, 'episode_class': 'normal', 'score': score} for label, pred, score in [('risk', True, 80), ('risk', False, 20), ('normal', True, 60), ('normal', False, 0)]]
        metrics = summarize(rows)
        self.assertEqual([metrics[k] for k in ('TP','FP','TN','FN')], [1,1,1,1])
        for key in ('recall', 'precision', 'fpr', 'fnr', 'alert_rate'): self.assertEqual(metrics[key]['value'], .5)
        self.assertIsNone(wilson_interval(0, 0))
        self.assertAlmostEqual(wilson_interval(1, 1)[0], .206543, places=5)
        self.assertAlmostEqual(wilson_interval(150, 300)[0], .443778, places=5)
        self.assertEqual(len(pr_curve(rows)), 101)
        self.assertEqual(pr_curve(rows)[0]['recall'], 1)
        self.assertIsNone(pr_curve(rows)[100]['precision'])
        self.assertIsNone(summarize([])['recall']['value'])
        for k, n in [(-1, 1), (2, 1), (1, -1), (True, 1)]:
            with self.assertRaises(ValueError): wilson_interval(k, n)

    def test_full_runner_and_reproducible_fixtures(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_fixtures(root/'fixtures')
            path = root/'fixtures/labeled_episodes.jsonl'
            before = path.read_bytes()
            write_fixtures(root/'fixtures')
            self.assertEqual(before, path.read_bytes())
            metrics = run_evaluation(path, root/'report')
            self.assertEqual(metrics['schema_version'], 'EvaluationMetricsV1')
            self.assertGreater(metrics['overall']['total_episodes'], 10)
            self.assertTrue(any('NOT validated' in warning for warning in metrics['warnings']))
            for filename in ['metrics.json', 'report.md', 'confusion_matrix.csv', 'pr_curve.csv', 'segment_breakdown.csv', 'evaluation_manifest.json', 'legitimate_negatives_report.md']:
                self.assertTrue((root/'report'/filename).is_file())
            with (root/'report/pr_curve.csv').open() as stream: self.assertEqual(len(list(csv.DictReader(stream))), 101)
            manifest = json.loads((root/'report/evaluation_manifest.json').read_text())
            self.assertEqual(manifest['rule_version'], RULE_VERSION)
            self.assertEqual(manifest['holdout_status'], 'development_only')
            threshold_metrics = run_evaluation(path, root/'threshold', positive_threshold=100)
            self.assertLessEqual(threshold_metrics['overall']['alert_rate']['value'], metrics['overall']['alert_rate']['value'])
            with self.assertRaises(ValueError): run_evaluation(path, root/'bad', rule_version='fictional')
            with self.assertRaises(ValueError): run_evaluation(path, root/'bad', holdout_only=True)

    def test_csv_and_snapshot_jsonl_formats(self):
        episode = build_fixtures()[0][0]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'episodes.csv'
            row = {key: value for key, value in episode.items() if key != 'payload'}
            row['is_holdout'] = 'false'
            row['payload_json'] = json.dumps(episode['payload'])
            with path.open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(row)); writer.writeheader(); writer.writerow(row)
            self.assertEqual(len(load_episodes(path)), 1)
            snapshot = copy.deepcopy(episode['payload'])
            snapshot['metadata'].update(episode_id=episode['episode_id'], label=episode['label'])
            path = Path(folder)/'snapshot.jsonl'; path.write_text(json.dumps(snapshot)+'\n')
            self.assertEqual(len(load_episodes(path)), 1)

    def test_bad_dataset_no_reports_and_holdout_leakage(self):
        episodes = build_fixtures()[0]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'bad.jsonl'
            for data in [[], [episodes[0], episodes[0]], [dict(episodes[0], label='ambiguous')]]:
                path.write_text(''.join(json.dumps(e)+'\n' for e in data))
                with self.assertRaises(ValueError): run_evaluation(path, Path(folder)/'output')
                self.assertFalse((Path(folder)/'output').exists())
            second = copy.deepcopy(episodes[0]); second['episode_id'] = ref('ep','other'); second['is_holdout'] = True; second['payload']['metadata']['is_holdout'] = True
            path.write_text(json.dumps(episodes[0])+'\n'+json.dumps(second)+'\n')
            with self.assertRaises(ValueError): load_episodes(path)


class TestEventsAndPower(unittest.TestCase):
    def event(self):
        return dict(event_id=str(uuid4()), event_type='risk_evaluated', timestamp=AT.isoformat(), evaluation_id='a'*64, rule_version=RULE_VERSION, threshold_version=THRESHOLD_VERSION)

    def test_event_allowlist_rejects_pii_top_level_nested_and_refs(self):
        ProductEventV1.model_validate(self.event())
        for field in ['phone', 'full_name', 'passport', 'card_number', 'otp', 'counterparty_name', 'transaction_text', 'location', 'biometrics']:
            for nested in (False, True):
                data = self.event()
                if nested: data['metadata'] = {field: 'forbidden'}
                else: data[field] = 'forbidden'
                with self.assertRaises(ValidationError): ProductEventV1.model_validate(data)
        with self.assertRaises(ValidationError): ProductEventV1.model_validate({**self.event(), 'subject_pseudonym': '+70000000000'})

    def test_all_event_types(self):
        for kind in ['risk_evaluated', 'alert_delivered', 'alert_viewed', 'language_selected', 'help_started', 'case_created', 'case_confirmed', 'safe_action_confirmed', 'request_failed', 'experiment_assigned']:
            ProductEventV1.model_validate({**self.event(), 'event_type': kind})

    def test_power(self):
        n = required_n_two_proportions(.2, 5)
        self.assertIsInstance(n, int)
        self.assertGreater(n, 0)
        self.assertGreater(required_n_two_proportions(.2, 5, dropout_rate=.1), n)
        for args in [(0, 5), (.99, 5), (.2, 0), (float('nan'), 5)]:
            with self.assertRaises(ValueError): required_n_two_proportions(*args)


if __name__ == '__main__':
    unittest.main()
