"""PostgreSQL-only persistence. Raw financial snapshots are never stored."""
import os
from datetime import datetime, timezone
from functools import lru_cache
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint, create_engine
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class RiskEvaluation(Base):
    __tablename__ = 'risk_evaluations'
    evaluation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject_ref: Mapped[str] = mapped_column(String(68), nullable=False)
    analysis_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(24), nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_version: Mapped[str] = mapped_column(String(80), nullable=False)
    decision_status: Mapped[str] = mapped_column(String(24), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    # JSONB preserves the bounded versioned decision, not arbitrary transaction metadata.
    decision: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    __table_args__ = (
        UniqueConstraint('evaluation_id', 'subject_ref', name='uq_evaluation_owner'),
        CheckConstraint('risk_score BETWEEN 0 AND 100', name='ck_risk_score'),
        CheckConstraint("source_type IN ('synthetic', 'sandbox')", name='ck_source_type'),
        Index('ix_evaluation_subject_created', 'subject_ref', 'created_at'),
        Index('ix_evaluation_created', 'created_at'),
    )


class SandboxCase(Base):
    __tablename__ = 'sandbox_cases'
    case_id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    subject_ref: Mapped[str] = mapped_column(String(68), nullable=False)
    evaluation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default='registered-sandbox', nullable=False)
    selected_language: Mapped[str] = mapped_column(String(5), nullable=False)
    contact_reason: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(['evaluation_id', 'subject_ref'], ['risk_evaluations.evaluation_id', 'risk_evaluations.subject_ref'], ondelete='CASCADE', name='fk_case_evaluation_owner'),
        Index('ix_case_subject_created', 'subject_ref', 'created_at', 'case_id'),
        CheckConstraint("status = 'registered-sandbox'", name='ck_case_status'),
    )


class CaseEvent(Base):
    __tablename__ = 'case_events'
    event_id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[object] = mapped_column(UUID(as_uuid=True), ForeignKey('sandbox_cases.case_id', ondelete='CASCADE'), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(24))
    new_status: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    __table_args__ = (Index('ix_case_event_case', 'case_id'),)


class IdempotencyRecord(Base):
    __tablename__ = 'idempotency_records'
    id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    subject_ref: Mapped[str] = mapped_column(String(68), nullable=False)
    operation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    # Only a digest of the client key is retained.
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    response_reference: Mapped[object] = mapped_column(UUID(as_uuid=True), ForeignKey('sandbox_cases.case_id', ondelete='CASCADE'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    __table_args__ = (UniqueConstraint('subject_ref', 'operation_type', 'idempotency_key', name='uq_idempotency_scope'),)


def database_url():
    value = os.environ.get('DATABASE_URL', '')
    if not value.startswith('postgresql+psycopg://'):
        raise DatabaseNotConfigured('DATABASE_URL must use postgresql+psycopg; no in-memory fallback')
    return value


class DatabaseNotConfigured(RuntimeError):
    pass


@lru_cache(maxsize=2)
def engine_for(url: str):
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5,
                         connect_args={'connect_timeout': 3, 'options': '-c timezone=UTC -c statement_timeout=5000 -c lock_timeout=5000'},
                         hide_parameters=True)


def get_engine():
    return engine_for(database_url())
