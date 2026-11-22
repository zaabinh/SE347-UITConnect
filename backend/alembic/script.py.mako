"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from scripts.migration_policy import require_phase
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}
migration_phase: str = ${repr(config.attributes.get("migration_phase", "expand"))}


def upgrade() -> None:
    require_phase(migration_phase)
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    require_phase("contract")
    ${downgrades if downgrades else "pass"}
