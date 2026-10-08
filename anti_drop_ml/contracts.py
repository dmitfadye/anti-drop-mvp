"""Strict, versioned boundaries. Opaque refs are caller-issued pseudonyms, not PII."""
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator, model_validator

Ref = Annotated[str, Field(pattern=r"^(sub|cp|dev|evt|src|ep|case|tpl)_[a-f0-9]{8,64}$")]
LabelSource = Literal['human_reviewed', 'synthetic_placeholder', 'bank_adjudicated', 'unknown']
EpisodeClass = Literal['normal', 'risk', 'legitimate_negative', 'edge', 'unknown']
ReasonCode = Literal['multiple_small_inbound', 'large_outbound_after_inbound', 'sim_changed_recently', 'device_novelty_with_baseline', 'rapid_in_out_pattern', 'borderline_window', 'insufficient_data', 'cashout_ratio', 'fanout_transfers', 'night_activity']


def aware_utc(value: object) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError('expected a valid timezone-aware ISO-8601 datetime') from None
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('timezone-aware ISO-8601 datetime required; naive dates are rejected')
    return value.astimezone(timezone.utc)


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra='forbid', validate_assignment=True)


class SnapshotMetadata(ClosedModel):
    dataset_version: str | None = Field(default=None, max_length=80, pattern=r'^[a-zA-Z0-9._-]+$')
    label_source: LabelSource = 'unknown'
    is_holdout: StrictBool = False
    episode_class: EpisodeClass = 'unknown'
    episode_id: Ref | None = None
    label: Literal['risk', 'normal'] | None = None


class RiskTransactionV1(ClosedModel):
    event_id: Ref
    source_event_id: Ref | None = None
    subject_ref: Ref | None = None
    occurred_at: datetime
    direction: Literal['in', 'out']
    type: Literal['transfer', 'cash_deposit', 'cash_withdrawal', 'salary', 'family_collection', 'other']
    amount_minor: Annotated[StrictInt, Field(ge=0, le=10**14)]
    currency: Literal['RUB']
    counterparty_ref: Ref | None = None
    device_id: Ref | None = None
    sim_changed_days_ago: Annotated[StrictInt, Field(ge=0)] | None = None

    _time = field_validator('occurred_at', mode='before')(aware_utc)

    @model_validator(mode='after')
    def transaction_rules(self):
        if self.type in ('transfer', 'family_collection') and self.amount_minor == 0:
            raise ValueError('transfers require amount_minor > 0')
        if self.type in ('salary', 'cash_deposit') and self.direction != 'in':
            raise ValueError('salary and cash_deposit must be inbound')
        if self.type == 'cash_withdrawal' and self.direction != 'out':
            raise ValueError('cash_withdrawal must be outbound')
        return self


class RiskSnapshotV1(ClosedModel):
    schema_version: Literal['RiskSnapshotV1']
    subject_ref: Ref
    analysis_at: datetime
    timezone_policy: Literal['normalize_to_utc']
    allow_future_events: StrictBool = False
    transactions: list[RiskTransactionV1] = Field(max_length=5000)
    metadata: SnapshotMetadata = Field(default_factory=SnapshotMetadata)

    _time = field_validator('analysis_at', mode='before')(aware_utc)

    @model_validator(mode='after')
    def snapshot_rules(self):
        for key in ('event_id', 'source_event_id'):
            values = [getattr(t, key) for t in self.transactions if getattr(t, key) is not None]
            if len(values) != len(set(values)):
                raise ValueError(f'duplicate {key}')
        if any(t.subject_ref is not None and t.subject_ref != self.subject_ref for t in self.transactions):
            raise ValueError('mixed subject_ref is forbidden')
        if not self.allow_future_events and any(t.occurred_at > self.analysis_at for t in self.transactions):
            raise ValueError('future events are forbidden')
        return self


class DataQuality(ClosedModel):
    has_missing_sim: bool
    has_missing_device: bool
    future_events_rejected: bool
    duplicate_events_rejected: bool
    future_events_excluded: int = 0


class WindowUsed(ClosedModel):
    short_minutes: int
    long_hours: int


class RiskDecisionV1(ClosedModel):
    schema_version: Literal['RiskDecisionV1'] = 'RiskDecisionV1'
    evaluation_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    subject_ref: Ref
    analysis_at: datetime
    rule_version: str
    threshold_version: str
    level: Literal['GREEN', 'YELLOW', 'RED']
    score: Annotated[StrictInt, Field(ge=0, le=100)]
    score_interpretation: Literal['deterministic_rule_score_not_probability'] = 'deterministic_rule_score_not_probability'
    reason_codes: list[ReasonCode]
    score_contributions: dict[ReasonCode, Annotated[StrictInt, Field(ge=0, le=100)]]
    window_used: WindowUsed
    data_quality: DataQuality
    status: Literal['ok', 'insufficient_data', 'rejected_input']

    _time = field_validator('analysis_at', mode='before')(aware_utc)
