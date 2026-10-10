"""Operator sandbox API: a local observation screen, not a bank back office.

Guard rails, in order:
1. route is off unless ANTI_DROP_DEMO_MODE and ANTI_DROP_OPERATOR_UI_ENABLED are
   both true;
2. the client address must be loopback when it can be determined вЂ” behind a
   reverse proxy this degrades to "unknown" and the limitation is stated out
   loud rather than assumed safe;
3. there is no authentication. That is acceptable for a local demo on loopback
   and unacceptable for real data, which is why the banner and the export
   redaction both say so explicitly.

Exports are pseudonymous by construction: cases only ever hold opaque refs,
reason codes and allowlisted note codes. `redact_row` is the last line of
defence and is unit-tested against raw-PII-shaped values.
"""
from __future__ import annotations

import csv
import io
import ipaddress
import re
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from anti_drop_ml.event_log import read_events
from src.cases import (
    ALLOWED_ACTOR_ROLES,
    ALLOWED_NOTE_CODES,
    ALLOWED_SCENARIO_CODES,
    OPERATOR_SANDBOX_NOTE,
    OPERATOR_STATUSES,
    CaseNotFound,
    IdempotencyConflict,
    IllegalTransition,
    create_operator_case,
    get_operator_case,
    list_operator_cases,
    operator_events,
    record_operator_action,
    update_operator_status,
)
from src.flags import SANDBOX_BANNER, SANDBOX_BANNER_EN, current_flags

router = APIRouter(prefix="/api/operator", tags=["operator-sandbox"])

LOOPBACK_HOSTNAMES = frozenset({'localhost', 'localhost.localdomain', ''})

# Every column an export may contain. Anything else is dropped by redact_row.
EXPORT_COLUMNS = (
    'case_id', 'created_at', 'updated_at', 'status', 'level', 'score', 'score_is_not_probability',
    'locale', 'locale_status', 'template_id', 'experiment_id', 'experiment_arm', 'episode_class',
    'scenario_code', 'subject_pseudonym', 'evaluation_id', 'rule_version', 'threshold_version',
    'reason_codes', 'translation_fallback', 'event_count', 'sandbox_notice',
)

PII_SHAPED = ('phone', 'passport', 'card_number', 'otp', 'full_name', 'name', 'email', 'address',
              'counterparty_name', 'location', 'biometrics', 'iban', 'snils', 'inn')

# Free-text-ish columns are the only ones where a stray phone or card number
# could hide inside a string. Masking digits everywhere would destroy legitimate
# structured values (timestamps, version numbers, hash refs), so the mask is
# applied deliberately, not blanket.
DIGIT_MASKED_COLUMNS = frozenset({'reason_codes', 'scenario_code'})

_PII_TOKEN_RE = re.compile(r'(\+?\d[\d\- ()]{7,}\d)')


class OperatorCaseCreateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    subject_pseudonym: str = Field(pattern=r'^sub_[a-f0-9]{8,64}$')
    scenario_code: str
    level: Literal['RED', 'YELLOW', 'GREEN']
    score: int = Field(ge=0, le=100, strict=True)
    locale: str = Field(default='ru-RU', pattern=r'^[a-z]{2,3}(-[A-Za-z0-9]{2,8})?$')
    locale_status: Literal['draft', 'native_reviewed', 'legal_reviewed', 'approved', 'deprecated'] = 'draft'
    template_id: str = Field(pattern=r'^[a-z0-9_]{3,64}$')
    evaluation_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    rule_version: str = Field(pattern=r'^[a-zA-Z0-9._-]{1,80}$')
    threshold_version: str = Field(pattern=r'^[a-zA-Z0-9._-]{1,80}$')
    experiment_id: str | None = Field(default=None, pattern=r'^exp-[a-z0-9.-]{1,60}$')
    experiment_arm: Literal['control', 'treatment'] | None = None
    episode_class: Literal['normal', 'risk', 'legitimate_negative', 'edge', 'unknown'] = 'unknown'
    reason_codes: list[str] = Field(default_factory=list, max_length=16)
    translation_fallback: bool = False


class OperatorStatusRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    status: str
    actor_role: str = 'demo_operator'
    note_code: str | None = None


def _is_loopback(request: Request) -> tuple[bool, str]:
    host = request.client.host if request.client else ''
    if host.lower() in LOOPBACK_HOSTNAMES:
        return True, 'loopback'
    try:
        return ipaddress.ip_address(host).is_loopback, host
    except ValueError:
        return False, 'unresolved'


def require_operator_enabled(request: Request) -> dict:
    """503 when the surface is off; 403 when the caller is not local."""
    flags = current_flags()
    if not flags.demo_mode:
        raise HTTPException(status_code=503, detail='operator sandbox requires ANTI_DROP_DEMO_MODE=true')
    if not flags.operator_ui_enabled:
        raise HTTPException(status_code=503, detail='operator sandbox is disabled; set ANTI_DROP_OPERATOR_UI_ENABLED=true')
    local, host = _is_loopback(request)
    if not local:
        raise HTTPException(status_code=403, detail='operator sandbox accepts loopback clients only (local demo, no auth)')
    return {'demo_mode': flags.demo_mode, 'operator_ui_enabled': flags.operator_ui_enabled, 'client_host': host}


def redact_row(row: dict) -> dict:
    """Allowlist columns, drop PII-shaped keys, mask digit runs in free text."""
    clean: dict[str, Any] = {}
    for column in EXPORT_COLUMNS:
        if column not in row:
            continue
        value = row[column]
        if isinstance(value, (list, tuple)):
            value = ','.join(str(item) for item in value)
        text = '' if value is None else str(value)
        if any(token in column.lower() for token in PII_SHAPED):
            text = '[REDACTED]'
        elif column in DIGIT_MASKED_COLUMNS:
            text = _PII_TOKEN_RE.sub('[REDACTED]', text)
        clean[column] = text
    clean.setdefault('sandbox_notice', OPERATOR_SANDBOX_NOTE)
    return clean


@router.get('/cases', summary='Sandbox case list with filters')
def operator_cases(
    request: Request,
    level: Annotated[Literal['RED', 'YELLOW', 'GREEN'] | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    locale: Annotated[str | None, Query()] = None,
    experiment_arm: Annotated[Literal['control', 'treatment'] | None, Query()] = None,
    episode_class: Annotated[Literal['normal', 'risk', 'legitimate_negative', 'edge', 'unknown'] | None, Query()] = None,
    created_from: Annotated[str | None, Query(description='ISO-8601 UTC lower bound')] = None,
    created_to: Annotated[str | None, Query()] = None,
) -> dict:
    require_operator_enabled(request)
    if status is not None and status not in OPERATOR_STATUSES:
        raise HTTPException(status_code=422, detail='status filter must come from the operator status allowlist')
    try:
        rows = list_operator_cases(level=level, status=status, locale=locale, experiment_arm=experiment_arm,
                                   episode_class=episode_class, created_from=created_from, created_to=created_to)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return {
        'schema_version': 'OperatorCaseListV1',
        'sandbox_notice': OPERATOR_SANDBOX_NOTE,
        'security_note': 'local demo only, no authentication, no real personal data, no banking action',
        'filters': {'level': level, 'status': status, 'locale': locale, 'experiment_arm': experiment_arm,
                    'episode_class': episode_class, 'created_from': created_from, 'created_to': created_to},
        'count': len(rows),
        'cases': [redact_row(row) for row in rows],
    }


@router.post('/cases', status_code=201, summary='Create one sandbox case (idempotent)')
def operator_case_create(
    payload: OperatorCaseCreateRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias='Idempotency-Key')] = None,
) -> dict:
    require_operator_enabled(request)
    if payload.scenario_code not in ALLOWED_SCENARIO_CODES:
        raise HTTPException(status_code=422, detail='scenario_code must come from the allowlist')
    if not idempotency_key:
        raise HTTPException(status_code=400, detail='Idempotency-Key header is required')
    try:
        case = create_operator_case(**payload.model_dump(), idempotency_key=idempotency_key)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    record_operator_action({'at': case['created_at'], 'action': 'case_created', 'case_id': case['case_id'],
                            'actor_role': 'demo_operator', 'note_code': None,
                            'client_host': request.client.host if request.client else ''})
    return {**redact_row(case), 'sandbox_notice': OPERATOR_SANDBOX_NOTE, 'idempotent_replay': case['idempotent_replay']}


