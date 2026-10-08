"""Communication layer: one decision, then a language. Never the other way round.

Order of operations is the whole point of this module:

1. `RiskSnapshotV1` is evaluated by the unchanged rules engine;
2. only then is a locale/arm/template chosen for presentation;
3. the render, the assignment and every emitted event carry the *same*
   `evaluation_id`, `rule_version` and `threshold_version` as the decision.

So the risk score cannot depend on the language, the experiment cannot change
rules, and an unapproved translation is visibly badged instead of quietly
served as approved. When the experiment flag is off, the control template is
used and the response says so.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import ValidationError

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from anti_drop_ml.adapter import RULE_VERSION, THRESHOLD_VERSION, evaluate_snapshot
from anti_drop_ml.contracts import ClosedModel, RiskSnapshotV1
from anti_drop_ml.event_log import append_event, new_event_id
from anti_drop_ml.events import ProductEventV1
from src.experiments import ExperimentConfigError, assign, build_event
from src.flags import current_flags
from src.localization import LocalizationPackError, registry
from src.templates import CONTROL_LOCALE, TemplateError, render_warning

router = APIRouter(prefix="/api/v1/communication", tags=["communication"])

LOCALES = {'ru-RU': 'ru', 'uz-UZ': 'uz', 'tg-TJ': 'tg', 'ky-KG': 'ky', 'en-US': 'en'}


class CommunicateRequest(ClosedModel):
    snapshot: RiskSnapshotV1
    preferred_locale: str = 'ru-RU'
    subject_pseudonym: str | None = None
    emit_events: bool = True


class EventLogResult(ClosedModel):
    schema_version: Literal['EventLogResultV1'] = 'EventLogResultV1'
    events: list[ProductEventV1]
    sink: Literal['disabled', 'local_jsonl']


def emit(payload: dict, enabled: bool = True) -> ProductEventV1 | None:
    """Append to the local JSON-lines sink; no-op when no path is configured."""
    if not enabled:
        return None
    return append_event(payload, current_flags().operator_log_path)


def event_sink_status() -> str:
    return 'local_jsonl' if current_flags().operator_log_path else 'disabled'


@router.get('/locales', summary='Available localization packs with honest review status')
def locales() -> dict:
    flags = current_flags()
    packs = registry()
    return {
        'schema_version': 'LocaleCatalogV1',
        'enabled': flags.localization_enabled,
        'control_locale': CONTROL_LOCALE,
        'target_locale': flags.target_locale,
        'locales': packs.describe(),
        'load_errors': packs.load_errors,
        'statement': ('Exactly one target locale pack exists. Every pack below draft/native_reviewed '
                      'status must be badged in the UI as unverified.'),
        'synthetic': True,
    }


@router.get('/templates', summary='Warning template variants and their approval state')
def templates() -> dict:
    from src.templates import TemplateRegistry

    registry_templates = TemplateRegistry().refresh()
    return {
        'schema_version': 'TemplateCatalogV1',
        'templates': registry_templates.describe(),
        'load_errors': registry_templates.load_errors,
        'language_does_not_change_score': True,
        'statement': ('Rendering never reads rules. Control and treatment differ only in locale and copy.'),
    }


@router.post('/evaluate', summary='Strict snapshot -> decision, arm and warning')
def communicate(payload: CommunicateRequest, request: Request) -> Any:
    flags = current_flags()
    if not flags.demo_mode:
        raise HTTPException(status_code=503, detail='communication layer requires ANTI_DROP_DEMO_MODE=true')
    localization = registry()
    if not localization.pack(payload.preferred_locale):
        known = ', '.join(localization.locales) or 'none'
        raise HTTPException(status_code=422, detail=f'unknown locale; available: {known}')
    if payload.subject_pseudonym is not None and not payload.subject_pseudonym.startswith('sub_'):
        raise HTTPException(status_code=422, detail='subject_pseudonym must be a sub_ pseudonymous ref')

    # 1. Decision first, with no locale anywhere near it.
    decision = evaluate_snapshot(payload.snapshot)
    events: list[dict] = []

    assignment_payload = None
    arm = 'control'
    if flags.experiment_enabled and payload.subject_pseudonym and decision.level in ('RED', 'YELLOW'):
        try:
            assignment = assign(
                experiment_id=flags.experiment_id,
                subject_pseudonym=payload.subject_pseudonym,
                rule_version=RULE_VERSION,
                threshold_version=THRESHOLD_VERSION,
                treatment_percent=flags.treatment_percent,
                allow_draft_treatment=flags.experiment_allow_draft_treatment,
            )
        except ExperimentConfigError as exc:
            assignment = assign(experiment_id=flags.experiment_id, subject_pseudonym=payload.subject_pseudonym,
                                rule_version=RULE_VERSION, threshold_version=THRESHOLD_VERSION,
                                treatment_percent=flags.treatment_percent)
            assignment = assignment.model_copy(update={'treatment_blocked_reason': str(exc)})
        arm = assignment.arm
        assignment_payload = assignment.model_dump(mode='json')
        events.append({'event_type': 'experiment_assigned', 'arm': arm, 'outcome_code': f'arm_{arm}'})
    elif flags.experiment_enabled and payload.subject_pseudonym:
        events.append({'event_type': 'experiment_assigned', 'arm': None, 'outcome_code': 'ok',
                       'metadata': {'assignment_method': 'deterministic_hash'}})

    warning_payload = None
    used_fallback = False
    if decision.level in ('RED', 'YELLOW'):
        locale = payload.preferred_locale
        if arm == 'treatment' and flags.experiment_enabled and flags.experiment_allow_draft_treatment:
            locale = flags.target_locale
        try:
            if locale == CONTROL_LOCALE or not flags.localization_enabled:
                template_id = 'warning_ru_control_v1' if decision.level == 'RED' else 'warning_ru_control_yellow_v1'
            else:
                from src.templates import template_id_for

                template_id = template_id_for(locale, decision.level)
            warning = render_warning(template_id, decision.level,
                                     values={'amount': '—', 'currency': 'RUB', 'reason_short': '—'},
                                     localization_registry=localization)
        except (TemplateError, LocalizationPackError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        warning_payload = warning.as_dict()
        used_fallback = bool(warning.used_fallback_keys)
        events.append({'event_type': 'template_rendered', 'outcome_code':
                       'rendered_draft_translation' if warning.template_status != 'approved' else 'ok'})
        events.append({'event_type': 'alert_delivered', 'outcome_code': 'ok'})
        if used_fallback:
            events.append({'event_type': 'translation_fallback', 'outcome_code': 'fallback_to_control_locale'})

    emitted: list[dict] = []
    for event in events:
        built = build_event(
            event_type=event['event_type'],
            evaluation_id=decision.evaluation_id,
            rule_version=decision.rule_version,
            threshold_version=decision.threshold_version,
            experiment_id=assignment_payload['experiment_id'] if assignment_payload else None,
            arm=event.get('arm'),
            template_id=(warning_payload or {}).get('template_id'),
            locale=(warning_payload or {}).get('locale') if warning_payload else payload.preferred_locale,
            subject_pseudonym=payload.subject_pseudonym,
            outcome_code=event.get('outcome_code'),
            metadata=event.get('metadata'),
            event_id=new_event_id(),
        )
        stored = emit(built.model_dump(mode='json'), payload.emit_events)
        if stored is not None:
            emitted.append(stored.model_dump(mode='json'))

    body = {
        'schema_version': 'CommunicationResponseV1',
        'decision': decision.model_dump(mode='json'),
        'warning': warning_payload,
        'language_note': {
            'requested_locale': payload.preferred_locale,
            'rendered_locale': (warning_payload or {}).get('locale'),
            'translation_fallback_used': used_fallback,
            'draft_badge': (warning_payload or {}).get('draft_badge'),
            'language_affects_score': False,
        },
        'experiment': {
            'enabled': flags.experiment_enabled,
            'experiment_id': flags.experiment_id,
            'treatment_percent': flags.treatment_percent if flags.experiment_enabled else 0,
            'assignment': assignment_payload,
            'control_template_id': 'warning_ru_control_v1',
            'treatment_template_id': f"warning_{flags.target_locale.split('-')[0]}_treatment_v1",
            'treatment_available': False,
            'blocked_reason': None,
        },
        'event_log': {'sink': event_sink_status(), 'event_count': len(emitted), 'events': emitted,
                      'note': 'events are synthetic and local; there is no analytics backend'},
        'sandbox': True,
        'not_a_banking_action': True,
    }
    try:
        from src.templates import resolve_pair

        pair = resolve_pair(flags.experiment_id, 'warning_ru_control_v1', f"warning_{flags.target_locale.split('-')[0]}_treatment_v1")
        body['experiment']['treatment_available'] = pair.treatment_available
        body['experiment']['blocked_reason'] = pair.blocked_reason
    except TemplateError as exc:
        body['experiment']['blocked_reason'] = str(exc)
    return JSONResponse(body)


@router.post('/preview', summary='Preview any warning template for an already-made level (always badged)')
def preview(level: Annotated[Literal['RED', 'YELLOW'], Query()], template_id: Annotated[str | None, Query()] = None) -> Any:
    """Compare control vs treatment copy without touching rules or the experiment.

    This is a preview for demonstration only: it does not assign an arm, does
    not log an experiment event and always returns the template status plus the
    mandatory draft badge.
    """
    from src.templates import TemplateRegistry, render_warning, template_id_for

    localization = registry()
    if template_id is None:
        target = current_flags().target_locale
        try:
            template_id = template_id_for(target, level)
        except TemplateError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
    try:
        warning = render_warning(template_id, level, values={'amount': '—', 'currency': 'RUB', 'reason_short': '—'},
                                 localization_registry=localization)
    except (TemplateError, LocalizationPackError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return {
        'schema_version': 'PreviewResponseV1',
        'preview': True,
        'warning': warning.as_dict(),
        'template_status_note': 'A template below approved must be shown with its draft badge. '
                                'It must never be presented as an approved translation.',
        'available_templates': TemplateRegistry().refresh().describe(),
        'language_does_not_change_score': True,
        'synthetic': True,
    }


@router.post('/events', status_code=202, summary='Append one synthetic client event to the local sink')
def record_event(payload: dict, request: Request,
                 idempotency_key: Annotated[str | None, Header(alias='Idempotency-Key')] = None) -> dict:
    flags = current_flags()
    if not flags.operator_log_path:
        raise HTTPException(status_code=503, detail='event sink is not configured; set ANTI_DROP_OPERATOR_LOG')
    candidate = {
        **payload,
        'event_id': payload.get('event_id') or new_event_id(),
        'timestamp': payload.get('timestamp') or datetime.now(timezone.utc).isoformat(),
    }
    try:
        event = ProductEventV1.model_validate(candidate)
    except ValidationError:
        # No raw payload echoed back: a rejected event is a closed-contract breach.
        raise HTTPException(status_code=422, detail='event rejected by the closed event contract') from None
    stored = append_event(event.model_dump(mode='json'), flags.operator_log_path)
    if stored is None:
        raise HTTPException(status_code=422, detail='event rejected by the closed event contract')
    return {'schema_version': 'EventAcceptedV1', 'event_id': stored.event_id, 'event_type': stored.event_type,
            'sink': 'local_jsonl', 'idempotency_key': idempotency_key, 'synthetic': True}