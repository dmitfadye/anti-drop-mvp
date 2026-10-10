"""Experiment instrumentation: one decision, two languages, honest bookkeeping.

The experiment is designed so a negative result is still a valid result:

- assignment is a deterministic hash of (salt, experiment_id, subject pseudonym),
  so it is reproducible, sticky per subject and needs no state store;
- the randomization unit is the subject, so both arms observe the *same*
  RiskDecisionV1 and the only difference is template + locale;
- a treatment arm whose template is not `approved` is refused, not silently
  downgraded to a different copy;
- blinding maps a display id to the real template/arm and is kept apart from
  the participant-facing export;
- analysis reports exploratory estimates with Wilson intervals and refuses to
  print an uplift claim without an explicit powered-sample declaration.

No participant data is stored here: participants are pseudonymous ids, and no
banking action is reachable from this module.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Iterable, Literal

from pydantic import Field, StrictBool, StrictInt, field_validator

from anti_drop_ml.contracts import ClosedModel, Ref, aware_utc
from anti_drop_ml.events import ProductEventV1
from anti_drop_ml.metrics import wilson_interval
from anti_drop_ml.power import required_n_two_proportions
from src.templates import CONTROL_LOCALE, CONTROL_TEMPLATE_ID, TREATMENT_LOCALE, TREATMENT_TEMPLATE_ID, resolve_pair

EXPERIMENT_SCHEMA_VERSION = 'ExperimentAssignmentV1'
ASSIGNMENT_METHOD = 'deterministic_hash'
ASSIGNMENT_SALT_VERSION = 'salt-v1'

Arm = Literal['control', 'treatment']
AssignmentStatus = Literal['active', 'paused', 'completed']

UnderstandingActions = Literal['safe_action_chosen', 'unsafe_action_chosen', 'declined_advisory', 'accepted_advisory']

EXPERIMENT_EVENT_TYPES = (
    'experiment_assigned', 'alert_delivered', 'alert_viewed', 'template_rendered', 'language_selected',
    'translation_fallback', 'help_started', 'case_created', 'case_confirmed', 'safe_action_confirmed',
    'understanding_survey_submitted', 'scoring_recorded', 'request_failed',
)

ACTION_CODES = frozenset({'safe_action_chosen', 'unsafe_action_chosen', 'declined_advisory', 'accepted_advisory'})


class ExperimentConfigError(ValueError):
    """Invalid experiment configuration; refuses to assign."""


class ExperimentAssignmentV1(ClosedModel):
    schema_version: Literal['ExperimentAssignmentV1'] = EXPERIMENT_SCHEMA_VERSION
    experiment_id: str = Field(pattern=r'^exp-[a-z0-9.-]{1,60}$')
    # The randomisation unit is a subject, so it must be a subject-shaped ref.
    # A counterparty or device ref here would mean the wrong unit of analysis.
    subject_pseudonym: str = Field(pattern=r'^sub_[a-f0-9]{8,64}$')
    arm: Arm
    assignment_method: Literal['deterministic_hash'] = ASSIGNMENT_METHOD
    assignment_salt_version: str = Field(default=ASSIGNMENT_SALT_VERSION, pattern=r'^[a-zA-Z0-9._-]{1,40}$')
    rule_version: str = Field(pattern=r'^[a-zA-Z0-9._-]{1,80}$')
    threshold_version: str = Field(pattern=r'^[a-zA-Z0-9._-]{1,80}$')
    control_template_id: str = Field(pattern=r'^[a-z0-9_]{3,64}$')
    treatment_template_id: str = Field(pattern=r'^[a-z0-9_]{3,64}$')
    assigned_at: datetime
    status: AssignmentStatus = 'active'
    # Why the arm could not be treatment, when true. Never null-but-ignored.
    treatment_blocked_reason: str | None = Field(default=None, max_length=200)

    _time = field_validator('assigned_at', mode='before')(aware_utc)


def deterministic_bucket(experiment_id: str, subject_pseudonym: str, salt_version: str = ASSIGNMENT_SALT_VERSION) -> int:
    """Stable 0..99 bucket. Pure function of its inputs, no clock, no randomness."""
    payload = f'{salt_version}|{experiment_id}|{subject_pseudonym}'.encode('utf-8')
    return int(hashlib.sha256(payload).hexdigest(), 16) % 100


def assign_arm(experiment_id: str, subject_pseudonym: str, treatment_percent: int = 50,
               salt_version: str = ASSIGNMENT_SALT_VERSION, allow_draft_treatment: bool = False) -> Arm:
    """Assign control/treatment. The treatment arm requires an approved template."""
    if not 1 <= treatment_percent <= 99:
        raise ExperimentConfigError('treatment_percent must be between 1 and 99')
    if deterministic_bucket(experiment_id, subject_pseudonym, salt_version) >= treatment_percent:
        return 'control'
    pair = resolve_pair(experiment_id, CONTROL_TEMPLATE_ID, TREATMENT_TEMPLATE_ID)
    if not pair.treatment_available and not allow_draft_treatment:
        raise ExperimentConfigError(f'treatment arm unavailable: {pair.blocked_reason}')
    return 'treatment'


def assign(
    experiment_id: str,
    subject_pseudonym: str,
    rule_version: str,
    threshold_version: str,
    treatment_percent: int = 50,
    salt_version: str = ASSIGNMENT_SALT_VERSION,
    allow_draft_treatment: bool = False,
    status: AssignmentStatus = 'active',
    assigned_at: datetime | str | None = None,
) -> ExperimentAssignmentV1:
    """Produce a full assignment record, recording why treatment was refused."""
    try:
        arm = assign_arm(experiment_id, subject_pseudonym, treatment_percent, salt_version, allow_draft_treatment)
        blocked = None
    except ExperimentConfigError as exc:
        arm, blocked = 'control', str(exc)
    return ExperimentAssignmentV1(
        experiment_id=experiment_id, subject_pseudonym=subject_pseudonym, arm=arm,
        rule_version=rule_version, threshold_version=threshold_version,
        control_template_id=CONTROL_TEMPLATE_ID, treatment_template_id=TREATMENT_TEMPLATE_ID,
        assigned_at=assigned_at or datetime.now(timezone.utc), status=status,
        treatment_blocked_reason=blocked,
    )


def template_id_for_assignment(assignment: ExperimentAssignmentV1, level: str) -> str:
    """Map an arm to a template for the given level without touching rules."""
    from src.templates import template_id_for  # local import keeps module import order simple

    locale = CONTROL_LOCALE if assignment.arm == 'control' else TREATMENT_LOCALE
    return template_id_for(locale, level)


def build_event(
    event_type: str,
    evaluation_id: str,
    rule_version: str,
    threshold_version: str,
    experiment_id: str | None = None,
    arm: Arm | None = None,
    template_id: str | None = None,
    locale: str | None = None,
    case_id: str | None = None,
    subject_pseudonym: str | None = None,
    outcome_code: str | None = None,
    metadata: dict | None = None,
    event_id: str | None = None,
    timestamp: datetime | None = None,
) -> ProductEventV1:
    """Build one closed event. Unknown event types raise instead of being logged."""
    if event_type not in EXPERIMENT_EVENT_TYPES:
        raise ExperimentConfigError(f'unknown experiment event type: {event_type}')
    from anti_drop_ml.event_log import new_event_id

    payload = {
        'event_id': event_id or new_event_id(),
        'event_type': event_type,
        'timestamp': (timestamp or datetime.now(timezone.utc)).isoformat(),
        'evaluation_id': evaluation_id,
        'case_id': case_id,
        'experiment_id': experiment_id,
        'experiment_arm': arm,
        'template_id': template_id,
        'locale': locale,
        'language': _legacy_language_code(locale),
        'rule_version': rule_version,
        'threshold_version': threshold_version,
        'subject_pseudonym': subject_pseudonym,
        'outcome_code': outcome_code,
        'metadata': metadata or {},
    }
    return ProductEventV1.model_validate({key: value for key, value in payload.items() if value is not None})


def _legacy_language_code(locale: str | None) -> str | None:
    """P0 events carry a two-letter code; P1 adds locale. Keep both consistent."""
    if not locale:
        return None
    code = locale.split('-')[0].lower()
    return code if code in {'ru', 'uz', 'tg', 'ky', 'en', 'zh', 'ar'} else None


# --------------------------------------------------------------------------
# Blinded usability scoring
# --------------------------------------------------------------------------

BLINDING_MAP_VERSION = 'blinding-map-v1'


class BlindedScoringRecordV1(ClosedModel):
    """One participant's blinded response. Comments must not contain PII."""

    schema_version: Literal['BlindedScoringV1'] = 'BlindedScoringV1'
    participant_pseudonym: Ref
    scenario_id: str = Field(pattern=r'^[a-z0-9_-]{2,40}$')
    presentation_order: StrictInt = Field(ge=1, le=999, strict=True)
    # Blinded id: does not reveal arm or template until the map is applied.
    display_template_id: str = Field(pattern=r'^blin_[a-f0-9]{8,32}$')
    risk_level: Literal['RED', 'YELLOW', 'GREEN']
    action_choice: UnderstandingActions
    time_to_action_ms: StrictInt = Field(ge=0, le=3_600_000, strict=True)
    confidence: StrictInt = Field(ge=1, le=5, strict=True)
    felt_accused: StrictBool
    understood_next_step: StrictBool
    comments_no_pii: str = Field(default='', max_length=280)
    collected_at: datetime

    _time = field_validator('collected_at', mode='before')(aware_utc)

    @field_validator('comments_no_pii')
    @classmethod
    def _no_contact_details(cls, value: str) -> str:
        # Cheap, honest guard against phone/card-shaped digit runs, including the
        # "позвоните +7 999 000 00 00" formatting that token-level checks miss.
        digits = re.sub(r'\D', '', value)
        if len(digits) >= 9:
            raise ValueError('comments_no_pii must not contain long digit runs that look like phone/card data')
        return value


