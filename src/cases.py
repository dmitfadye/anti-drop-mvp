"""Sandbox case store: one module, two views.

P0 kept a legacy in-memory dict for the demo "обращение" button. P1 adds the
operator sandbox cases next to it in the same module, so the project still has
exactly one case store and no second database.

Nothing here is a banking action. A case is a local, synthetic record that an
operator screen can walk through; no ticket is created, no client is contacted,
no transfer is touched. Optional JSONL persistence exists only so a demo can be
restarted; there is no concurrency model and no audit guarantee.
"""
from __future__ import annotations

import hashlib
import re
import threading
from datetime import datetime

from src.policy import UTC

_LOCK = threading.RLock()

NOTE = "Учебный кейс (демо): поддержка не вызывается, операции не ограничиваются."
OPERATOR_SANDBOX_NOTE = "Локальная песочница. Синтетические данные. Не банковская система поддержки."

# P0 demo cases (legacy, unchanged public behaviour)
_STORE: dict[str, dict] = {}

# P1 operator sandbox cases
OPERATOR_STATUSES = (
    'created', 'viewed', 'help_started', 'case_confirmed', 'safe_action_confirmed',
    'closed_demo', 'failed', 'unknown',
)
TERMINAL_STATUSES = frozenset({'closed_demo'})

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    'created': frozenset({'viewed', 'help_started', 'failed', 'unknown', 'closed_demo'}),
    'viewed': frozenset({'help_started', 'case_confirmed', 'failed', 'unknown', 'closed_demo'}),
    'help_started': frozenset({'case_confirmed', 'safe_action_confirmed', 'failed', 'unknown', 'closed_demo'}),
    'case_confirmed': frozenset({'safe_action_confirmed', 'failed', 'unknown', 'closed_demo'}),
    'safe_action_confirmed': frozenset({'closed_demo', 'failed', 'unknown'}),
    'closed_demo': frozenset(),
    'failed': frozenset({'closed_demo', 'unknown'}),
    'unknown': frozenset({'viewed', 'help_started', 'case_confirmed', 'closed_demo', 'failed'}),
}

# Free-text operator notes are not accepted at all: a note_code from this
# allowlist is the only way to annotate a transition.
ALLOWED_NOTE_CODES = frozenset({
    'sandbox_confirmation', 'help_path_explained', 'translation_fallback_seen', 'client_will_hold_transfer',
    'client_asked_official_channel', 'client_unreachable', 'duplicate_report', 'simulator_test', 'demo_no_response',
})
ALLOWED_ACTOR_ROLES = frozenset({'demo_operator', 'demo_observer', 'demo_reviewer'})

ALLOWED_SCENARIO_CODES = frozenset({
    'demo_normal', 'demo_attack', 'demo_edge', 'demo_missing_data', 'demo_family_collection',
    'demo_salary_cash', 'demo_night_worker', 'demo_regular_payments', 'demo_manual',
})

_REF_RE = re.compile(r'^(sub|cp|dev|evt|src|ep|case|tpl)_[a-f0-9]{8,64}$')


class CaseNotFound(LookupError):
    """Unknown case id."""


class IllegalTransition(ValueError):
    """Requested status change is not in the state machine; HTTP 409."""


class IdempotencyConflict(ValueError):
    """Same Idempotency-Key reused with a different payload; HTTP 409."""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec='seconds').replace('+00:00', 'Z')


def _is_ref(value: object) -> bool:
    return isinstance(value, str) and bool(_REF_RE.match(value))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def create_case(summary: str, lang: str, score: int, idempotency_key: str | None) -> dict:
    """P0 legacy demo case. Stable case_id plus idempotency (unchanged contract)."""
    key = (idempotency_key or f"{summary}|{lang}|{score}").strip() or "empty"
    case_id = "CASE-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:8].upper()
    with _LOCK:
        existed = case_id in _STORE
        if not existed:
            _STORE[case_id] = {
                "case_id": case_id,
                "status": "open-sandbox",
                "demo": True,
                "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "summary": summary[:500],
                "lang": lang,
                "score": score,
                "note": NOTE,
            }
    return {**_STORE[case_id], "deduped": existed}


def get_case(case_id: str) -> dict | None:
    return _STORE.get(case_id.upper())


# --------------------------------------------------------------------------
# P1 operator sandbox cases
# --------------------------------------------------------------------------

_OPERATOR_CASES: dict[str, dict] = {}
_OPERATOR_IDEMPOTENCY: dict[str, dict] = {}
_OPERATOR_EVENTS: list[dict] = []


def operator_case_id(subject_pseudonym: str, scenario_code: str, idempotency_key: str) -> str:
    digest = hashlib.sha256(f'{subject_pseudonym}|{scenario_code}|{idempotency_key}'.encode()).hexdigest()
    return f'case_{digest[:16]}'


