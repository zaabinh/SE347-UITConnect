"""MD-01 expand proposal: metadata and nullable post attachment. Requires schema review."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER

from scripts.migration_policy import require_phase

revision = "20261122_03"
down_revision = "20261119_02"
branch_labels = depends_on = None
migration_phase = "expand"


def upgrade():
    require_phase(migration_phase)
    op.create_table(
        "media",
        sa.Column("id", UNIQUEIDENTIFIER(as_uuid=False), primary_key=True),
        sa.Column("owner_id", UNIQUEIDENTIFIER(as_uuid=False), sa.ForeignKey("users.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("upload_key", sa.String(512), nullable=False, unique=True),
        sa.Column("final_key", sa.String(512), nullable=True),
        sa.Column("original_filename", sa.Unicode(255), nullable=False),
        sa.Column("declared_content_type", sa.String(100), nullable=False),
        sa.Column("declared_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("verified_content_type", sa.String(100), nullable=True),
        sa.Column("verified_input_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("stored_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("failure_code", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("upload_expires_at", sa.DateTime(), nullable=False),
        sa.Column("verification_token", UNIQUEIDENTIFIER(as_uuid=False), nullable=True),
        sa.Column("verification_lease_until", sa.DateTime(), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("cleanup_after", sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('pending','verifying','ready','rejected','expired','deleting','deleted')", name="ck_media_status"),
        sa.CheckConstraint("purpose = 'post_cover'", name="ck_media_purpose"),
        sa.CheckConstraint("declared_size_bytes > 0 AND declared_size_bytes <= 5242880", name="ck_media_declared_size"),
    )
    op.create_index("ix_media_owner_status", "media", ["owner_id", "status"])
    op.create_index("ix_media_expiration", "media", ["status", "upload_expires_at"])
    op.create_index("ix_media_cleanup", "media", ["status", "cleanup_after"])
    op.create_index("uq_media_final_key", "media", ["final_key"], unique=True, mssql_where=sa.text("final_key IS NOT NULL"))
    op.add_column("posts", sa.Column("cover_media_id", UNIQUEIDENTIFIER(as_uuid=False), nullable=True))
    op.create_foreign_key("fk_posts_cover_media", "posts", "media", ["cover_media_id"], ["id"], ondelete="NO ACTION")
    op.create_index("uq_posts_cover_media", "posts", ["cover_media_id"], unique=True, mssql_where=sa.text("cover_media_id IS NOT NULL"))


def downgrade():
    # Destructive: retain legacy data and require the existing contract opt-in.
    require_phase("contract")
    op.drop_index("uq_posts_cover_media", table_name="posts")
    op.drop_constraint("fk_posts_cover_media", "posts", type_="foreignkey")
    op.drop_column("posts", "cover_media_id")
    op.drop_table("media")
