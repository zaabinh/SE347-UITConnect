from io import StringIO
from datetime import datetime, timedelta

import pytest
from sqlalchemy import MetaData, Uuid, create_engine, event
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy.dialects import mssql
from sqlalchemy.schema import CreateIndex

from app.core import config as configuration
from app.modules.media.models import Media
from app.modules.posts.models import Post
from app.modules.users.models import User
from scripts.migrate import alembic_config


def test_media_revision_is_additive_offline_sqlserver(monkeypatch):
    monkeypatch.setattr(configuration, "settings", configuration.settings.model_copy(update={
        "database_url": "mssql+pyodbc://offline/unused?driver=ODBC+Driver+18+for+SQL+Server",
    }))
    config = alembic_config()
    config.output_buffer = StringIO()
    assert ScriptDirectory.from_config(config).get_current_head() == "20261122_03"
    command.upgrade(config, "20261119_02:20261122_03", sql=True)
    ddl = config.output_buffer.getvalue()
    assert "CREATE TABLE media" in ddl
    assert "ALTER TABLE posts ADD cover_media_id UNIQUEIDENTIFIER NULL" in ddl
    assert "WHERE cover_media_id IS NOT NULL" in ddl
    assert "WHERE final_key IS NOT NULL" in ddl
    assert "DROP " not in ddl and "DELETE FROM" not in ddl


def test_model_filtered_unique_indexes_allow_legacy_nulls():
    assert Post.__table__.c.cover_media_id.nullable
    for table, name, predicate in [(Post.__table__, "uq_posts_cover_media", "cover_media_id IS NOT NULL"),
                                    (Media.__table__, "uq_media_final_key", "final_key IS NOT NULL")]:
        index = next(i for i in table.indexes if i.name == name)
        sql = str(CreateIndex(index).compile(dialect=mssql.dialect()))
        assert "UNIQUE" in sql and predicate in sql


def test_media_attachment_unique_constraint_preserves_multiple_legacy_posts():
    # Execute constraints with SQLite; SQL Server DDL is covered separately above.
    engine = create_engine("sqlite://")
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    metadata = MetaData()
    for model in (User, Media, Post):
        table = model.__table__.to_metadata(metadata)
        for column in table.columns:
            if isinstance(column.type, UNIQUEIDENTIFIER):
                column.type = Uuid(as_uuid=False)
            if column.server_default is not None and "NEWSEQUENTIALID" in str(column.server_default.arg):
                column.server_default = None
    metadata.create_all(engine)
    with Session(engine) as db:
        user = User(id="11111111-1111-4111-8111-111111111111", email="test@example.com",
                    username="owner", full_name="Owner", password_hash="unused")
        db.add(user)
        db.flush()
        media = Media(owner_id=user.id, upload_key="pending/test", original_filename="image.png",
                      declared_content_type="image/png", declared_size_bytes=100,
                      upload_expires_at=datetime.now() + timedelta(minutes=5))
        db.add(media)
        db.flush()
        db.add_all([Post(user_id=user.id, title="Legacy one", content="one", cover_image="legacy-one"),
                    Post(user_id=user.id, title="Legacy two", content="two", cover_image="legacy-two"),
                    Post(user_id=user.id, title="Attached", content="three", cover_media_id=media.id)])
        db.commit()
        db.add(Post(user_id=user.id, title="Duplicate attachment", content="four", cover_media_id=media.id))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert db.query(Post).count() == 3
        assert {p.cover_image for p in db.query(Post) if p.cover_image} == {"legacy-one", "legacy-two"}
    engine.dispose()