@router.get('/cases/{case_id}', summary='Sandbox case detail with event timeline')
def operator_case_detail(case_id: str, request: Request) -> dict:
    require_operator_enabled(request)
    try:
        case = get_operator_case(case_id)
    except CaseNotFound:
        raise HTTPException(status_code=404, detail='case not found in the local sandbox store') from None
    return {**redact_row(case), 'timeline': case['events'], 'sandbox_notice': OPERATOR_SANDBOX_NOTE,
            'status_machine': {key: sorted(value) for key, value in _transitions().items()}}


def _transitions() -> dict[str, frozenset[str]]:
    from src.cases import ALLOWED_TRANSITIONS

    return ALLOWED_TRANSITIONS


@router.post('/cases/{case_id}/status', summary='Operator status transition (idempotent)')
def operator_case_status(
    case_id: str,
    payload: OperatorStatusRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias='Idempotency-Key')] = None,
) -> dict:
    require_operator_enabled(request)
    if payload.status not in OPERATOR_STATUSES:
        raise HTTPException(status_code=422, detail='status must come from the operator status allowlist')
    if payload.actor_role not in ALLOWED_ACTOR_ROLES:
        raise HTTPException(status_code=422, detail='actor_role must come from the allowlist')
    if payload.note_code is not None and payload.note_code not in ALLOWED_NOTE_CODES:
        raise HTTPException(status_code=422, detail='note_code must come from the allowlist; free text is refused')
    if not idempotency_key:
        raise HTTPException(status_code=400, detail='Idempotency-Key header is required')
    try:
        case, replay = update_operator_status(case_id, payload.status, actor_role=payload.actor_role,
                                              note_code=payload.note_code, idempotency_key=idempotency_key)
    except CaseNotFound:
        raise HTTPException(status_code=404, detail='case not found in the local sandbox store') from None
    except IdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    record_operator_action({'at': case['updated_at'], 'action': 'status_changed', 'case_id': case_id,
                            'to_status': payload.status, 'actor_role': payload.actor_role,
                            'note_code': payload.note_code, 'idempotent_replay': replay,
                            'client_host': request.client.host if request.client else ''})
    return {
        'case_id': case_id,
        'status': case['status'],
        'updated_at': case['updated_at'],
        'idempotent_replay': replay,
        'note_code': payload.note_code,
        'sandbox_notice': OPERATOR_SANDBOX_NOTE,
    }


