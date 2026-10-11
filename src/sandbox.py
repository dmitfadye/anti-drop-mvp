"""Authenticated synthetic workflow, atomic durable case creation and scoped replay."""
import hashlib
import hmac
import json
import os
import re
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import Field
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from anti_drop_ml.adapter import evaluate_snapshot
from anti_drop_ml.contracts import ClosedModel, RiskDecisionV1, RiskSnapshotV1
from src.database import CaseEvent, IdempotencyRecord, RiskEvaluation, SandboxCase, get_engine

router = APIRouter(tags=['Persistent synthetic sandbox'])
NEXT_STEP = 'Тестовое обращение зарегистрировано. Реальное обращение в банк не отправлялось.'


class ErrorModel(ClosedModel):
    error_code: str
    field: str | None = None
    detail: str
    request_id: str
    errors: list[dict] = Field(default_factory=list)


class SandboxCaseCreate(ClosedModel):
    evaluation_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    selected_language: Literal['ru', 'en', 'uz', 'tg', 'ky', 'zh', 'ar'] = 'ru'
    contact_reason: Literal['explain_risk', 'suspicious_request', 'need_assistance']
    client_comment: str | None = Field(default=None, max_length=500, description='Synthetic only; fingerprinted, not retained')


class SandboxCaseResponse(ClosedModel):
    case_id: UUID
    evaluation_id: str
    status: Literal['registered-sandbox']
    selected_language: str
    contact_reason: str
    created_at: datetime
    sandbox: Literal[True] = True
    next_step: str = NEXT_STEP


def trusted_subject(credentials: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False))) -> str:
    """Server-configured opaque credentials, never a client-supplied subject header."""
    try:
        tokens = json.loads(os.environ.get('SANDBOX_TOKENS', '{}'))
        if not isinstance(tokens, dict) or not tokens:
            raise ValueError('disabled')
        if any(not isinstance(k, str) or len(k) < 32 or not isinstance(v, str) or not re.fullmatch(r'sub_[a-f0-9]{8,64}', v) for k, v in tokens.items()):
            raise ValueError('invalid server config')
    except (ValueError, TypeError):
        raise HTTPException(503, 'Sandbox identity is not configured') from None
    provided = credentials.credentials if credentials else ''
    if not credentials or credentials.scheme.lower() != 'bearer' or len(provided) > 512:
        raise HTTPException(401, 'Valid sandbox bearer credential required', headers={'WWW-Authenticate': 'Bearer'})
    for token, subject in tokens.items():
        if hmac.compare_digest(token.encode(), provided.encode()):
            return subject
    raise HTTPException(401, 'Valid sandbox bearer credential required', headers={'WWW-Authenticate': 'Bearer'})


def case_response(row):
    if row is None:
        raise HTTPException(410, 'Synthetic case expired under retention policy')
    return SandboxCaseResponse.model_validate({key: getattr(row, key) for key in ('case_id', 'evaluation_id', 'status', 'selected_language', 'contact_reason', 'created_at')})


@router.post('/sandbox/evaluations', response_model=RiskDecisionV1)
def persist_evaluation(snapshot: RiskSnapshotV1, subject: str = Depends(trusted_subject)):
    if snapshot.subject_ref != subject:
        raise HTTPException(403, 'Snapshot subject does not match authenticated sandbox identity')
    decision = evaluate_snapshot(snapshot)
    with Session(get_engine()) as session, session.begin():
        session.execute(insert(RiskEvaluation).values(
            evaluation_id=decision.evaluation_id, subject_ref=subject, analysis_at=decision.analysis_at,
            risk_level=decision.level, risk_score=decision.score, rule_version=decision.rule_version,
            decision_status=decision.status, source_type=decision.source_type, decision=decision.model_dump(mode='json'),
        ).on_conflict_do_nothing(index_elements=['evaluation_id']))
    # Exiting session.begin commits before any successful response.
    return decision


@router.get('/sandbox/evaluations/{evaluation_id}', response_model=RiskDecisionV1)
def read_evaluation(evaluation_id: str, subject: str = Depends(trusted_subject)):
    if not re.fullmatch(r'[a-f0-9]{64}', evaluation_id):
        raise HTTPException(404, 'Evaluation not found')
    with Session(get_engine()) as session:
        row = session.scalar(select(RiskEvaluation).where(RiskEvaluation.evaluation_id == evaluation_id, RiskEvaluation.subject_ref == subject))
        if row is None:
            raise HTTPException(404, 'Evaluation not found')
        return RiskDecisionV1.model_validate(row.decision)


@router.post('/sandbox/cases', response_model=SandboxCaseResponse, status_code=201)
def create_sandbox_case(body: SandboxCaseCreate, idempotency_key: str = Header(min_length=1, max_length=128), subject: str = Depends(trusted_subject)):
    if not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', idempotency_key):
        raise HTTPException(422, 'Idempotency-Key must contain visible ASCII identifier characters')
    fingerprint = hashlib.sha256(json.dumps(body.model_dump(mode='json'), sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
    key_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()
    scope = f'{subject}|create_case|{key_hash}'
    lock_id = int.from_bytes(hashlib.sha256(scope.encode()).digest()[:8], 'big', signed=True)
    with Session(get_engine()) as session, session.begin():
        # Transaction lock serializes retries; unique constraint remains the final DB invariant.
        session.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': lock_id})
        previous = session.scalar(select(IdempotencyRecord).where(
            IdempotencyRecord.subject_ref == subject, IdempotencyRecord.operation_type == 'create_case',
            IdempotencyRecord.idempotency_key == key_hash))
        if previous:
            if previous.request_fingerprint != fingerprint:
                raise HTTPException(409, 'Idempotency-Key already used with a different request')
            response = case_response(session.get(SandboxCase, previous.response_reference))
        else:
            evaluation = session.scalar(select(RiskEvaluation).where(RiskEvaluation.evaluation_id == body.evaluation_id, RiskEvaluation.subject_ref == subject).with_for_update())
            if evaluation is None:
                raise HTTPException(404, 'Evaluation not found')
            row = SandboxCase(case_id=uuid4(), subject_ref=subject, evaluation_id=body.evaluation_id,
                              selected_language=body.selected_language, contact_reason=body.contact_reason)
            session.add(row)
            session.flush()
            session.add(CaseEvent(case_id=row.case_id, event_type='case_registered', previous_status=None, new_status=row.status))
            session.add(IdempotencyRecord(subject_ref=subject, operation_type='create_case', idempotency_key=key_hash,
                                          request_fingerprint=fingerprint, response_reference=row.case_id))
            response = case_response(row)
    return response


@router.get('/sandbox/cases/{case_id}', response_model=SandboxCaseResponse)
def read_case(case_id: UUID, subject: str = Depends(trusted_subject)):
    with Session(get_engine()) as session:
        row = session.scalar(select(SandboxCase).where(SandboxCase.case_id == case_id, SandboxCase.subject_ref == subject))
        if row is None:
            raise HTTPException(404, 'Case not found')
        return case_response(row)


@router.get('/sandbox/cases', response_model=list[SandboxCaseResponse])
def list_cases(limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0, le=10000), subject: str = Depends(trusted_subject)):
    with Session(get_engine()) as session:
        rows = session.scalars(select(SandboxCase).where(SandboxCase.subject_ref == subject).order_by(SandboxCase.created_at.desc(), SandboxCase.case_id).offset(offset).limit(limit))
        return [case_response(row) for row in rows]