def create_operator_case(
    *,
    subject_pseudonym: str,
    scenario_code: str,
    level: str,
    score: int,
    locale: str,
    template_id: str,
    evaluation_id: str,
    rule_version: str,
    threshold_version: str,
    experiment_id: str | None = None,
    experiment_arm: str | None = None,
    episode_class: str = 'unknown',
    reason_codes: list[str] | None = None,
    idempotency_key: str | None = None,
    locale_status: str = 'draft',
    translation_fallback: bool = False,
) -> dict:
    """Create one sandbox case. Idempotent per (subject, scenario, key)."""
    _require(_is_ref(subject_pseudonym), 'subject_pseudonym must be an opaque pseudonymous ref')
    _require(scenario_code in ALLOWED_SCENARIO_CODES, 'scenario_code must come from the allowlist')
    _require(level in ('RED', 'YELLOW', 'GREEN'), 'level must be RED, YELLOW or GREEN')
    _require(isinstance(score, int) and not isinstance(score, bool) and 0 <= score <= 100, 'score must be an integer 0..100')
    _require(bool(idempotency_key), 'Idempotency-Key is required for operator case creation')
    key = f'create|{subject_pseudonym}|{scenario_code}|{idempotency_key}'
    with _LOCK:
        if key in _OPERATOR_IDEMPOTENCY:
            return {**_OPERATOR_IDEMPOTENCY[key]['response'], 'idempotent_replay': True}
        case_id = operator_case_id(subject_pseudonym, scenario_code, idempotency_key)
        case = {
            'case_id': case_id,
            'schema_version': 'OperatorCaseSummaryV1',
            'status': 'created',
            'created_at': _now(),
            'updated_at': _now(),
            'subject_pseudonym': subject_pseudonym,
            'scenario_code': scenario_code,
            'episode_class': episode_class,
            'level': level,
            'score': score,
            'score_is_not_probability': True,
            'locale': locale,
            'locale_status': locale_status,
            'template_id': template_id,
            'evaluation_id': evaluation_id,
            'rule_version': rule_version,
            'threshold_version': threshold_version,
            'experiment_id': experiment_id,
            'experiment_arm': experiment_arm,
            'reason_codes': sorted(reason_codes or []),
            'translation_fallback': translation_fallback,
            'sandbox_notice': OPERATOR_SANDBOX_NOTE,
            'events': [{'status': 'created', 'at': _now(), 'actor_role': 'demo_operator', 'note_code': None}],
        }
        _OPERATOR_CASES[case_id] = case
        response = {k: v for k, v in case.items() if k != 'events'}
        _OPERATOR_IDEMPOTENCY[key] = {'fingerprint': 'create', 'response': response}
        return {**response, 'idempotent_replay': False}


def get_operator_case(case_id: str) -> dict:
    with _LOCK:
        case = _OPERATOR_CASES.get(case_id)
    if case is None:
        raise CaseNotFound('case not found in the local sandbox store')
    return dict(case)


def list_operator_cases(
    *,
    level: str | None = None,
    status: str | None = None,
    locale: str | None = None,
    experiment_arm: str | None = None,
    episode_class: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
) -> list[dict]:
    with _LOCK:
        rows = [dict(case) for case in _OPERATOR_CASES.values()]
    def keep(case: dict) -> bool:
        if level and case['level'] != level:
            return False
        if status and case['status'] != status:
            return False
        if locale and case['locale'] != locale:
            return False
        if experiment_arm and (case['experiment_arm'] or 'none') != experiment_arm:
            return False
        if episode_class and case['episode_class'] != episode_class:
            return False
        if created_from and case['created_at'] < created_from:
            return False
        if created_to and case['created_at'] > created_to:
            return False
        return True
    return sorted((case for case in rows if keep(case)), key=lambda case: (case['created_at'], case['case_id']), reverse=True)


def update_operator_status(
    case_id: str,
    status: str,
    *,
    actor_role: str,
    note_code: str | None = None,
    idempotency_key: str | None = None,
) -> tuple[dict, bool]:
    """Apply one state transition. Returns (case_summary, idempotent_replay)."""
    _require(status in OPERATOR_STATUSES, 'status must come from the operator status allowlist')
    _require(actor_role in ALLOWED_ACTOR_ROLES, 'actor_role must come from the allowlist')
    _require(note_code is None or note_code in ALLOWED_NOTE_CODES, 'note_code must come from the allowlist; free text is refused')
    _require(bool(idempotency_key), 'Idempotency-Key is required for status updates')
    key = f'status|{case_id}|{idempotency_key}'
    fingerprint = f'{status}|{actor_role}|{note_code or ""}'
    with _LOCK:
        case = _OPERATOR_CASES.get(case_id)
        if case is None:
            raise CaseNotFound('case not found in the local sandbox store')
        previous = _OPERATOR_IDEMPOTENCY.get(key)
        if previous is not None:
            if previous['fingerprint'] != fingerprint:
                raise IdempotencyConflict('Idempotency-Key reused with a different payload')
            return dict(previous['response']), True
        if status == case['status']:
            # Same-state replay without a matching key: a no-op, not an error,
            # but reported so the caller can see nothing changed.
            response = _summary(case)
            _OPERATOR_IDEMPOTENCY[key] = {'fingerprint': fingerprint, 'response': response}
            return response, True
        if status not in ALLOWED_TRANSITIONS[case['status']]:
            raise IllegalTransition(f'{case["status"]} -> {status} is not an allowed operator transition')
        case['status'] = status
        case['updated_at'] = _now()
        case['events'] = [*case['events'], {'status': status, 'at': case['updated_at'], 'actor_role': actor_role, 'note_code': note_code}]
        response = _summary(case)
        _OPERATOR_IDEMPOTENCY[key] = {'fingerprint': fingerprint, 'response': response}
        return response, False


def _summary(case: dict) -> dict:
    return {key: value for key, value in case.items() if key != 'events'}


def operator_events() -> list[dict]:
    with _LOCK:
        return list(_OPERATOR_EVENTS)


def record_operator_action(action: dict) -> None:
    """Append-only in-process trace, mirrored to JSONL when a path is configured."""
    with _LOCK:
        _OPERATOR_EVENTS.append(action)


def reset_operator_store() -> None:
    """Test/demonstration helper: clears the sandbox store."""
    with _LOCK:
        _OPERATOR_CASES.clear()
        _OPERATOR_IDEMPOTENCY.clear()
        _OPERATOR_EVENTS.clear()