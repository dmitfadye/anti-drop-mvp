"""Normalize strict snapshots and reuse the existing, instrumented rules engine."""
import hashlib
import json

from anti_drop_ml.contracts import RiskDecisionV1, RiskSnapshotV1
from src.detector import analyze_transactions
from src.policy import DEFAULT_POLICY

RULE_VERSION = DEFAULT_POLICY.version
THRESHOLD_VERSION = 'thresholds-2026.10.08-red50-yellow25'
ADAPTER_VERSION = 'snapshot-adapter-v1'


def evaluate_snapshot(snapshot: RiskSnapshotV1 | dict) -> RiskDecisionV1:
    # Revalidate even model instances: never trust model_construct or mutated nested lists.
    snapshot = RiskSnapshotV1.model_validate(snapshot.model_dump() if isinstance(snapshot, RiskSnapshotV1) else snapshot)
    ordered = sorted(snapshot.transactions, key=lambda t: (t.occurred_at, t.event_id))
    canonical = snapshot.model_dump(mode='json', exclude={'metadata'})
    canonical['transactions'] = [t.model_dump(mode='json') for t in ordered]
    identity = {'snapshot': canonical, 'rules': RULE_VERSION, 'thresholds': THRESHOLD_VERSION, 'adapter': ADAPTER_VERSION}
    evaluation_id = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    transactions = []
    for t in ordered:
        # Family collections remain P2P: a self-declared purpose is not evidence of legitimacy.
        kind = ('incoming_p2p' if t.direction == 'in' else 'outgoing_p2p') if t.type in ('transfer', 'family_collection') else {'salary': 'incoming_salary', 'cash_withdrawal': 'cash_withdraw'}.get(t.type, 'purchase')
        transactions.append({'id': t.event_id, 'user_id': snapshot.subject_ref, 'ts': t.occurred_at, 'type': kind, 'amount': t.amount_minor / 100, 'counterparty': t.counterparty_ref or '', 'device_id': t.device_id or '', 'sim_changed_days_ago': t.sim_changed_days_ago})
    result = analyze_transactions(transactions, now=snapshot.analysis_at)
    contributions = result['metrics'].get('score_contributions', {})
    effective = [t for t in ordered if t.occurred_at <= snapshot.analysis_at]
    codes = sorted(contributions)
    if not effective:
        codes.append('insufficient_data')
    if any(abs((snapshot.analysis_at - t.occurred_at).total_seconds() - DEFAULT_POLICY.transit_window_min * 60) <= 60 for t in effective):
        codes.append('borderline_window')
    return RiskDecisionV1(
        evaluation_id=evaluation_id, subject_ref=snapshot.subject_ref, analysis_at=snapshot.analysis_at,
        rule_version=RULE_VERSION, threshold_version=THRESHOLD_VERSION, level=result['level'], score=result['score'],
        reason_codes=codes, score_contributions=contributions,
        window_used={'short_minutes': DEFAULT_POLICY.transit_window_min, 'long_hours': DEFAULT_POLICY.cashout_window_h},
        data_quality={'has_missing_sim': any(t.sim_changed_days_ago is None for t in effective), 'has_missing_device': any(t.device_id is None for t in effective), 'future_events_rejected': False, 'duplicate_events_rejected': False, 'future_events_excluded': len(ordered) - len(effective)},
        status='ok' if effective else 'insufficient_data',
    )
