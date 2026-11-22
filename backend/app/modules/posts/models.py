from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, Unicode, UnicodeText, Index, text
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (Index("uq_posts_cover_media", "cover_media_id", unique=True,
                            mssql_where=text("cover_media_id IS NOT NULL"),
                            sqlite_where=text("cover_media_id IS NOT NULL")),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=False),
        ForeignKey("users.id", ondelete="NO ACTION"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    content: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    cover_image: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_media_id: Mapped[str | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=False),
        ForeignKey("media.id", name="fk_posts_cover_media", ondelete="NO ACTION"), nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending", index=True)
    original_post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id", ondelete="NO ACTION"), nullable=True, index=True)
    share_caption: Mapped[str | None] = mapped_column(UnicodeText, nullable=True)
    requested_new_tags: Mapped[str | None] = mapped_column(UnicodeText, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    author = relationship("User", back_populates="posts")
    original_post = relationship("Post", remote_side=[id], uselist=False)
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    bookmarks = relationship("Bookmark", back_populates="post", cascade="all, delete-orphan")
    likes = relationship("PostLike", back_populates="post", cascade="all, delete-orphan")
    tags = relationship("PostTag", back_populates="post", cascade="all, delete-orphan")
    views = relationship("PostView", back_populates="post", cascade="all, delete-orphan")
    shares = relationship("PostShare", back_populates="post", cascade="all, delete-orphan")


class Bookmark(Base):
    __tablename__ = "bookmarks"

    user_id: Mapped[str] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=False),
        ForeignKey("users.id"),
        primary_key=True,
    )
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="NO ACTION"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User", back_populates="bookmarks")
    post = relationship("Post", back_populates="bookmarks")


class PostLike(Base):
    __tablename__ = "post_likes"

    user_id: Mapped[str] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=False),
        ForeignKey("users.id", ondelete="NO ACTION"),
        primary_key=True,
    )
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="NO ACTION"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User", back_populates="post_likes")
    post = relationship("Post", back_populates="likes")


class PostShare(Base):
    __tablename__ = "post_shares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="NO ACTION"), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(UNIQUEIDENTIFIER(as_uuid=False), ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    post = relationship("Post", back_populates="shares")
    user = relationship("User", back_populates="post_shares")


class PostTag(Base):
    __tablename__ = "post_tags"

    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)

    post = relationship("Post", back_populates="tags", passive_deletes=True)
    tag = relationship("Tag", back_populates="posts", passive_deletes=True)


class PostView(Base):
    __tablename__ = "post_views"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="NO ACTION"), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(UNIQUEIDENTIFIER(as_uuid=False), ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    post = relationship("Post", back_populates="views")
    user = relationship("User", back_populates="post_views")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    posts = relationship("PostTag", back_populates="tag", cascade="all, delete-orphan", passive_deletes=True)
