"""A/B event contract only; no tracking, storage, assignment or bank actions."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from anti_drop_ml.contracts import ClosedModel, Ref, aware_utc
from src.alerts import TEMPLATE_VERSION


class EventMetadata(ClosedModel):
    # Closed allowlist avoids arbitrary nested metadata that could contain raw PII.
    synthetic: Literal[True] = True
    schema_version: Literal['ProductEventV1'] = 'ProductEventV1'
    template_version: Literal['warning-templates-2026.10.08.p1'] = TEMPLATE_VERSION
    latency_ms: int | None = Field(default=None, ge=0, le=3600000, strict=True)
    http_status: int | None = Field(default=None, ge=100, le=599, strict=True)


class ProductEventV1(ClosedModel):
    event_id: UUID
    event_type: Literal['risk_evaluated', 'alert_delivered', 'alert_viewed', 'language_selected', 'help_started', 'case_created', 'case_confirmed', 'safe_action_confirmed', 'request_failed', 'experiment_assigned']
    timestamp: datetime
    evaluation_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    case_id: Ref | None = None
    experiment_arm: Literal['control', 'treatment'] | None = None
    template_id: Ref | None = None
    language: Literal['ru', 'uz', 'tg', 'ky', 'en', 'zh', 'ar'] | None = None
    rule_version: str = Field(pattern=r'^[a-zA-Z0-9._-]{1,80}$')
    threshold_version: str = Field(pattern=r'^[a-zA-Z0-9._-]{1,80}$')
    subject_pseudonym: Ref | None = None
    outcome_code: Literal['ok', 'failed', 'cancelled', 'confirmed_sandbox', 'unknown'] | None = None
    metadata: EventMetadata = Field(default_factory=EventMetadata)

    _time = field_validator('timestamp', mode='before')(aware_utc)
