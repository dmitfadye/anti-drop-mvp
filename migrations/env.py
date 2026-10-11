"""Migrations use the same PostgreSQL-only environment contract as the API."""
from alembic import context
from src.database import Base, get_engine
from src.learning_models import LearningBase

if context.is_offline_mode():
    raise RuntimeError('Use online migrations against an explicit PostgreSQL database')
with get_engine().connect() as connection:
    context.configure(connection=connection, target_metadata=[Base.metadata, LearningBase.metadata], compare_type=True)
    with context.begin_transaction():
        context.run_migrations()
