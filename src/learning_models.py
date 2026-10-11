"""Durable educational progress; deliberately separate from banking records."""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class LearningBase(DeclarativeBase):
    pass


class LearningProfile(LearningBase):
    __tablename__ = 'learning_profiles'
    subject_ref: Mapped[str] = mapped_column(String(68), primary_key=True)
    state: Mapped[dict] = mapped_column(JSONB, nullable=False)


class LearningReplay(LearningBase):
    __tablename__ = 'learning_replays'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_ref: Mapped[str] = mapped_column(String(68), nullable=False)
    key_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    response: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (UniqueConstraint('subject_ref', 'key_digest', name='uq_learning_replay_scope'),)
