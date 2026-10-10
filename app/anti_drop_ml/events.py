"""P1 event contract: A/B instrumentation for the communication layer only.

P0 shipped the shape; P1 widens the closed allowlists for the language
experiment and the pre-transfer advisory. The design rule is unchanged:
closed models with fixed vocabularies, because an open `metadata` bag is how
raw PII reaches logs and exports. Anything not in the allowlist is rejected.
"""
from datetime import datetime
from typing import Literal, get_args
from uuid import UUID

from pydantic import Field, field_validator

from anti_drop_ml.contracts import ClosedModel, Ref, aware_utc
from src.alerts import TEMPLATE_VERSION

# Template identifiers are product slugs ("warning_uz_treatment_v1"), not opaque
# hashes, so they need their own vocabulary-safe pattern.
TemplateId = str

EventType = Literal[
    # P0 lifecycle
    'risk_evaluated',
    'alert_delivered',
    'alert_viewed',
    'language_selected',
    'help_started',
    'case_created',
    'case_confirmed',
    'safe_action_confirmed',
    'request_failed',
    'experiment_assigned',
    # P1 communication-layer instrumentation
    'template_rendered',
    'translation_fallback',
    'understanding_survey_submitted',
    'scoring_recorded',
    'pre_transfer_advised',
]

OutcomeCode = Literal[
    'ok',
    'failed',
    'cancelled',
    'confirmed_sandbox',
    'unknown',
    'arm_control',
    'arm_treatment',
    'rendered_draft_translation',
    'fallback_to_control_locale',
    'understood_next_step',
    'did_not_understand',
    'safe_action_chosen',
    'unsafe_action_chosen',
    'declined_advisory',
    'accepted_advisory',
    'rejected_input',
]

Arm = Literal['control', 'treatment']

# The vocabulary, exported so tests and reports can assert against it directly.
EVENT_TYPES: tuple[str, ...] = get_args(EventType)
OUTCOME_CODES: tuple[str, ...] = get_args(OutcomeCode)


class EventMetadata(ClosedModel):
    # Closed allowlist avoids arbitrary nested metadata that could contain raw PII.
    synthetic: Literal[True] = True
    schema_version: Literal['ProductEventV1'] = 'ProductEventV1'
    template_version: Literal['warning-templates-2026.10.08.p1'] = TEMPLATE_VERSION
    latency_ms: int | None = Field(default=None, ge=0, le=3600000, strict=True)
    http_status: int | None = Field(default=None, ge=100, le=599, strict=True)
    localization_version: str | None = Field(default=None, pattern=r'^[a-zA-Z0-9._-]{1,80}$')
    template_status: Literal['draft', 'native_reviewed', 'legal_reviewed', 'approved', 'deprecated'] | None = None
    assignment_method: Literal['deterministic_hash'] | None = None
    question_id: str | None = Field(default=None, pattern=r'^q[0-9]{1,2}$')
    score_value: int | None = Field(default=None, ge=0, le=100, strict=True)


class ProductEventV1(ClosedModel):
    event_id: UUID
    event_type: EventType
    timestamp: datetime
    evaluation_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    case_id: Ref | None = None
    experiment_id: str | None = Field(default=None, pattern=r'^exp-[a-z0-9.-]{1,60}$')
    experiment_arm: Arm | None = None
    template_id: str | None = Field(default=None, pattern=r'^[a-z0-9_]{3,64}$')
    language: Literal['ru', 'uz', 'tg', 'ky', 'en', 'zh', 'ar'] | None = None
    locale: str | None = Field(default=None, pattern=r'^[a-z]{2,3}(-[A-Za-z0-9]{2,8})?$')
    rule_version: str = Field(pattern=r'^[a-zA-Z0-9._-]{1,80}$')
    threshold_version: str = Field(pattern=r'^[a-zA-Z0-9._-]{1,80}$')
    subject_pseudonym: Ref | None = None
    outcome_code: OutcomeCode | None = None
    metadata: EventMetadata = Field(default_factory=EventMetadata)

    _time = field_validator('timestamp', mode='before')(aware_utc)