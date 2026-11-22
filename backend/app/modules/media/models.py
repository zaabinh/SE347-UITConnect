"""Draft MD-01 metadata for schema review; no automatic database creation."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Unicode, text
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Media(Base):
    __tablename__ = "media"
    __table_args__ = (
        CheckConstraint("status IN ('pending','verifying','ready','rejected','expired','deleting','deleted')", name="ck_media_status"),
        CheckConstraint("purpose = 'post_cover'", name="ck_media_purpose"),
        CheckConstraint("declared_size_bytes > 0 AND declared_size_bytes <= 5242880", name="ck_media_declared_size"),
        Index("ix_media_owner_status", "owner_id", "status"),
        Index("ix_media_expiration", "status", "upload_expires_at"),
        Index("ix_media_cleanup", "status", "cleanup_after"),
        Index("uq_media_final_key", "final_key", unique=True,
              mssql_where=text("final_key IS NOT NULL"), sqlite_where=text("final_key IS NOT NULL")),
    )

    id: Mapped[str] = mapped_column(UNIQUEIDENTIFIER(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id: Mapped[str] = mapped_column(UNIQUEIDENTIFIER(as_uuid=False), ForeignKey("users.id", ondelete="NO ACTION"))
    purpose: Mapped[str] = mapped_column(String(30), default="post_cover")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    upload_key: Mapped[str] = mapped_column(String(512), unique=True)
    final_key: Mapped[str | None] = mapped_column(String(512))
    original_filename: Mapped[str] = mapped_column(Unicode(255))
    declared_content_type: Mapped[str] = mapped_column(String(100))
    declared_size_bytes: Mapped[int] = mapped_column(BigInteger)
    verified_content_type: Mapped[str | None] = mapped_column(String(100))
    verified_input_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    stored_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64))
    failure_code: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))
    upload_expires_at: Mapped[datetime] = mapped_column(DateTime)
    verification_token: Mapped[str | None] = mapped_column(UNIQUEIDENTIFIER(as_uuid=False))
    verification_lease_until: Mapped[datetime | None] = mapped_column(DateTime)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)
    cleanup_after: Mapped[datetime | None] = mapped_column(DateTime)
