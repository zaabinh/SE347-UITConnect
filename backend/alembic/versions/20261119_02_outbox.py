"""Expand: durable outbox for side effects dispatched after commit."""

from alembic import op
import sqlalchemy as sa

from scripts.migration_policy import require_phase

revision = '20261119_02'
down_revision = '20261119_01'
branch_labels = depends_on = None
migration_phase = 'expand'


def upgrade():
    require_phase(migration_phase)
    op.create_table(
        'outbox_events',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('event_type', sa.String(64), nullable=False),
        sa.Column('payload', sa.UnicodeText(), nullable=False),
        sa.Column('status', sa.String(16), nullable=False, server_default='pending'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('available_at', sa.DateTime(), nullable=False),
        sa.Column('locked_at', sa.DateTime(), nullable=True),
        sa.Column('lock_token', sa.String(36), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_outbox_events_dispatch', 'outbox_events', ['status', 'available_at'])


def downgrade():
    require_phase('contract')
    op.drop_index('ix_outbox_events_dispatch', table_name='outbox_events')
    op.drop_table('outbox_events')
