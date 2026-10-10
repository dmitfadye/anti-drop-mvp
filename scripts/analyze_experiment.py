"""Unblind a collected scoring file and report descriptive estimates only.

    python -m scripts.analyze_experiment \
        --scored reports/experiment/collected.csv \
        --blinding-map reports/experiment/blinding_map.json \
        --declared-powered-n 400 \
        --output-dir reports/experiment

This script deliberately cannot print an uplift claim. `claim_permitted` is
hard-coded to False, and every warning is preserved in the output, because an
exploratory usability A/B with synthetic participants proves nothing about
banking outcomes.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.experiments import (  # noqa: E402
    UNBLINDED_COLUMNS,
    analyze_experiment,
    power_plan,
    read_csv,
    unblind,
    write_csv,
    write_json,
)

BOOLEAN_FIELDS = ('felt_accused', 'understood_next_step')
INT_FIELDS = ('presentation_order', 'time_to_action_ms', 'confidence')


def coerce(row: dict) -> dict:
    """CSV gives strings; the analysis needs real booleans and ints."""
    out = dict(row)
    for field in BOOLEAN_FIELDS:
        out[field] = str(out.get(field, '')).strip().lower() in ('true', '1', 'yes')
    for field in INT_FIELDS:
        try:
            out[field] = int(str(out.get(field, '0')).strip() or 0)
        except ValueError:
            out[field] = 0
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scored', type=Path, required=True)
    parser.add_argument('--blinding-map', type=Path, required=True)
    parser.add_argument('--declared-powered-n', type=int, default=0,
                        help='n per arm that a power analysis says is required; 0 means none declared')
    parser.add_argument('--baseline-rate', type=float, default=0.30, help='assumption for the power plan')
    parser.add_argument('--expected-uplift-pp', type=float, default=8.0, help='assumption for the power plan')
    parser.add_argument('--output-dir', type=Path, default=Path('reports/experiment'))
    args = parser.parse_args()

    try:
        raw = [coerce(row) for row in read_csv(args.scored)]
        mapping = json.loads(args.blinding_map.read_text(encoding='utf-8'))['entries']
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f'Analysis rejected: {exc}', file=sys.stderr)
        return 2
    if not raw:
        print('Analysis rejected: the scored file is empty. There is nothing to unblind.', file=sys.stderr)
        return 2

    rows = unblind(raw, mapping)
    analysis = analyze_experiment(rows, declared_powered_n=args.declared_powered_n)
    plan = power_plan(args.baseline_rate, args.expected_uplift_pp)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / 'unblinded_analysis_template.csv', rows, UNBLINDED_COLUMNS)
    write_json(args.output_dir / 'experiment_analysis.json', analysis)
    write_json(args.output_dir / 'power_plan.json', plan)
    (args.output_dir / 'power_analysis.md').write_text(_power_md(plan, analysis), encoding='utf-8')

    print(json.dumps({
        'rows': len(rows),
        'arms': {arm: data['n'] for arm, data in analysis['arms'].items()},
        'arm_difference': analysis['arm_difference'],
        'claim_permitted': analysis['claim_permitted'],
        'declared_powered_n_per_arm': analysis['declared_powered_n_per_arm'],
        'required_n_per_arm_from_assumptions': plan['required_n_per_arm'],
        'artifacts': sorted(str(path) for path in args.output_dir.glob('*')),
    }, ensure_ascii=False, indent=2))
    return 0


def _power_md(plan: dict, analysis: dict) -> str:
    lines = [
        '# Power analysis — planning only, NOT a pilot sample size', '',
        '> Inputs are ASSUMPTIONS from this repository, not measurements.',
        '> No powered experiment has been run. Nothing here proves uplift.', '',
        '| Parameter | Value |', '|---|---:|',
        f'| baseline safe action rate (assumption) | {plan["baseline_safe_action_rate"]} |',
        f'| expected uplift, percentage points (assumption) | {plan["expected_uplift_pp"]} |',
        f'| alpha | {plan["alpha"]} |',
        f'| power | {plan["power"]} |',
        f'| dropout rate | {plan["dropout_rate"]} |',
        f'| required n per arm | {plan["required_n_per_arm"]} |',
        f'| required n total | {plan["required_n_total"]} |', '',
        f'Status: `{plan["status"]}`.', '',
        '## Assumptions', '',
        *[f'- {item}' for item in plan['assumptions']], '',
        '## Collected sample so far', '',
        f'- control n: {analysis["arms"]["control"]["n"]}, treatment n: {analysis["arms"]["treatment"]["n"]}',
        f'- declared powered n per arm: {analysis["declared_powered_n_per_arm"] or "none declared"}',
        f'- claim permitted: {analysis["claim_permitted"]}', '',
        '## Warnings', '',
        *[f'- {warning}' for warning in analysis['warnings']], '',
        'A blank or tiny sample is not a weak result, it is a missing measurement.', '',
    ]
    return '\n'.join(lines)


if __name__ == '__main__':
    raise SystemExit(main())