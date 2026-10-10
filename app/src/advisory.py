"""Pre-transfer advisory sandbox — advisory only, never a payment decision.

This is the optional P1 block and it is deliberately narrow:

- a separate contract (`PlannedTransferAdvisoryV1`) with `analysis_mode`
  pinned to `pre_transfer_advisory`, so a planned event can never be smuggled
  into the ordinary completed-transaction path;
- the decision it returns carries `status = advisory_only`;
- the text says "this is a check before the transfer, not a block", and the
  renderer refuses any wording that promises a block;
- nothing here can freeze, decline or hold a transfer. There is no code path
  from this module to a payment decision, and the sandbox case it may create is
  still a local demo record.

If this is not finished, a correct post-event sandbox is strictly better than a
half-built pre-transfer flow that raises false expectations. That is why it is
optional.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Literal

from pydantic import Field, StrictBool, StrictInt, model_validator

from anti_drop_ml.adapter import RULE_VERSION, THRESHOLD_VERSION, evaluate_snapshot
from anti_drop_ml.contracts import ClosedModel, Ref, RiskSnapshotV1, RiskDecisionV1, RiskTransactionV1, aware_utc
from pydantic import field_validator

ADVISORY_SCHEMA_VERSION = 'PlannedTransferAdvisoryV1'
ADVISORY_NOTICE_RU = 'Это проверка перед переводом, а не блокировка.'
ADVISORY_NOTICE_EN = 'This is a check before the transfer, not a block.'

FORBIDDEN_ADVISORY_PHRASES = (
    'заблокирован', 'заблокирована', 'заморажив', 'деньги заморожены', 'операция отклонена',
    'перевод отклонён', 'мы заблокируем', 'счёт закроют', 'платёж не пройдёт',
)


class PlannedTransferV1(ClosedModel):
    planned_event_id: str = Field(pattern=r'^[a-z0-9][a-z0-9_-]{2,40}$')
    requested_at: datetime
    direction: Literal['out'] = 'out'
    type: Literal['transfer', 'cash_deposit', 'cash_withdrawal', 'other'] = 'transfer'
    amount_minor: StrictInt = Field(ge=1, le=10**14, strict=True)
    currency: Literal['RUB'] = 'RUB'
    counterparty_ref: Ref | None = None
    channel: Literal['mobile_app', 'branch', 'api_sandbox']

    _time = field_validator('requested_at', mode='before')(aware_utc)


class PlannedTransferAdvisoryV1(ClosedModel):
    schema_version: Literal['PlannedTransferAdvisoryV1'] = ADVISORY_SCHEMA_VERSION
    analysis_mode: Literal['pre_transfer_advisory'] = 'pre_transfer_advisory'
    subject_ref: Ref
    analysis_at: datetime
    history: list[RiskTransactionV1] = Field(max_length=5000)
    planned_transfer: PlannedTransferV1
    synthetic: StrictBool = True

    _time = field_validator('analysis_at', mode='before')(aware_utc)

    @model_validator(mode='after')
    def advisory_rules(self):
        if self.planned_transfer.requested_at > self.analysis_at:
            raise ValueError('planned_transfer.requested_at must not be in the future')
        seen = [t.event_id for t in self.history]
        if len(seen) != len(set(seen)):
            raise ValueError('duplicate event_id in history')
        if self.planned_transfer.planned_event_id in set(seen):
            raise ValueError('planned_transfer must not be part of completed history')
        if any(t.subject_ref is not None and t.subject_ref != self.subject_ref for t in self.history):
            raise ValueError('mixed subject_ref is forbidden')
        if any(t.occurred_at > self.analysis_at for t in self.history):
            raise ValueError('completed history must not contain events after analysis_at')
        return self

    def to_snapshot(self) -> RiskSnapshotV1:
        """History-only snapshot. The planned transfer is analysed separately."""
        return RiskSnapshotV1.model_validate({
            'schema_version': 'RiskSnapshotV1',
            'subject_ref': self.subject_ref,
            'analysis_at': self.analysis_at,
            'timezone_policy': 'normalize_to_utc',
            'allow_future_events': False,
            'transactions': [t.model_dump(mode='json') for t in self.history],
            'metadata': {'label_source': 'synthetic_placeholder', 'episode_class': 'unknown'},
        })


class AdvisoryResultV1(ClosedModel):
    schema_version: Literal['AdvisoryResultV1'] = 'AdvisoryResultV1'
    advisory_id: str = Field(pattern=r'^adv_[a-f0-9]{16}$')
    analysis_mode: Literal['pre_transfer_advisory'] = 'pre_transfer_advisory'
    status: Literal['advisory_only'] = 'advisory_only'
    level: Literal['RED', 'YELLOW', 'GREEN']
    score: StrictInt = Field(ge=0, le=100, strict=True)
    score_interpretation: Literal['deterministic_rule_score_not_probability'] = 'deterministic_rule_score_not_probability'
    reason_codes: list[str] = Field(default_factory=list, max_length=16)
    rule_version: str
    threshold_version: str
    history_decision: RiskDecisionV1
    planned_transfer_contribution: dict[str, int]
    message_ru: str
    message_en: str
    advisory_notice_ru: str = ADVISORY_NOTICE_RU
    advisory_notice_en: str = ADVISORY_NOTICE_EN
    banking_action: Literal['none'] = 'none'
    synthetic: StrictBool = True


def _planned_contribution(snapshot: RiskSnapshotV1, planned: PlannedTransferV1) -> tuple[dict[str, int], int]:
    """Score the hypothetical: history plus one planned outbound transaction.

    This is a *what-if* on the same rule engine, not a payment decision. The
    planned transaction is injected only for scoring and never stored.
    """
    history_scores = evaluate_snapshot(snapshot)
    hypothetical_event_id = 'evt_' + hashlib.sha256(planned.planned_event_id.encode()).hexdigest()[:16]
    hypothetical = {
        'schema_version': 'RiskSnapshotV1',
        'subject_ref': snapshot.subject_ref,
        'analysis_at': snapshot.analysis_at,
        'timezone_policy': 'normalize_to_utc',
        'allow_future_events': True,
        'transactions': [
            *(t.model_dump(mode='json') for t in snapshot.transactions),
            {'event_id': hypothetical_event_id, 'occurred_at': planned.requested_at, 'direction': 'out',
             'type': planned.type, 'amount_minor': planned.amount_minor, 'currency': planned.currency,
             'counterparty_ref': planned.counterparty_ref, 'device_id': None, 'sim_changed_days_ago': None},
        ],
        'metadata': {'label_source': 'synthetic_placeholder', 'episode_class': 'unknown'},
    }
    with_planned = evaluate_snapshot(hypothetical)
    contribution = {code: value for code, value in with_planned.score_contributions.items()
                    if history_scores.score_contributions.get(code) != value}
    return contribution, with_planned.score


def advise(request: PlannedTransferAdvisoryV1 | dict) -> AdvisoryResultV1:
    payload = request if isinstance(request, PlannedTransferAdvisoryV1) else PlannedTransferAdvisoryV1.model_validate(request)
    snapshot = payload.to_snapshot()
    history = evaluate_snapshot(snapshot)
    contribution, score = _planned_contribution(snapshot, payload.planned_transfer)
    advisory_id = 'adv_' + hashlib.sha256(
        f'{payload.subject_ref}|{payload.planned_transfer.planned_event_id}|{RULE_VERSION}'.encode()).hexdigest()[:16]

    if level_of(score) == 'GREEN':
        message_ru = 'Признаков риска в этих операциях не найдено. Это проверка, а не блокировка перевода.'
        message_en = ('No risk pattern found for this history and planned amount. This is a check, '
                      'not a transfer block.')
    elif level_of(score) == 'YELLOW':
        message_ru = ('Есть признаки, отличающиеся от обычного поведения. Сверьте операцию с своими '
                      'и не пересылайте деньги по просьбе незнакомцев. Свяжитесь с банком через официальный канал.')
        message_en = ('Some patterns differ from the usual behaviour. Check the operation against your own '
                      'and do not forward money on a stranger’s request. Contact the bank through an official channel.')
    else:
        message_ru = ('Есть признаки рискованной схемы. Не отправляйте деньги по просьбе незнакомцев. '
                      'Свяжитесь с банком через официальный канал.')
        message_en = ('There are signs of a risky scheme. Do not send money on a stranger’s request. '
                      'Contact the bank through an official channel.')
    for text in (message_ru, message_en, ADVISORY_NOTICE_RU, ADVISORY_NOTICE_EN):
        if any(phrase in text.lower() for phrase in FORBIDDEN_ADVISORY_PHRASES):
            raise ValueError('advisory text must not promise a block')
    return AdvisoryResultV1(
        advisory_id=advisory_id, level=level_of(score), score=score,
        reason_codes=sorted(contribution), rule_version=RULE_VERSION, threshold_version=THRESHOLD_VERSION,
        history_decision=history, planned_transfer_contribution=contribution,
        message_ru=message_ru, message_en=message_en,
    )


def level_of(score: int) -> str:
    from src.policy import DEFAULT_POLICY

    return 'RED' if score >= DEFAULT_POLICY.score_red else ('YELLOW' if score >= DEFAULT_POLICY.score_yellow else 'GREEN')


def advisory_event_fields(result: AdvisoryResultV1) -> dict:
    """Field subset for the `pre_transfer_advised` event; no amounts, no refs."""
    return {
        'event_type': 'pre_transfer_advised',
        'evaluation_id': result.history_decision.evaluation_id,
        'rule_version': result.rule_version,
        'threshold_version': result.threshold_version,
        'outcome_code': 'accepted_advisory' if result.level == 'GREEN' else 'declined_advisory',
        'metadata': {'http_status': 200},
    }