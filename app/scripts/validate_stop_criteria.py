"""Validate configs/pilot_stop_criteria.json before a pilot is authorised.

    python -m scripts.validate_stop_criteria --config configs/pilot_stop_criteria.json

Returns non-zero when the stop plan is incomplete, because "we forgot to define
the rollback" is a launch blocker, not a documentation nit. It also refuses a
config that tries to weaken an immediate-stop category such as real PII exposure.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REQUIRED_SECTIONS = ('schema_version', 'immediate_stop', 'pause_and_review', 'rollback',
                     'entry_gates', 'required_owners')
REQUIRED_ENTRY_GATES = ('owner_assigned', 'data_legal_security_approvals', 'reviewed_templates',
                        'access_controls', 'data_contract', 'instrumented_baseline', 'power_plan',
                        'support_capacity', 'stop_rollback_plan')
GATE_STATUSES = frozenset({'satisfied', 'partial', 'pending', 'blocked'})
MANDATORY_IMMEDIATE = ('confirmed_cross_subject_leak', 'unauthorised_banking_action', 'real_pii_exposure',
                       'unauthorised_payment_or_blocking_attempt', 'legal_or_privacy_incident')


def validate(config: dict) -> list[str]:
    problems: list[str] = []
    for section in REQUIRED_SECTIONS:
        if section not in config:
            problems.append(f'missing section: {section}')
    immediate = config.get('immediate_stop') or []
    if not isinstance(immediate, list):
        problems.append('immediate_stop must be a list')
        immediate = []
    codes = {item.get('code') for item in immediate if isinstance(item, dict)}
    for code in MANDATORY_IMMEDIATE:
        if code not in codes:
            problems.append(f'immediate_stop is missing the mandatory category: {code}')
    for item in immediate:
        if isinstance(item, dict) and item.get('severity') != 'immediate':
            problems.append(f'{item.get("code")}: severity must be "immediate"')
    gates = config.get('entry_gates') or {}
    if not isinstance(gates, dict):
        problems.append('entry_gates must be an object')
        gates = {}
    for gate in REQUIRED_ENTRY_GATES:
        entry = gates.get(gate)
        if entry is None:
            problems.append(f'entry gate missing: {gate}')
        elif isinstance(entry, dict) and entry.get('status') not in GATE_STATUSES:
            problems.append(f'{gate}: status must be one of {" | ".join(sorted(GATE_STATUSES))}')
    if not config.get('required_owners'):
        problems.append('at least one named owner role is required')
    for stage in config.get('pilot_stages') or []:
        if isinstance(stage, dict) and stage.get('proves_fraud_roi') is True:
            problems.append(f'stage {stage.get("id")}: a usability stage cannot prove fraud ROI')
    return problems


def ready_to_start(config: dict) -> bool:
    """A complete plan is still not a green light: every gate must be signed."""
    gates = config.get('entry_gates') or {}
    return bool(gates) and all(
        isinstance(entry, dict) and entry.get('status') == 'satisfied' for entry in gates.values()
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('configs/pilot_stop_criteria.json'))
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        print(f'Stop criteria rejected: {args.config.name} is unreadable ({type(exc).__name__})', file=sys.stderr)
        return 2
    problems = validate(config)
    if problems:
        print(json.dumps({'config': str(args.config), 'ok': False, 'problems': problems}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({
        'config': str(args.config),
        'ok': True,
        'ready_to_start': ready_to_start(config),
        'immediate_stop_categories': len(config.get('immediate_stop') or []),
        'pause_categories': len(config.get('pause_and_review') or []),
        'entry_gates': sorted((config.get('entry_gates') or {}).keys()),
        'note': ('A valid plan is a precondition, not evidence that the pilot may start. '
                 'ready_to_start stays false until a real owner signs every entry gate.'),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())