@router.get('/metrics', summary='Operator metrics (synthetic counts only)')
def operator_metrics(request: Request) -> dict:
    require_operator_enabled(request)
    rows = list_operator_cases()
    alerts = [row for row in rows if row['level'] in ('RED', 'YELLOW')]
    negatives = [row for row in rows if row['episode_class'] == 'legitimate_negative']
    negative_alerts = [row for row in negatives if row['level'] in ('RED', 'YELLOW')]
    flags = current_flags()
    events = read_events(flags.operator_log_path) if flags.operator_log_path else []
    rejections = sum(1 for event in events if event.get('event_type') == 'request_failed')
    return {
        'schema_version': 'OperatorMetricsV1',
        'sandbox_notice': OPERATOR_SANDBOX_NOTE,
        'banner_ru': SANDBOX_BANNER,
        'banner_en': SANDBOX_BANNER_EN,
        'total_cases': len(rows),
        'cases_by_level': _count_by(rows, 'level'),
        'cases_by_status': _count_by(rows, 'status'),
        'cases_by_locale': _count_by(rows, 'locale'),
        'cases_by_arm': {**{'control': 0, 'treatment': 0, 'none': 0}, **_count_by(rows, 'experiment_arm')},
        'cases_by_episode_class': _count_by(rows, 'episode_class'),
        'alert_rate': _ratio(len(alerts), len(rows)),
        'legitimate_negative_alert_rate': _ratio(len(negative_alerts), len(negatives)) if negatives else None,
        'legitimate_negative_cases': len(negatives),
        'translation_fallback_count': sum(1 for row in rows if row['translation_fallback']),
        'experiment_assignment_count': sum(1 for row in rows if row['experiment_id']),
        'errors_and_rejections': rejections,
        'operator_actions_logged': len(operator_events()),
        'statuses': list(OPERATOR_STATUSES),
        'allowlisted_note_codes': sorted(ALLOWED_NOTE_CODES),
        'allowlisted_actor_roles': sorted(ALLOWED_ACTOR_ROLES),
        'limitations': [
            'Counts describe a local synthetic sandbox, not production volumes.',
            'No authentication: loopback-only is a demo guard, not production security.',
            'Rate denominators are undefined (null) when no cases of that kind exist; they are never shown as zero.',
        ],
    }


def _count_by(rows: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = row.get(key) or 'none'
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _ratio(numerator: int, denominator: int) -> dict:
    return {'value': numerator / denominator if denominator else None, 'numerator': numerator, 'denominator': denominator}


@router.get('/export', summary='Pseudonymous export (json or csv)')
def operator_export(
    request: Request,
    format: Annotated[Literal['json', 'csv'], Query()] = 'json',
) -> Any:
    require_operator_enabled(request)
    flags = current_flags()
    if not flags.operator_export_enabled:
        raise HTTPException(status_code=503, detail='export is off by default; set ANTI_DROP_OPERATOR_EXPORT_ENABLED=true')
    rows = [redact_row(row) for row in list_operator_cases()]
    if format == 'csv':
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(EXPORT_COLUMNS), extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
        return PlainTextResponse(buffer.getvalue(), media_type='text/csv; charset=utf-8')
    return JSONResponse({
        'schema_version': 'OperatorExportV1',
        'sandbox_notice': OPERATOR_SANDBOX_NOTE,
        'security_note': 'pseudonymous export; no raw personal data, no banking action, append-only JSONL log',
        'columns': list(EXPORT_COLUMNS),
        'count': len(rows),
        'cases': rows,
        'redaction': {'dropped_columns_named_like': list(PII_SHAPED),
                      'digit_masked_columns': sorted(DIGIT_MASKED_COLUMNS),
                      'digit_runs': '[REDACTED]'},
    })


@router.get('/status-machine', summary='Allowed operator transitions and allowlists')
def operator_status_machine(request: Request) -> dict:
    require_operator_enabled(request)
    return {
        'schema_version': 'OperatorStatusMachineV1',
        'statuses': list(OPERATOR_STATUSES),
        'transitions': {key: sorted(value) for key, value in _transitions().items()},
        'allowlisted_note_codes': sorted(ALLOWED_NOTE_CODES),
        'allowlisted_actor_roles': sorted(ALLOWED_ACTOR_ROLES),
        'allowlisted_scenario_codes': sorted(ALLOWED_SCENARIO_CODES),
        'forbidden_notes': [
            'free text containing personal data', 'money returned', 'account frozen',
            'client accused', 'OTP verified', 'cashback granted',
        ],
        'sandbox_notice': OPERATOR_SANDBOX_NOTE,
    }