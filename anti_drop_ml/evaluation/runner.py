"""Run from repository root: python -m anti_drop_ml.evaluation.runner --help."""
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
from anti_drop_ml.metrics import pr_curve, summarize


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
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def run_evaluation(dataset: Path, output_dir: Path, positive_threshold: int | None = None, positive_level: str = 'RED', rule_version: str = RULE_VERSION, holdout_only: bool = False) -> dict:
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
    rows = []
    for episode in episodes:
        decision = evaluate_snapshot(episode.payload)
        rows.append({'episode_id': episode.episode_id, 'subject_ref': episode.subject_ref, 'label': episode.label, 'episode_class': episode.episode_class, 'label_source': episode.label_source, 'is_holdout': episode.is_holdout, 'score': decision.score, 'level': decision.level, 'evaluation_id': decision.evaluation_id, 'predicted_positive': decision.level == 'RED' if positive_threshold is None else decision.score >= positive_threshold})
    summary = summarize(rows)
    sources = sorted({e.label_source for e in episodes})
    warnings = ['Rule score is not probability. Warnings are not legal conclusions. No banking actions are performed.', 'Wilson intervals assume independent episodes; repeated subjects and synthetic labels do not establish bank accuracy.', 'PR threshold sweeps are descriptive; do not tune on a holdout used to report performance.']
    if any(source not in ('human_reviewed', 'bank_adjudicated') for source in sources):
        warnings.append('UNVALIDATED LABELS: synthetic_placeholder/unknown labels are pipeline fixtures, NOT validated banking accuracy.')
    if not all(e.is_holdout for e in episodes):
        warnings.append('Not an exclusively held-out evaluation. Independent human-reviewed holdout is required.')
    if not any(e.episode_class == 'legitimate_negative' for e in episodes):
        warnings.append('No legitimate negatives: false-positive assessment is incomplete.')
    breakdown = {}
    segments = []
    for field, values in [('episode_class', ['normal', 'risk', 'legitimate_negative', 'edge']), ('label_source', sources), ('is_holdout', [False, True])]:
        breakdown[field] = {}
        for value in values:
            metrics = summarize([r for r in rows if r[field] == value])
            breakdown[field][str(value).lower()] = metrics
            segments.append({'segment_type': field, 'segment': str(value).lower(), **{k: metrics[k] for k in ('total_episodes', 'TP', 'FP', 'TN', 'FN')}, **{k: metrics[k]['value'] for k in ('recall', 'precision', 'fpr', 'alert_rate')}})
    metrics = {'schema_version': 'EvaluationMetricsV1', 'overall': summary, 'breakdown': breakdown, 'warnings': warnings}
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=Path(__file__).resolve().parents[2], text=True, stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=Path(__file__).resolve().parents[2], text=True))
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = None, None
    evaluation_threshold_version = THRESHOLD_VERSION if positive_threshold is None else f'evaluation-score-ge-{positive_threshold}-v1'
    manifest = {'dataset_version': next(iter(versions)), 'dataset_sha256': hashlib.sha256(dataset.read_bytes()).hexdigest(), 'rule_version': RULE_VERSION, 'threshold_version': evaluation_threshold_version, 'detector_threshold_version': THRESHOLD_VERSION, 'adapter_version': ADAPTER_VERSION, 'template_version': TEMPLATE_VERSION, 'positive_definition': 'level == RED' if positive_threshold is None else f'score >= {positive_threshold}', 'number_of_episodes': len(rows), 'label_sources': sources, 'holdout_status': 'holdout_only' if all(e.is_holdout for e in episodes) else 'development_only' if not any(e.is_holdout for e in episodes) else 'mixed_reported_separately', 'warnings': warnings, 'git_commit': commit, 'git_worktree_dirty': dirty, 'timestamp': datetime.now(timezone.utc).isoformat()}
    # Validate every record before creating or overwriting reports.
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, data in [('metrics.json', metrics), ('evaluation_manifest.json', manifest), ('episode_decisions.json', rows)]:
        (output_dir/name).write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')
    write_csv(output_dir/'confusion_matrix.csv', [{'actual': 'risk', 'predicted_positive': summary['TP'], 'predicted_negative': summary['FN']}, {'actual': 'normal', 'predicted_positive': summary['FP'], 'predicted_negative': summary['TN']}], ['actual', 'predicted_positive', 'predicted_negative'])
    write_csv(output_dir/'pr_curve.csv', pr_curve(rows), ['threshold', 'precision', 'recall', 'fpr', 'TP', 'FP', 'TN', 'FN'])
    write_csv(output_dir/'segment_breakdown.csv', segments, ['segment_type', 'segment', 'total_episodes', 'TP', 'FP', 'TN', 'FN', 'recall', 'precision', 'fpr', 'alert_rate'])
    lines = ['# Synthetic detector evaluation', '', *['> '+warning for warning in warnings], '', f'Dataset: {manifest["dataset_version"]}; rules: {RULE_VERSION}; thresholds: {evaluation_threshold_version}.', f'Positive definition: {manifest["positive_definition"]}. Episodes: {len(rows)}.', '', '| Metric | Estimate | Wilson 95% CI |', '|---|---:|---|']
    for name in ('recall', 'precision', 'fpr', 'fnr', 'alert_rate', 'legitimate_negative_alert_rate'):
        rate = summary[name]
        value = 'undefined' if rate['value'] is None else f'{rate["value"]:.4f}'
        ci = 'undefined (n=0)' if rate['wilson_95_ci'] is None else ' – '.join(f'{v:.4f}' for v in rate['wilson_95_ci'])
        lines.append(f'| {name} | {value} | {ci} |')
    lines += ['', f'TP={summary["TP"]}, FP={summary["FP"]}, TN={summary["TN"]}, FN={summary["FN"]}.', '', '## Legitimate negatives', '', 'See legitimate_negatives_report.md for separate counts and alerted fixture IDs.', '', '## Segments', '', '| Class | N | FP | FN |', '|---|---:|---:|---:|']
    for name, values in breakdown['episode_class'].items():
        lines.append(f'| {name} | {values["total_episodes"]} | {values["FP"]} | {values["FN"]} |')
    (output_dir/'report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    legitimate = [r for r in rows if r['episode_class'] == 'legitimate_negative']
    (output_dir/'legitimate_negatives_report.md').write_text('# Legitimate negatives — synthetic fixtures only\n\nNot validated banking accuracy. These cases test false-positive sensitivity.\n\n'+json.dumps(summarize(legitimate), indent=2)+'\n\nAlerted episode IDs:\n'+ '\n'.join('- '+r['episode_id'] for r in legitimate if r['predicted_positive'])+'\n', encoding='utf-8')
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--positive-level', choices=['RED'], default='RED')
    parser.add_argument('--positive-threshold', type=int)
    parser.add_argument('--rule-version', default=RULE_VERSION)
    parser.add_argument('--holdout-only', action='store_true')
    args = parser.parse_args()
    try:
        metrics = run_evaluation(**vars(args))
    except (ValueError, OSError, KeyError, TypeError):
        parser.exit(2, 'Evaluation rejected: invalid dataset/configuration or inaccessible files. No raw payload is printed.\n')
    print(f'Evaluated {metrics["overall"]["total_episodes"]} episodes. See report.md for limitations.')


if __name__ == '__main__':
    main()
