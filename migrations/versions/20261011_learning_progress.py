"""Add owned educational progress and stable request replays (additive)."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20261011_learning'
down_revision = '832fa12ce83f'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('learning_profiles', sa.Column('subject_ref', sa.String(68), primary_key=True),
                    sa.Column('state', postgresql.JSONB(), nullable=False))
    op.create_table('learning_replays', sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('subject_ref', sa.String(68), nullable=False),
                    sa.Column('key_digest', sa.String(64), nullable=False),
                    sa.Column('fingerprint', sa.String(64), nullable=False),
                    sa.Column('response', postgresql.JSONB(), nullable=False),
                    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
                    sa.UniqueConstraint('subject_ref', 'key_digest', name='uq_learning_replay_scope'))


def downgrade():
    op.drop_table('learning_replays')
    op.drop_table('learning_profiles')
