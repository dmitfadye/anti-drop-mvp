"""Deterministic experiment assignment for a synthetic subject list.

    python -m scripts.run_experiment_assignment --experiment-id exp-warning-language-2026.10 \
        --treatment-percent 50 --output reports/experiment/assignments.jsonl

Rules of the road:
- the randomization unit is `subject_pseudonym`, never a phone or a name;
- assignment is a pure function of (salt, experiment_id, subject), so reruns
  produce the same arms;
- if the treatment template is not `approved`, the assignment is recorded as
  `control` with the reason attached. `--allow-draft-treatment` exists to
  demonstrate the draft path in a demo, and it is written into the artifact.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from anti_drop_ml.adapter import RULE_VERSION, THRESHOLD_VERSION  # noqa: E402
from anti_drop_ml.event_log import append_event, new_event_id  # noqa: E402
from src.experiments import assign  # noqa: E402
from src.flags import current_flags  # noqa: E402


def read_subjects(path: Path) -> list[str]:
    """Read one pseudonymous subject ref per line, or from a JSON array."""
    # utf-8-sig: editors on Windows add a BOM, which would otherwise poison the first ref.
    text = path.read_text(encoding='utf-8-sig').strip()
    if text.startswith('['):
        rows = json.loads(text)
    else:
        rows = [line.strip() for line in text.splitlines() if line.strip()]
    subjects = []
    for row in rows:
        value = row if isinstance(row, str) else row.get('subject_pseudonym')
        if not isinstance(value, str) or not value.startswith('sub_'):
            raise ValueError('subject_pseudonym must be a sub_ pseudonymous ref; raw identifiers are refused')
        subjects.append(value)
    if not subjects:
        raise ValueError('no subjects supplied')
    return sorted(set(subjects))


def main() -> int:
    flags = current_flags()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment-id', default='exp-warning-language-2026.10')
    parser.add_argument('--subjects', type=Path, required=True, help='file with one sub_ ref per line')
    parser.add_argument('--treatment-percent', type=int, default=flags.treatment_percent)
    parser.add_argument('--allow-draft-treatment', action='store_true',
                        help='demo only: permit an arm whose translation is still draft')
    parser.add_argument('--output', type=Path, default=Path('reports/experiment/assignments.jsonl'))
    parser.add_argument('--event-log', default='', help='optional local JSON-lines sink')
    args = parser.parse_args()

    try:
        subjects = read_subjects(args.subjects)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f'Assignment rejected: {exc}', file=sys.stderr)
        return 2

    now = datetime.now(timezone.utc)
    rows = []
    for subject in subjects:
        assignment = assign(args.experiment_id, subject, RULE_VERSION, THRESHOLD_VERSION,
                            args.treatment_percent, allow_draft_treatment=args.allow_draft_treatment,
                            assigned_at=now)
        rows.append(assignment.model_dump(mode='json'))
        append_event({
            'event_id': new_event_id(),
            'event_type': 'experiment_assigned',
            'timestamp': now.isoformat(),
            'evaluation_id': '0' * 64,
            'experiment_id': args.experiment_id,
            'experiment_arm': assignment.arm,
            'rule_version': RULE_VERSION,
            'threshold_version': THRESHOLD_VERSION,
            'subject_pseudonym': subject,
            'outcome_code': f'arm_{assignment.arm}',
            'metadata': {'assignment_method': 'deterministic_hash'},
        }, args.event_log or None)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(''.join(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n' for row in rows),
                           encoding='utf-8')
    arms = {arm: sum(1 for row in rows if row['arm'] == arm) for arm in ('control', 'treatment')}
    blocked = sorted({row['treatment_blocked_reason'] for row in rows if row['treatment_blocked_reason']})
    print(json.dumps({
        'assignments': len(rows),
        'arms': arms,
        'experiment_id': args.experiment_id,
        'rule_version': RULE_VERSION,
        'threshold_version': THRESHOLD_VERSION,
        'allow_draft_treatment': args.allow_draft_treatment,
        'treatment_blocked_reasons': blocked,
        'event_log': args.event_log or 'disabled',
        'status': 'EXPLORATORY_NO_UPLIFT_CLAIM',
        'output': str(args.output),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())