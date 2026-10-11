"""Single migration job, then grant runtime only required DML privileges."""
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from src.database import get_engine

command.upgrade(Config('alembic.ini'), 'head')
with get_engine().begin() as connection:
    connection.execute(text('GRANT SELECT, INSERT, UPDATE ON risk_evaluations, sandbox_cases, case_events, idempotency_records TO antidrop_app'))
    connection.execute(text('GRANT SELECT, INSERT, UPDATE ON learning_profiles, learning_replays TO antidrop_app'))
    connection.execute(text('GRANT USAGE, SELECT ON SEQUENCE learning_replays_id_seq TO antidrop_app'))
