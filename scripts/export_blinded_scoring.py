"""Build the blinded usability scoring export and its separate blinding map.

    python -m scripts.export_blinded_scoring --experiment-id exp-warning-language-2026.10 \
        --output reports/experiment/blinded_scoring_template.csv

Two files, deliberately separate:
- `blinded_scoring_template.csv` — what a participant sees and answers. It
  contains a blinded display id and no arm, no template, no locale.
- `blinding_map.json` — display id -> template/arm/locale. Opened only after
  collection, by scripts/analyze_experiment.py.

The rows are empty scaffolding for real collection. Nothing here fabricates
participant answers, and the template ships with zero filled rows on purpose.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.experiments import (  # noqa: E402
    BLINDED_COLUMNS,
    BLINDING_MAP_VERSION,
    build_blinding_map,
    blind_record,
    write_csv,
)
from src.templates import (  # noqa: E402
    CONTROL_LOCALE,
    CONTROL_TEMPLATE_ID,
    CONTROL_TEMPLATE_ID_YELLOW,
    TREATMENT_LOCALE,
    TREATMENT_TEMPLATE_ID,
    TREATMENT_TEMPLATE_ID_YELLOW,
)

SCENARIOS = [
    {'scenario_id': 'transit_red', 'risk_level': 'RED', 'template_id': CONTROL_TEMPLATE_ID, 'locale': CONTROL_LOCALE,
     'arm': 'control'},
    {'scenario_id': 'transit_red', 'risk_level': 'RED', 'template_id': TREATMENT_TEMPLATE_ID, 'locale': TREATMENT_LOCALE,
     'arm': 'treatment'},
    {'scenario_id': 'salary_cash_yellow', 'risk_level': 'YELLOW', 'template_id': CONTROL_TEMPLATE_ID_YELLOW,
     'locale': CONTROL_LOCALE, 'arm': 'control'},
    {'scenario_id': 'salary_cash_yellow', 'risk_level': 'YELLOW', 'template_id': TREATMENT_TEMPLATE_ID_YELLOW,
     'locale': TREATMENT_LOCALE, 'arm': 'treatment'},
]

EXPERIMENT_PLAN = '''# Experiment plan ? warning language (exp-warning-language-2026.10)

**Status: PLANNING DOCUMENT. Nothing has been run. `treatment_available: false`
because the `uz-UZ` translation is `draft` and no native or legal reviewer has
signed it.**

## Question

Does the same risk warning, shown in the client\'s own language instead of
Russian, change what the client does next?

Not: does the detector work, does the warning reduce fraud loss. Those need
different data and are not what this experiment measures.

## Design

| Field | Value |
|---|---|
| randomization unit | `subject_pseudonym` |
| assignment | deterministic hash of salt + experiment_id + subject |
| treatment share | 50% (`ANTI_DROP_EXPERIMENT_TREATMENT_PERCENT`) |
| control | `ru-RU`, `warning_ru_control_v1` / `warning_ru_control_yellow_v1` |
| treatment | `uz-UZ`, `warning_uz_treatment_v1` / `warning_uz_treatment_yellow_v1` |
| shared | one `RiskDecisionV1`, one `rule_version`, one `threshold_version` per subject |
| variable changed | template + locale only |
| scoring | blinded, `display_template_id` = `blin_<hash>` |
| analysis | intention-to-treat |

## Metrics

**Primary:** `safe_action_rate` uplift (`safe_action_chosen`, `accepted_advisory`).

**Secondary:** `understanding_rate`, `time_to_action_ms` (median and p90),
completion of the help flow.

**Guardrails:** `felt_accused_rate`, support contacts per 1000 warnings,
technical error rate, `translation_fallback_rate`, complaints.

## Gates before the pilot may start

- [ ] `uz-UZ` pack is `approved` (native review + legal review recorded)
- [ ] control copy is `approved` as well
- [ ] baseline `safe_action_rate` measured in a real usability session
- [ ] power plan recomputed from that baseline
- [ ] analysis code preregistered with a commit hash
- [ ] fixed analysis date, no interim looks

## Sample size

`required_n_two_proportions(baseline_rate, expected_uplift_pp, alpha, power, dropout)`
? an approximate planning figure for independent individuals, equal allocation.
It does not model clustering, event-rate multiplicity or interim looks. Run:

```
python -m scripts.analyze_experiment --scored <collected.csv> \
  --blinding-map reports/experiment/blinding_map.json --declared-powered-n 400
```

## Stopping

Stop for harm only: `felt_accused_rate` rising, support load over capacity, a
legal or privacy trigger, or a technical error rate above 2%. Stopping early
because the numbers look good destroys the result and is forbidden.

Full criteria: `configs/pilot_stop_criteria.json`.

## Claims this plan does not license

- "the language experiment showed uplift" ? nothing has been collected;
- "safe action rate improved by X pp" ? no data exists;
- "the treatment is production-ready" ? the translation is a machine draft.

Every analysis output carries `claim_permitted: false` until a powered sample
exists. `reports/experiment/blinded_scoring_template.csv` ships with zero filled
rows on purpose.
'''

UNDERSTANDING_QUESTIONS = [
    'q1: «Что сейчас произошло с моими операциями?» (open understanding check)',
    'q2: «Что банк предлагает сделать дальше?» (next-step check)',
    'q3: «Будет ли банк блокировать мои деньги?» (false-promise check: answer must be no)',
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment-id', default='exp-warning-language-2026.10')
    parser.add_argument('--output', type=Path, default=Path('reports/experiment/blinded_scoring_template.csv'))
    parser.add_argument('--blinding-map', type=Path, default=Path('reports/experiment/blinding_map.json'))
    parser.add_argument('--rubric', type=Path, default=Path('reports/experiment/understanding_questions.json'))
    parser.add_argument('--experiment-plan', type=Path, default=Path('reports/experiment/experiment_plan.md'))
    parser.add_argument('--rows', type=int, default=0, help='scaffolding rows to pre-create (no answers filled in)')
    args = parser.parse_args()

    mapping = build_blinding_map([
        (item['template_id'], item['locale'], item['arm'], item['scenario_id']) for item in SCENARIOS
    ])
    args.blinding_map.parent.mkdir(parents=True, exist_ok=True)
    args.blinding_map.write_text(json.dumps({
        'schema_version': BLINDING_MAP_VERSION,
        'experiment_id': args.experiment_id,
        'rule_version': None,
        'note': ('Open this only after collection is complete. It maps display_template_id to the real '
                 'template, arm and locale. It is stored apart from the participant-facing export.'),
        'entries': list(mapping.values()),
    }, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    now = datetime.now(timezone.utc)
    rows = []
    for index in range(args.rows):
        scenario = SCENARIOS[index % len(SCENARIOS)]
        record = {
            'template_id': scenario['template_id'],
            'participant_pseudonym': f'sub_participant{index + 1:04d}',
            'scenario_id': scenario['scenario_id'],
            'presentation_order': index // len(SCENARIOS) + 1,
            'risk_level': scenario['risk_level'],
            'action_choice': 'safe_action_chosen',
            'time_to_action_ms': 0,
            'confidence': 3,
            'felt_accused': False,
            'understood_next_step': True,
            'comments_no_pii': '',
            'collected_at': now.isoformat(),
        }
        rows.append(blind_record(record, mapping))

    write_csv(args.output, rows, BLINDED_COLUMNS)
    args.rubric.write_text(json.dumps({
        'schema_version': 'UnderstandingRubricV1',
        'experiment_id': args.experiment_id,
        'questions': UNDERSTANDING_QUESTIONS,
        'safe_actions': ['safe_action_chosen', 'accepted_advisory'],
        'unsafe_actions': ['unsafe_action_chosen', 'declined_advisory'],
        'status': 'EMPTY_TEMPLATE_NOT_COLLECTED',
        'note': 'No participant answers exist in this repository. Any analysis must run on collected data.',
    }, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    args.experiment_plan.write_text(EXPERIMENT_PLAN, encoding='utf-8')

    print(json.dumps({
        'experiment_plan': str(args.experiment_plan),
        'blinded_csv': str(args.output),
        'blinding_map': str(args.blinding_map),
        'scaffolding_rows': len(rows),
        'display_ids': sorted(mapping),
        'status': 'BLINDED_TEMPLATE_CREATED_NO_DATA',
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())