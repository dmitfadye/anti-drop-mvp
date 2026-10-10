"""P1 quality evidence: ablation, co-occurrence, thresholds, business cost.

This module turns a list of decisions into the artifacts a reviewer asks for
after seeing "recall 1.0 on two synthetic episodes": which rule did the work,
which alerts are false and why, how much a threshold change buys, and what a
false alert costs. Every table carries the caveat that the labels are
`synthetic_placeholder` and nothing here is a validated bank metric.

Nothing in this module changes the detector. Ablation re-runs the same rules
with one rule switched off and compares outcomes.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from anti_drop_ml.adapter import ADAPTER_VERSION, RULE_VERSION, THRESHOLD_VERSION, evaluate_snapshot
from anti_drop_ml.metrics import summarize, wilson_interval
from src.detector import RULE_KEYS

PRIMARY_CLASSES = ('normal', 'risk', 'legitimate_negative')
EDGE_CLASSES = ('edge',)


def _primary(rows: list[dict]) -> list[dict]:
    return [row for row in rows if row['episode_class'] in PRIMARY_CLASSES]


def _delta(value: float | None, baseline: float | None) -> float | None:
    if value is None or baseline is None:
        return None
    return value - baseline


def rule_ablation(episodes: list, rows: list[dict], holdout_only: bool = False) -> list[dict]:
    """Baseline vs each rule removed. Deltas are recall/FPR/alert-rate shifts."""
    selected = [e for e in episodes if (not holdout_only or e.is_holdout)]
    baseline_rows = [row for row in rows if not holdout_only or row.get('is_holdout')]
    baseline = summarize(_primary(baseline_rows))
    table = [{'configuration': 'baseline_all_rules', 'rule': 'none', 'disabled': '',
              'recall': baseline['recall']['value'], 'fpr': baseline['fpr']['value'],
              'alert_rate': baseline['alert_rate']['value'],
              'delta_recall': 0.0, 'delta_fpr': 0.0, 'delta_alert_rate': 0.0,
              'TP': baseline['TP'], 'FP': baseline['FP'], 'TN': baseline['TN'], 'FN': baseline['FN']}]
    for rule in RULE_KEYS:
        ablated = []
        for episode in selected:
            decision = evaluate_snapshot(episode.payload, disabled_rules=frozenset({rule}))
            ablated.append({
                'label': episode.label,
                'episode_class': episode.episode_class,
                'label_source': episode.label_source,
                'is_holdout': episode.is_holdout,
                'score': decision.score,
                'predicted_positive': decision.level == 'RED',
                'reason_codes': list(decision.reason_codes),
            })
        metrics = summarize(_primary(ablated))
        table.append({
            'configuration': 'without_rule', 'rule': rule, 'disabled': rule,
            'recall': metrics['recall']['value'], 'fpr': metrics['fpr']['value'],
            'alert_rate': metrics['alert_rate']['value'],
            'delta_recall': _delta(metrics['recall']['value'], baseline['recall']['value']),
            'delta_fpr': _delta(metrics['fpr']['value'], baseline['fpr']['value']),
            'delta_alert_rate': _delta(metrics['alert_rate']['value'], baseline['alert_rate']['value']),
            'TP': metrics['TP'], 'FP': metrics['FP'], 'TN': metrics['TN'], 'FN': metrics['FN'],
        })
    return table


def reason_cooccurrence(rows: list[dict]) -> list[dict]:
    """How often two reason codes appear on the same decision.

    A high diagonal on `multiple_small_inbound` next to
    `large_outbound_after_inbound` means the same transit pattern is charged
    twice, which is exactly what a reviewer should see before a threshold debate.
    """
    codes = sorted({code for row in rows for code in row.get('reason_codes', [])})
    counts = {code: sum(1 for row in rows if code in row.get('reason_codes', [])) for code in codes}
    pairs = []
    for i, left in enumerate(codes):
        for right in codes[i:]:
            together = sum(1 for row in rows if left in row.get('reason_codes', []) and right in row.get('reason_codes', []))
            union = sum(1 for row in rows if left in row.get('reason_codes', []) or right in row.get('reason_codes', []))
            pairs.append({
                'reason_code_a': left, 'reason_code_b': right,
                'episodes_with_a': counts[left], 'episodes_with_b': counts[right],
                'episodes_with_both': together,
                'jaccard': round(together / union, 4) if union else None,
            })
    return sorted(pairs, key=lambda row: (-row['episodes_with_both'], row['reason_code_a'], row['reason_code_b']))


def threshold_sensitivity(rows: list[dict], step: int = 5) -> list[dict]:
    """Score-threshold sweep over the primary classes."""
    table = []
    for threshold in range(0, 101, step):
        metrics = summarize([{**row, 'predicted_positive': row['score'] >= threshold} for row in _primary(rows)])
        table.append({
            'score_threshold': threshold,
            'alert_level_equivalent': 'RED' if threshold >= 50 else ('YELLOW' if threshold >= 25 else 'GREEN'),
            'TP': metrics['TP'], 'FP': metrics['FP'], 'TN': metrics['TN'], 'FN': metrics['FN'],
            'recall': metrics['recall']['value'], 'precision': metrics['precision']['value'],
            'fpr': metrics['fpr']['value'],
            'legitimate_negative_alert_rate': metrics['legitimate_negative_alert_rate']['value'],
            'alert_rate': metrics['alert_rate']['value'],
        })
    return table


def business_thresholds(rows: list[dict], cost_false_alert: float, cost_missed_risk: float,
                        prevalence: float) -> dict:
    """Cost-weighted threshold table. Costs and prevalence are ASSUMPTIONS."""
    primary = _primary(rows)
    positives = sum(1 for row in primary if row['label'] == 'risk')
    n = len(primary)
    if n == 0 or positives == 0:
        return {
            'schema_version': 'BusinessThresholdV1',
            'status': 'UNDEFINED',
            'reason': 'no labelled positives in the primary classes',
            'inputs': {'cost_false_alert': cost_false_alert, 'cost_missed_risk': cost_missed_risk,
                       'prevalence': prevalence},
            'rows': [],
        }
    table = []
    for threshold in range(0, 101, 5):
        metrics = summarize([{**row, 'predicted_positive': row['score'] >= threshold} for row in primary])
        alerts = metrics['TP'] + metrics['FP']
        expected_cost = metrics['FP'] * cost_false_alert + metrics['FN'] * cost_missed_risk
        table.append({
            'score_threshold': threshold,
            'alerts': alerts,
            'TP': metrics['TP'], 'FP': metrics['FP'], 'FN': metrics['FN'],
            'expected_cost': expected_cost,
            'expected_cost_per_1000_episodes': round(expected_cost / n * 1000, 2) if n else None,
            'recall': metrics['recall']['value'],
            'prevalence_in_dataset': positives / n,
        })
    best = min((row for row in table if row['expected_cost'] is not None), key=lambda row: row['expected_cost'], default=None)
    return {
        'schema_version': 'BusinessThresholdV1',
        'status': 'ASSUMPTION_DRIVEN',
        'inputs': {
            'cost_false_alert_rubles': cost_false_alert,
            'cost_missed_risk_rubles': cost_missed_risk,
            'prevalence_assumption': prevalence,
            'note': 'costs and prevalence are ASSUMPTIONS supplied by the caller; no bank data exists',
        },
        'dataset_prevalence': positives / n,
        'prevalence_sensitivity': [
            {'prevalence': candidate,
             'note': 'synthetic weighting; the dataset prevalence is '
                     f'{positives / n:.4f}, so re-weighting changes the optimal threshold'}
            for candidate in sorted({round(positives / n, 4), 0.001, 0.005, 0.02, 0.05})
        ],
        'best_threshold_by_cost': best['score_threshold'] if best else None,
        'rows': table,
        'warnings': [
            'Costs and prevalence are assumptions, not measurements.',
            'Expected cost scales linearly with episode volume and ignores clustering by subject.',
            'A threshold chosen here must be re-derived on an independent holdout before a pilot.',
        ],
    }


def edge_case_behavior(rows: list[dict]) -> dict:
    """What the detector does on boundary fixtures, and with how much data."""
    edge = [row for row in rows if row['episode_class'] in EDGE_CLASSES]
    by_level = Counter(row['level'] for row in edge)
    insufficient = [row['episode_id'] for row in edge if row.get('status') == 'insufficient_data']
    return {
        'schema_version': 'EdgeCaseBehaviorV1',
        'episodes': len(edge),
        'levels': dict(sorted(by_level.items())),
        'borderline_window_flagged': sum(1 for row in edge if 'borderline_window' in row.get('reason_codes', [])),
        'insufficient_data_episodes': sorted(insufficient),
        'notes': [
            'Edge fixtures test boundary behaviour, not accuracy; they are excluded from the primary confusion matrix.',
            'Edge episodes with a risk pattern but only one firing rule are expected to stay YELLOW at the RED threshold.',
            'Any RED on an edge fixture is listed in top_false_positive_patterns and needs review.',
        ],
    }


def _flag_rate(rows: list[dict], field: str) -> dict:
    """Rate over the rows that actually carry the flag; undefined when none do."""
    observed = [row for row in rows if row.get(field) is not None]
    missing = [row for row in observed if row[field]]
    return {'episodes': len(missing), 'observed_episodes': len(observed),
            'rate': len(missing) / len(observed) if observed else None}


def missing_data_summary(rows: list[dict]) -> dict:
    sim = _flag_rate(rows, 'has_missing_sim')
    device = _flag_rate(rows, 'has_missing_device')
    observed = [row for row in rows if row.get('has_missing_sim') is not None or row.get('has_missing_device') is not None]
    either = [row for row in observed if row.get('has_missing_sim') or row.get('has_missing_device')]
    return {
        'schema_version': 'MissingDataSummaryV1',
        'episodes': len(rows),
        'missing_sim': sim,
        'missing_device': device,
        'any_missing': {'episodes': len(either), 'observed_episodes': len(observed),
                        'rate': len(either) / len(observed) if observed else None},
        'insufficient_data_status': sum(1 for row in rows if row.get('status') == 'insufficient_data'),
        'note': ('Missing data lowers rule sensitivity; it never manufactures a reason code on its own. '
                 'A rate is undefined when no episode was observed for that field, never shown as zero.'),
    }


def error_patterns(rows: list[dict], catalog: dict[str, dict]) -> dict:
    """Top false positive / false negative shapes, with the reason codes involved."""
    false_positives = [row for row in rows if row['label'] != 'risk' and row['predicted_positive']]
    false_negatives = [row for row in rows if row['label'] == 'risk' and not row['predicted_positive']]

    def shape(row: dict) -> str:
        return '+'.join(sorted(row.get('reason_codes', []))) or 'no_reason_code'

    def group(items: list[dict]) -> list[dict]:
        counter = Counter(shape(row) for row in items)
        out = []
        for key, count in counter.most_common():
            members = [row for row in items if shape(row) == key]
            out.append({
                'reason_code_shape': key,
                'count': count,
                'episode_ids': sorted(row['episode_id'] for row in members),
                'scenario_names': sorted(catalog[row['episode_id']]['scenario'] for row in members
                                         if row['episode_id'] in catalog),
                'episode_classes': sorted({row['episode_class'] for row in members}),
            })
        return out

    return {
        'schema_version': 'ErrorPatternsV1',
        'false_positive_count': len(false_positives),
        'false_negative_count': len(false_negatives),
        'top_false_positive_patterns': group(false_positives),
        'top_false_negative_patterns': group(false_negatives),
        'interpretation': [
            'False positives on family collections are expected: a declared purpose does not change the observable flow.',
            'False negatives concentrated on single-counterparty or out-of-window patterns are documented detector blind spots.',
            'Both lists are synthetic fixtures; neither is a validated bank error profile.',
        ],
    }


def environment_fingerprint() -> dict:
    import platform
    import sys

    packages = {}
    for name in ('pydantic', 'fastapi', 'uvicorn', 'httpx'):
        try:
            module = __import__(name)
            packages[name] = getattr(module, '__version__', 'unknown')
        except ImportError:
            packages[name] = 'not_installed'
    return {
        'python_version': sys.version.split()[0],
        'python_implementation': platform.python_implementation(),
        'platform': platform.system(),
        'packages': packages,
        'rule_version': RULE_VERSION,
        'threshold_version': THRESHOLD_VERSION,
        'adapter_version': ADAPTER_VERSION,
        'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    }


def language_invariance_check(episodes: list) -> dict:
    """Prove the detector ignores language by trying to smuggle it in.

    A `language` (or any locale/nationality) field on a snapshot must be
    refused by the closed contract. If it were accepted, language could become
    an implicit risk factor, which the product forbids.
    """
    from pydantic import ValidationError

    attempts = 0
    rejected = 0
    for episode in episodes:
        payload = episode.payload.model_dump(mode='json')
        for field, value in (('language', 'uz-UZ'), ('locale', 'uz-UZ'), ('citizenship', 'TJ'),
                             ('nationality', 'TJ'), ('ethnicity', 'x'), ('full_name', 'SYNTHETIC')):
            attempts += 1
            try:
                evaluate_snapshot({**payload, field: value})
            except (ValidationError, ValueError):
                rejected += 1
    return {
        'schema_version': 'LanguageInvarianceV1',
        'attempts': attempts,
        'rejected': rejected,
        'accepted': attempts - rejected,
        'all_rejected': attempts == rejected,
        'statement': ('The risk snapshot contract has no language, locale, citizenship or ethnicity field, '
                      'so none of them can reach the rules. Language is a presentation attribute only.'),
    }


def wilson(successes: int, n: int) -> list[float] | None:
    return wilson_interval(successes, n)


def artifact_hashes(output_dir: Path, names: list[str]) -> dict[str, str]:
    import hashlib

    hashes: dict[str, str] = {}
    for name in names:
        path = Path(output_dir) / name
        if path.is_file():
            hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes