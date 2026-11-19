"""Baseline captured from the live SQL Server catalogs on 2026-11-19.

Replays the frozen DDL, never the current ORM. Existing databases must be
verified and stamped; this migration only runs against an empty schema.
"""

from alembic import context, op
from sqlalchemy import text

from scripts.db_schema import inventory
from scripts.migration_policy import baseline_statements

revision = '20261119_01'
down_revision = None
branch_labels = None
depends_on = None
migration_phase = 'baseline'


def upgrade() -> None:
    if not context.is_offline_mode():
        schema = inventory(op.get_bind())
        if schema['tables'] or schema['modules']:
            raise RuntimeError('Database is not empty. Run python -m scripts.migrate adopt after verifying equivalence; do not replay baseline DDL.')
    for statement in baseline_statements():
        op.execute(text(statement))


def downgrade() -> None:
    raise RuntimeError('Baseline downgrade is disabled: dropping the application schema would destroy data.')