@dataclass(frozen=True)
class BlindingEntry:
    display_template_id: str
    template_id: str
    arm: Arm
    locale: str


def build_blinding_map(templates: Iterable[tuple[str, str, Arm, str]], salt_version: str = ASSIGNMENT_SALT_VERSION) -> dict:
    """Create a blinded id per template. Deterministic so reruns are stable."""
    mapping = {}
    for template_id, locale, arm, scenario in templates:
        digest = hashlib.sha256(f'{salt_version}|{scenario}|{template_id}'.encode()).hexdigest()[:16]
        mapping[f'blin_{digest}'] = {
            'display_template_id': f'blin_{digest}',
            'template_id': template_id,
            'arm': arm,
            'locale': locale,
            'scenario_id': scenario,
        }
    return mapping


def blind_record(record: dict, mapping: dict) -> dict:
    """Attach a blinded display id and strip everything that reveals the arm."""
    template_id = record['template_id']
    entry = next((value for value in mapping.values() if value['template_id'] == template_id), None)
    if entry is None:
        raise ExperimentConfigError(f'no blinding entry for template {template_id}')
    return {
        'participant_pseudonym': record['participant_pseudonym'],
        'scenario_id': record['scenario_id'],
        'presentation_order': record['presentation_order'],
        'display_template_id': entry['display_template_id'],
        'risk_level': record['risk_level'],
        'action_choice': record['action_choice'],
        'time_to_action_ms': record['time_to_action_ms'],
        'confidence': record['confidence'],
        'felt_accused': record['felt_accused'],
        'understood_next_step': record['understood_next_step'],
        'comments_no_pii': record.get('comments_no_pii', ''),
        'collected_at': record['collected_at'],
    }


def unblind(records: list[dict], mapping: dict | list[dict]) -> list[dict]:
    """Post-collection step: attach arm/template. Never called during collection.

    Accepts the map either as a dict keyed by display id or as the list of
    entries written to blinding_map.json.
    """
    index = mapping if isinstance(mapping, dict) else {row['display_template_id']: row for row in mapping}
    rows = []
    for record in records:
        entry = index.get(record['display_template_id'])
        if entry is None:
            raise ExperimentConfigError(f'unknown blinded id {record["display_template_id"]}')
        rows.append({**record, 'arm': entry['arm'], 'template_id': entry['template_id'], 'locale': entry['locale']})
    return rows


def _rate(flags: list[bool]) -> dict:
    successes = sum(1 for flag in flags if flag)
    n = len(flags)
    return {'value': successes / n if n else None, 'numerator': successes, 'denominator': n,
            'wilson_95_ci': wilson_interval(successes, n)}


def analyze_arm(rows: list[dict]) -> dict:
    """Descriptive per-arm estimates. Exploratory by construction."""
    if not rows:
        return {'n': 0, 'understanding_rate': _rate([]), 'safe_action_rate': _rate([]),
                'felt_accused_rate': _rate([]), 'translation_fallback_rate': _rate([]),
                'time_to_action_ms': {'median': None, 'p90': None, 'n': 0}}
    times = sorted(int(row['time_to_action_ms']) for row in rows)
    p90 = times[min(len(times) - 1, int(round(0.9 * (len(times) - 1))))]
    return {
        'n': len(rows),
        'understanding_rate': _rate([bool(row['understood_next_step']) for row in rows]),
        'safe_action_rate': _rate([row['action_choice'] in ('safe_action_chosen', 'accepted_advisory') for row in rows]),
        'felt_accused_rate': _rate([bool(row['felt_accused']) for row in rows]),
        'translation_fallback_rate': _rate([row.get('translation_fallback', False) is True for row in rows]),
        'time_to_action_ms': {'median': median(times), 'p90': p90, 'n': len(times)},
    }


def analyze_experiment(rows: list[dict], declared_powered_n: int = 0, primary_metric: str = 'safe_action_rate') -> dict:
    """Arm comparison with intervals plus a blunt claim guard."""
    warnings = [
        'Exploratory sample: usability A/B with synthetic participants does not prove uplift.',
        'No causal claim without randomisation integrity and intention-to-treat analysis.',
        'Wilson intervals assume independent participants; repeated sessions per participant break that.',
    ]
    if declared_powered_n and min(
        len([r for r in rows if r.get('arm') == arm]) for arm in ('control', 'treatment')
    ) < declared_powered_n:
        warnings.append(f'NOT POWERED: declared required n per arm is {declared_powered_n}.')
    elif not declared_powered_n:
        warnings.append('NOT POWERED: no power analysis declared; required_n was never computed for this sample.')

    by_arm = {arm: analyze_arm([row for row in rows if row.get('arm') == arm]) for arm in ('control', 'treatment')}
    difference = _difference(by_arm['control'], by_arm['treatment'], primary_metric)
    return {
        'schema_version': 'ExperimentAnalysisV1',
        'primary_metric': primary_metric,
        'declared_powered_n_per_arm': declared_powered_n,
        'arms': by_arm,
        'arm_difference': difference,
        'claim_permitted': False,
        'claim_text': 'No uplift claim. Observed difference is exploratory and unpowered.',
        'warnings': warnings,
    }


def _difference(control: dict, treatment: dict, metric: str) -> dict:
    left = control.get(metric, {}).get('value')
    right = treatment.get(metric, {}).get('value')
    if left is None or right is None:
        return {'metric': metric, 'control': left, 'treatment': right, 'difference_pp': None, 'interpretation': 'undefined (empty arm)'}
    return {'metric': metric, 'control': left, 'treatment': right, 'difference_pp': (right - left) * 100,
            'interpretation': 'exploratory only; not a powered or ITT-corrected estimate'}


def power_plan(baseline_safe_action_rate: float, expected_uplift_pp: float, alpha: float = 0.05,
               power: float = 0.80, dropout_rate: float = 0.10) -> dict:
    """Required sample size per arm, plus the caveats that make it non-final."""
    per_arm = required_n_two_proportions(baseline_safe_action_rate, expected_uplift_pp, alpha, power, dropout_rate)
    return {
        'schema_version': 'PowerPlanV1',
        'baseline_safe_action_rate': baseline_safe_action_rate,
        'expected_uplift_pp': expected_uplift_pp,
        'alpha': alpha,
        'power': power,
        'dropout_rate': dropout_rate,
        'required_n_per_arm': per_arm,
        'required_n_total': per_arm * 2,
        'assumptions': [
            'baseline and expected rates are ASSUMPTIONS, not measured in this repository',
            'independent individuals, equal allocation, single session per participant',
            'no clustering, no event-rate multiplicity, no interim looks',
            'must be recomputed on pilot baseline data before the pilot starts',
        ],
        'status': 'PLANNING_ONLY_NOT_A_PILOT_SAMPLE_SIZE',
    }


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with Path(path).open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def write_json(path: Path, payload: object) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


BLINDED_COLUMNS = [
    'participant_pseudonym', 'scenario_id', 'presentation_order', 'display_template_id', 'risk_level',
    'action_choice', 'time_to_action_ms', 'confidence', 'felt_accused', 'understood_next_step', 'comments_no_pii',
    'collected_at',
]
UNBLINDED_COLUMNS = BLINDED_COLUMNS + ['arm', 'template_id', 'locale']