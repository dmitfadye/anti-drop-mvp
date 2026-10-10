"""Run from repository root: python -m anti_drop_ml.evaluation.runner --help.

P0 produced counts. P1 produces evidence: per-segment breakdowns, legitimate
negative reporting, threshold sensitivity, rule ablation, reason-code
co-occurrence, a subject/time-disjoint holdout split and a cost-weighted
threshold table.

Two reporting decisions are made explicitly so a reviewer cannot misread them:

- **Primary metrics** are computed over `normal`, `risk` and
  `legitimate_negative` episodes only. Edge and missing-data fixtures test
  boundary behaviour, not accuracy, and are reported separately.
- **Everything is synthetic.** `label_source` is `synthetic_placeholder`
  unless the dataset says otherwise, and the report says so in words as well
  as in the warnings list.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import StrictBool, ValidationError, model_validator

from anti_drop_ml.adapter import ADAPTER_VERSION, RULE_VERSION, THRESHOLD_VERSION, evaluate_snapshot
from anti_drop_ml.contracts import ClosedModel, EpisodeClass, LabelSource, Ref, RiskSnapshotV1
from anti_drop_ml.events import TEMPLATE_VERSION
from anti_drop_ml.evaluation import quality
from anti_drop_ml.evaluation.holdout import split_episodes, write_split
from anti_drop_ml.metrics import pr_curve, summarize
from src.policy import PROJECT_TZ

# Hours in project local time, diagnostics only.
HOUR_BUCKETS = {'night_00_05': set(range(0, 6)), 'morning_06_11': set(range(6, 12)),
                'day_12_17': set(range(12, 18)), 'evening_18_23': set(range(18, 24))}


class Episode(ClosedModel):
    episode_id: Ref
    subject_ref: Ref
    label: Literal['risk', 'normal']
    episode_class: EpisodeClass
    label_source: LabelSource
    is_holdout: StrictBool
    payload: RiskSnapshotV1

    @model_validator(mode='after')
    def consistent(self):
        if self.episode_class == 'unknown':
            raise ValueError('labeled episodes require a known episode_class')
        if self.subject_ref != self.payload.subject_ref:
            raise ValueError('episode subject_ref does not match snapshot')
        metadata = self.payload.metadata
        for key in ('label_source', 'is_holdout', 'episode_class'):
            if getattr(self, key) != getattr(metadata, key):
                raise ValueError(f'episode and snapshot metadata disagree: {key}')
        if metadata.label is not None and metadata.label != self.label:
            raise ValueError('conflicting labels')
        if metadata.episode_id is not None and metadata.episode_id != self.episode_id:
            raise ValueError('conflicting episode_id')
        return self


def load_episodes(path: Path) -> list[Episode]:
    """JSONL envelopes or snapshots with metadata labels; CSV with payload_json."""
    if path.suffix.lower() == '.csv':
        with path.open(encoding='utf-8-sig', newline='') as stream:
            raw = []
            for row in csv.DictReader(stream):
                payload = json.loads(row.pop('payload_json'))
                metadata = payload.get('metadata', {})
                for key in ('label_source', 'is_holdout'):
                    row.setdefault(key, metadata.get(key))
                if isinstance(row.get('is_holdout'), str):
                    if row['is_holdout'].lower() not in ('true', 'false'):
                        raise ValueError('CSV is_holdout must be true or false')
                    row['is_holdout'] = row['is_holdout'].lower() == 'true'
                raw.append({**row, 'payload': payload})
    else:
        raw = [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    episodes = []
    for index, row in enumerate(raw, 1):
        if row.get('schema_version') == 'RiskSnapshotV1':
            metadata = row.get('metadata', {})
            row = {**{key: metadata.get(key) for key in ('episode_id', 'label', 'episode_class', 'label_source', 'is_holdout')}, 'subject_ref': row.get('subject_ref'), 'payload': row}
        try:
            episodes.append(Episode.model_validate(row))
        except ValidationError:
            # No raw payload in CLI errors or generated artifacts.
            raise ValueError(f'invalid episode at record {index}; dataset rejected') from None
    if not episodes:
        raise ValueError('dataset is empty')
    ids = [e.episode_id for e in episodes]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate episode_id')
    groups: dict[str, set[bool]] = {}
    for episode in episodes:
        groups.setdefault(episode.subject_ref, set()).add(episode.is_holdout)
    if any(len(flags) > 1 for flags in groups.values()):
        raise ValueError('subject leakage between holdout and development episodes')
    return sorted(episodes, key=lambda e: e.episode_id)


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def _snapshot_features(episode: Episode) -> dict:
    """Diagnostics only: SIM profile, device novelty and local-time bucket."""
    transactions = episode.payload.transactions
    window_start = episode.payload.analysis_at.timestamp() - 60 * 60
    recent = [t for t in transactions if t.occurred_at.timestamp() >= window_start]
    older = [t for t in transactions if t.occurred_at.timestamp() < window_start]
    sim_values = sorted({t.sim_changed_days_ago for t in transactions if t.sim_changed_days_ago is not None})
    old_devices = {t.device_id for t in older if t.device_id}
    recent_devices = {t.device_id for t in recent if t.device_id}
    device_novel = bool(recent_devices - old_devices)
    hours = {t.occurred_at.astimezone(PROJECT_TZ).hour for t in transactions}
    bucket = next((name for name, hours_set in HOUR_BUCKETS.items() if hours & hours_set), 'unknown')
    if not sim_values and any(t.sim_changed_days_ago is None for t in transactions):
        sim_profile = 'null_only'
    elif not sim_values:
        sim_profile = 'absent'
    else:
        freshest = min(sim_values)
        sim_profile = f'fresh_{freshest}d' if freshest <= 2 else f'stale_{freshest}d'
    return {'sim_profile': sim_profile, 'device_novelty': device_novel, 'hour_bucket': bucket}


def _git_state() -> tuple[str | None, bool | None]:
    root = Path(__file__).resolve().parents[2]
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True))
    except (OSError, subprocess.CalledProcessError):
        return None, None
    return commit, dirty


def _load_scenario_catalog(dataset: Path) -> dict[str, dict]:
    """Best-effort scenario names from a sibling fixture catalog, if present."""
    for candidate in (dataset.parent / 'fixture_catalog_p1.json', dataset.parent / 'fixture_catalog.json'):
        if not candidate.is_file():
            continue
        try:
            data = json.loads(candidate.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            continue
        rows = data if isinstance(data, list) else data.get('episodes', []) if isinstance(data, dict) else []
        return {row['episode_id']: row for row in rows if isinstance(row, dict) and 'episode_id' in row}
    return {}


def _build_warnings(episodes: list[Episode], sources: list[str], catalog: dict[str, dict]) -> list[str]:
    warnings = [
        'Rule score is not probability. Warnings are not legal conclusions. No banking actions are performed.',
        'Wilson intervals assume independent episodes; repeated subjects and synthetic labels do not establish bank accuracy.',
        'PR threshold sweeps are descriptive; do not tune on a holdout used to report performance.',
        'Primary metrics cover normal/risk/legitimate_negative episodes only; edge and missing-data fixtures are boundary checks.',
        'The warning is post-event: without an approved pre-transfer mode the client is informed after the transaction, not before.',
    ]
    if any(source not in ('human_reviewed', 'bank_adjudicated') for source in sources):
        warnings.append('UNVALIDATED LABELS: synthetic_placeholder/unknown labels are pipeline fixtures, NOT validated banking accuracy.')
    if not all(e.is_holdout for e in episodes):
        warnings.append('Not an exclusively held-out evaluation. Independent human-reviewed holdout is required.')
    if not any(e.episode_class == 'legitimate_negative' for e in episodes):
        warnings.append('No legitimate negatives: false-positive assessment is incomplete.')
    if len(episodes) < 200:
        warnings.append(f'SMALL SAMPLE: {len(episodes)} episodes. Rates move a lot with one episode; do not quote them externally.')
    if catalog and all(row.get('adversarial') is not True for row in catalog.values()):
        warnings.append('No adversarial fixtures: rule evasion has not been probed in this run.')
    elif catalog:
        probed = sorted(row['scenario'] for row in catalog.values() if row.get('adversarial') is True)
        warnings.append(f'Adversarial fixtures present ({len(probed)}): {", ".join(probed)}. '
                        'They probe rule evasion and are expected to appear in the false-negative list.')
    warnings.append('NO BANK ADJUDICATION: no episode in this repository carries a bank-reviewed label.')
    warnings.append('Score bands are the rule score mapped to levels; nothing here is a calibrated probability of fraud.')
    return warnings


def run_evaluation(dataset: Path, output_dir: Path, positive_threshold: int | None = None,
                   positive_level: str = 'RED', rule_version: str = RULE_VERSION, holdout_only: bool = False,
                   cost_false_alert: float | None = None, cost_missed_risk: float | None = None,
                   prevalence: float | None = None, holdout_percent: int = 30,
                   write_holdout: bool = True, skip_ablation: bool = False) -> dict:
    if rule_version != RULE_VERSION:
        raise ValueError(f'unsupported rule version; implemented version is {RULE_VERSION}')
    if positive_level != 'RED':
        raise ValueError('only RED level is supported; use positive_threshold to sweep score')
    if positive_threshold is not None and (isinstance(positive_threshold, bool) or not isinstance(positive_threshold, int) or not 0 <= positive_threshold <= 100):
        raise ValueError('positive_threshold must be an integer between 0 and 100')
    episodes = load_episodes(dataset)
    if holdout_only:
        episodes = [e for e in episodes if e.is_holdout]
        if not episodes:
            raise ValueError('no holdout episodes')
    versions = {e.payload.metadata.dataset_version for e in episodes}
    if None in versions or len(versions) != 1:
        raise ValueError('require one explicit dataset_version per evaluation')

    catalog = _load_scenario_catalog(dataset)
    rows = []
    for episode in episodes:
        decision = evaluate_snapshot(episode.payload)
        rows.append({
            'episode_id': episode.episode_id, 'subject_ref': episode.subject_ref, 'label': episode.label,
            'episode_class': episode.episode_class, 'label_source': episode.label_source, 'is_holdout': episode.is_holdout,
            'score': decision.score, 'level': decision.level, 'evaluation_id': decision.evaluation_id,
            'predicted_positive': decision.level == 'RED' if positive_threshold is None else decision.score >= positive_threshold,
            'status': decision.status, 'reason_codes': list(decision.reason_codes),
            'has_missing_sim': decision.data_quality.has_missing_sim,
            'has_missing_device': decision.data_quality.has_missing_device,
            'scenario': catalog.get(episode.episode_id, {}).get('scenario'),
            **_snapshot_features(episode),
        })

    primary = [row for row in rows if row['episode_class'] in quality.PRIMARY_CLASSES]
    edge = [row for row in rows if row['episode_class'] in quality.EDGE_CLASSES]
    summary = summarize(primary)
    all_summary = summarize(rows)
    sources = sorted({e.label_source for e in episodes})
    warnings = _build_warnings(episodes, sources, catalog)

    breakdown: dict[str, dict] = {}
    segments = []

    def add_segment(segment_type: str, value: str, rows_in: list[dict], note: str = '') -> None:
        metrics = summarize(rows_in) if rows_in else summarize([])
        scope = 'primary' if rows_in and all(row['episode_class'] in quality.PRIMARY_CLASSES for row in rows_in) else 'all'
        breakdown.setdefault(segment_type, {})[value] = metrics
        segments.append({'segment_type': segment_type, 'segment': value, 'scope': scope,
                         **{k: metrics[k] for k in ('total_episodes', 'TP', 'FP', 'TN', 'FN')},
                         **{k: metrics[k]['value'] for k in ('recall', 'precision', 'fpr', 'alert_rate')},
                         'note': note})

    for value in ('normal', 'risk', 'legitimate_negative', 'edge'):
        add_segment('episode_class', value, [row for row in rows if row['episode_class'] == value])
    for value in sources:
        add_segment('label_source', value, [row for row in rows if row['label_source'] == value],
                    note='synthetic_placeholder is not validated accuracy')
    for flag in (False, True):
        add_segment('is_holdout', str(flag).lower(), [row for row in rows if row['is_holdout'] == flag])
    for value in sorted({row['sim_profile'] for row in rows}):
        add_segment('sim_profile', value, [row for row in rows if row['sim_profile'] == value],
                    note='null means unknown, not zero days')
    for value in (False, True):
        add_segment('device_novelty', str(value).lower(), [row for row in rows if row['device_novelty'] == value])
    for value in sorted({row['hour_bucket'] for row in rows}):
        add_segment('hour_bucket_local', value, [row for row in rows if row['hour_bucket'] == value],
                    note='diagnostics only: night hours partially drive the score in this rule set')

    metrics = {
        'schema_version': 'EvaluationMetricsV1',
        'scope': {
            'primary_episode_classes': list(quality.PRIMARY_CLASSES),
            'edge_episode_classes': list(quality.EDGE_CLASSES),
            'positive_definition': 'level == RED' if positive_threshold is None else f'score >= {positive_threshold}',
        },
        'overall': summary,
        'overall_all_classes': all_summary,
        'breakdown': breakdown,
        'edge_case_behavior_summary': quality.edge_case_behavior(rows),
        'missing_data_rate': quality.missing_data_summary(rows),
        'error_patterns': quality.error_patterns(rows, catalog),
        'language_invariance': quality.language_invariance_check(episodes),
        'warnings': warnings,
    }

    commit, dirty = _git_state()
    evaluation_threshold_version = THRESHOLD_VERSION if positive_threshold is None else f'evaluation-score-ge-{positive_threshold}-v1'
    manifest = {
        'dataset_version': next(iter(versions)),
        'dataset_sha256': hashlib.sha256(dataset.read_bytes()).hexdigest(),
        'rule_version': RULE_VERSION,
        'threshold_version': evaluation_threshold_version,
        'detector_threshold_version': THRESHOLD_VERSION,
        'adapter_version': ADAPTER_VERSION,
        'template_version': TEMPLATE_VERSION,
        'positive_definition': metrics['scope']['positive_definition'],
        'number_of_episodes': len(rows),
        'number_of_primary_episodes': len(primary),
        'number_of_edge_episodes': len(edge),
        'label_sources': sources,
        'holdout_status': 'holdout_only' if all(e.is_holdout for e in episodes) else 'development_only' if not any(e.is_holdout for e in episodes) else 'mixed_reported_separately',
        'environment': quality.environment_fingerprint(),
        'experiment_id': None,
        'random_seed': None,
        'warnings': warnings,
        'git_commit': commit,
        'git_worktree_dirty': dirty,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }

    # Holdout split before writing anything, so a split failure leaves no reports.
    split = split_episodes(episodes, holdout_percent) if write_holdout else None
    manifest['holdout_split'] = {
        'written': bool(write_holdout),
        'holdout_percent': holdout_percent,
        'development_episodes': len(split.development) if split else None,
        'holdout_episodes': len(split.holdout) if split else None,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    for name, data in [('metrics.json', metrics), ('evaluation_manifest.json', manifest), ('episode_decisions.json', rows)]:
        (output_dir / name).write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')

    write_csv(output_dir / 'confusion_matrix.csv',
              [{'actual': 'risk', 'predicted_positive': summary['TP'], 'predicted_negative': summary['FN']},
               {'actual': 'normal', 'predicted_positive': summary['FP'], 'predicted_negative': summary['TN']}],
              ['actual', 'predicted_positive', 'predicted_negative'])
    write_csv(output_dir / 'pr_curve.csv', pr_curve(primary),
              ['threshold', 'precision', 'recall', 'fpr', 'TP', 'FP', 'TN', 'FN'])
    write_csv(output_dir / 'segment_breakdown.csv', segments,
              ['segment_type', 'segment', 'scope', 'total_episodes', 'TP', 'FP', 'TN', 'FN', 'recall', 'precision',
               'fpr', 'alert_rate', 'note'])
    write_csv(output_dir / 'threshold_sensitivity.csv', quality.threshold_sensitivity(rows),
              ['score_threshold', 'alert_level_equivalent', 'TP', 'FP', 'TN', 'FN', 'recall', 'precision', 'fpr',
               'legitimate_negative_alert_rate', 'alert_rate'])
    write_csv(output_dir / 'reason_cooccurrence.csv', quality.reason_cooccurrence(rows),
              ['reason_code_a', 'reason_code_b', 'episodes_with_a', 'episodes_with_b', 'episodes_with_both', 'jaccard'])
    if not skip_ablation:
        write_csv(output_dir / 'rule_ablation.csv', quality.rule_ablation(episodes, rows),
                  ['configuration', 'rule', 'disabled', 'recall', 'fpr', 'alert_rate', 'delta_recall', 'delta_fpr',
                   'delta_alert_rate', 'TP', 'FP', 'TN', 'FN'])
    if cost_false_alert is not None and cost_missed_risk is not None:
        business = quality.business_thresholds(rows, cost_false_alert, cost_missed_risk,
                                               prevalence if prevalence is not None else 0.0)
        (output_dir / 'business_thresholds.json').write_text(
            json.dumps(business, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
        write_csv(output_dir / 'business_thresholds.csv',
                  [{'score_threshold': row['score_threshold'], 'alerts': row['alerts'], 'TP': row['TP'], 'FP': row['FP'],
                    'FN': row['FN'], 'expected_cost': row['expected_cost'],
                    'expected_cost_per_1000_episodes': row['expected_cost_per_1000_episodes'], 'recall': row['recall']}
                   for row in business['rows']],
                  ['score_threshold', 'alerts', 'TP', 'FP', 'FN', 'expected_cost', 'expected_cost_per_1000_episodes', 'recall'])
    if split is not None:
        write_split(split, output_dir)

    (output_dir / 'report.md').write_text(_report(metrics, manifest, summary, breakdown, segments), encoding='utf-8')
    _write_legitimate_reports(output_dir, rows, summary)
    (output_dir / 'warnings.md').write_text(_warnings_md(metrics, manifest), encoding='utf-8')

    metrics['manifest'] = manifest
    return metrics


def _fmt(value: float | None, digits: int = 4) -> str:
    return 'undefined' if value is None else f'{value:.{digits}f}'


def _rate_row(name: str, rate: dict) -> str:
    ci = 'undefined (n=0)' if rate['wilson_95_ci'] is None else ' – '.join(f'{v:.4f}' for v in rate['wilson_95_ci'])
    return f'| {name} | {_fmt(rate["value"])} | {ci} |'


def _report(metrics: dict, manifest: dict, summary: dict, breakdown: dict, segments: list[dict]) -> str:
    lines = [
        '# Synthetic detector evaluation — P1 quality evidence pack', '',
        *[f'> {warning}' for warning in metrics['warnings']], '',
        '## What this report is and is not', '',
        '- Score is a deterministic rule score. **It is not a probability of fraud.**',
        '- Labels are `synthetic_placeholder`. **Synthetic labels are not validated bank accuracy.**',
        '- **The real banking effect is not measured.** No pilot ran, no bank adjudicated anything.',
        '- Legitimate negatives are the critical part of this report: a detector that never cries wolf on',
        '  family collections is worth more than one with a higher recall on synthetic attacks.',
        '- **Language is not a risk factor.** The snapshot contract has no language field at all;',
        '  presentation language is a UX attribute only.',
        '- The warning is **post-event**: without an approved pre-transfer mode the client is told after',
        '  the transaction, not before it.',
        '- A sandbox case is **not a real bank support request**: nothing is blocked, frozen or contacted.', '',
        '## Run identity', '',
        f'- dataset: `{manifest["dataset_version"]}` (sha256 `{manifest["dataset_sha256"][:16]}…`)',
        f'- rules: `{manifest["rule_version"]}`, thresholds: `{manifest["threshold_version"]}`'
        f' (detector `{manifest["detector_threshold_version"]}`), adapter: `{manifest["adapter_version"]}`',
        f'- positive definition: `{manifest["positive_definition"]}`',
        f'- episodes: {manifest["number_of_episodes"]} total, {manifest["number_of_primary_episodes"]} primary,'
        f' {manifest["number_of_edge_episodes"]} edge/missing-data',
        f'- label sources: {", ".join(manifest["label_sources"]) or "none"}',
        f'- holdout status: `{manifest["holdout_status"]}`',
        f'- python: {manifest["environment"]["python_version"]} ({manifest["environment"]["platform"]}),'
        f' git commit: {manifest["git_commit"] or "unknown"} (dirty: {manifest["git_worktree_dirty"]})',
        f'- generated at: {manifest["timestamp"]}', '',
        '## Counts and rates (primary classes only)', '',
        '| Metric | Estimate | Wilson 95% CI |', '|---|---:|---|',
    ]
    for name in ('recall', 'precision', 'fpr', 'fnr', 'alert_rate', 'legitimate_negative_alert_rate'):
        lines.append(_rate_row(name, summary[name]))
    lines += ['', f'TP={summary["TP"]}, FP={summary["FP"]}, TN={summary["TN"]}, FN={summary["FN"]}.',
              '', '## Segments', '', '| Segment type | Segment | N | TP | FP | TN | FN | FPR |', '|---|---|---:|---:|---:|---:|---:|---:|']
    for row in segments:
        lines.append(f'| {row["segment_type"]} | {row["segment"]} | {row["total_episodes"]} | {row["TP"]} | {row["FP"]} | {row["TN"]} | {row["FN"]} | {_fmt(row["fpr"])} |')
    edge = metrics['edge_case_behavior_summary']
    missing = metrics['missing_data_rate']
    patterns = metrics['error_patterns']
    invariance = metrics['language_invariance']
    lines += [
        '', '## Edge cases and missing data', '',
        f'- edge/boundary episodes: {edge["episodes"]}, levels: {edge["levels"]}',
        f'- episodes flagged `borderline_window`: {edge["borderline_window_flagged"]}',
        f'- episodes with `insufficient_data`: {len(edge["insufficient_data_episodes"])}',
        f'- missing SIM rate: {_fmt(missing["missing_sim"]["rate"])}; missing device rate: {_fmt(missing["missing_device"]["rate"])}', '',
        '## Error patterns', '',
        f'- false positives: {patterns["false_positive_count"]}, false negatives: {patterns["false_negative_count"]}',
        *[f'  - {item["reason_code_shape"]}: {item["count"]} ({", ".join(item["scenario_names"][:5])})' for item in patterns['top_false_positive_patterns'][:5]],
        *[f'  - FN {item["reason_code_shape"]}: {item["count"]} ({", ".join(item["scenario_names"][:5])})' for item in patterns['top_false_negative_patterns'][:5]],
        *[f'  - {line}' for line in patterns['interpretation']], '',
        '## Language invariance', '',
        f'- {invariance["attempts"]} attempts to inject language/locale/nationality/ethnicity/name into a snapshot,'
        f' {invariance["rejected"]} rejected, {invariance["accepted"]} accepted.', '',
        '## Companion artifacts', '',
        '- `legitimate_negative_report.md` — false-positive detail on legitimate scenarios',
        '- `threshold_sensitivity.csv` — score sweep over the primary classes',
        '- `business_thresholds.csv` / `business_thresholds.json` — cost-weighted thresholds (assumptions!)',
        '- `rule_ablation.csv` — each rule removed in turn',
        '- `reason_cooccurrence.csv` — which rules charge for the same pattern twice',
        '- `holdout_manifest.json` + `holdout_development.jsonl` / `holdout_holdout.jsonl` — subject/time-disjoint split',
        '- `warnings.md` — the same caveats as a standalone checklist',
    ]
    return '\n'.join(lines) + '\n'


def _write_legitimate_reports(output_dir: Path, rows: list[dict], summary: dict) -> None:
    negatives = [row for row in rows if row['episode_class'] == 'legitimate_negative']
    negatives_summary = summarize(negatives)
    alerted = [row for row in negatives if row['predicted_positive']]
    lines = [
        '# Legitimate negatives — synthetic fixtures only', '',
        'Not validated banking accuracy. These fixtures exist to measure false-positive sensitivity on',
        'scenarios that look superficially like the attack: family collections, salary plus cash,',
        'recurring payments, night work, a new device, a fresh SIM, inbound-only bursts.', '',
        *[f'> {warning}' for warning in [
            'No episode here was reviewed by a human analyst or a bank.',
            'A silent legitimate negative still produces a monitoring signal; YELLOW is not "nothing".',
            'A self-declared purpose (family_collection) does not override the observable flow.',
        ]], '',
        '## Counts', '',
        '| Metric | Estimate | Wilson 95% CI |', '|---|---:|---|',
        _rate_row('legitimate_negative_alert_rate', negatives_summary['legitimate_negative_alert_rate']),
        _rate_row('alert_rate', negatives_summary['alert_rate']), '',
        f'Alerted legitimate negatives: {len(alerted)} of {len(negatives)}.', '',
        '## Per-scenario behaviour', '',
        '| Scenario | Class | Label | Level | Score | Reason codes |', '|---|---|---|---|---:|---|',
    ]
    for row in sorted(negatives, key=lambda item: (item['episode_class'], item['episode_id'])):
        lines.append(f'| {row.get("scenario") or row["episode_id"]} | {row["episode_class"]} | {row["label"]} |'
                     f' {row["level"]} | {row["score"]} | {", ".join(row["reason_codes"]) or "—"} |')
    lines += ['', '## Known trade-off', '',
              '`family_collection_then_small_rent` and `many_inbound_without_outbound` deliberately resemble the',
              'attack at the observable level. The detector keeps them below RED; if thresholds are lowered, these',
              'are the fixtures that will alert first. That is the trade-off the pilot has to price, not hide.', '']
    text = '\n'.join(lines)
    (output_dir / 'legitimate_negative_report.md').write_text(text, encoding='utf-8')
    (output_dir / 'legitimate_negatives_report.md').write_text(
        '# Legitimate negatives (legacy filename)\n\nSee legitimate_negative_report.md for the full report.\n', encoding='utf-8')


def _warnings_md(metrics: dict, manifest: dict) -> str:
    lines = ['# Evaluation warnings', '',
             'Read this before quoting any number from `metrics.json`.', '',
             '## Sample', '',
             f'- episodes: {manifest["number_of_episodes"]} (primary {manifest["number_of_primary_episodes"]}, edge {manifest["number_of_edge_episodes"]})',
             f'- label sources: {", ".join(manifest["label_sources"]) or "none"}',
             f'- holdout status: `{manifest["holdout_status"]}`', '',
             '## Generated warnings', '']
    lines += [f'- {warning}' for warning in metrics['warnings']]
    lines += ['', '## Claims this repository does NOT support', '',
              '- "recall 1.0" or "recall 90%" as a bank accuracy figure — labels are synthetic.',
              '- "we prevented a transfer" — the data already contains the outgoing transfer.',
              '- "works in 7 languages" — one target locale pack exists and it is a draft.',
              '- "ROI positive" — the base financial case is close to or below break-even by construction.',
              '- "supports real clients" — there is no authentication, no real data path and no bank integration.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--positive-level', choices=['RED'], default='RED')
    parser.add_argument('--positive-threshold', type=int)
    parser.add_argument('--rule-version', default=RULE_VERSION)
    parser.add_argument('--holdout-only', action='store_true')
    parser.add_argument('--holdout-percent', type=int, default=30)
    parser.add_argument('--no-holdout-split', dest='write_holdout', action='store_false')
    parser.add_argument('--skip-ablation', action='store_true')
    parser.add_argument('--cost-false-alert', type=float, help='assumption: rubles per false alert')
    parser.add_argument('--cost-missed-risk', type=float, help='assumption: rubles per missed risk episode')
    parser.add_argument('--prevalence', type=float, help='assumption: risk episode prevalence')
    args = parser.parse_args()
    try:
        metrics = run_evaluation(**vars(args))
    except (ValueError, OSError, KeyError, TypeError):
        parser.exit(2, 'Evaluation rejected: invalid dataset/configuration or inaccessible files. No raw payload is printed.\n')
    print(f'Evaluated {metrics["overall"]["total_episodes"]} primary episodes. See report.md and warnings.md for limitations.')


if __name__ == '__main__':
    main()