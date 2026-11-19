"""SQLite checks for user write transactions and access policies."""

import pytest
from sqlalchemy import MetaData, Uuid, create_engine, event, func, select
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.db.base import Base
from app.modules.notifications.models import Notification
from app.modules.posts.models import Bookmark, Post
from app.modules.users import application
from app.modules.users.models import Follow, User
from app.modules.users.schemas import UpdateProfileRequest


@pytest.fixture
def users_db(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'users.db'}")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        copied = table.to_metadata(metadata)
        for column in copied.columns:
            if isinstance(column.type, UNIQUEIDENTIFIER):
                column.type = Uuid(as_uuid=False)
            if column.server_default is not None and "NEWSEQUENTIALID" in str(column.server_default.arg):
                column.server_default = None
    metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        users = [
            User(
                id=f"00000000-0000-0000-0000-{number:012d}",
                username=name,
                email=f"{name}@example.com",
                full_name=name.title(),
                password_hash="hash",
                role=role,
                status="active",
                is_verified=True,
            )
            for number, name, role in [(1, "alice", "Student"), (2, "bob", "Student"), (3, "admin", "admin")]
        ]
        db.add_all(users)
        db.flush()
        post = Post(user_id=users[0].id, title="Alice draft", slug="alice-draft", content="Body", status="pending")
        active = Post(user_id=users[0].id, title="Alice post", slug="alice-post", content="Body", status="active")
        db.add_all([post, active])
        db.flush()
        db.add(Bookmark(user_id=users[0].id, post_id=active.id))
        db.commit()
        yield db, users, post, active
    engine.dispose()


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def commits(db):
    seen = []
    event.listen(db, "after_commit", lambda _: seen.append(True))
    return seen


def test_follow_and_notification_commit_together_once(users_db):
    db, (alice, bob, _), _, _ = users_db
    committed = commits(db)

    result = application.follow_user(db, alice, bob.id)

    assert result.message == "Followed user successfully."
    assert committed == [True]
    assert db.query(Follow).one().following_id == bob.id
    assert db.query(Notification).one().user_id == bob.id


def test_follow_notification_failure_rolls_back_follow(users_db, monkeypatch):
    db, (alice, bob, _), _, _ = users_db

    def fail_after_add(*args, **kwargs):
        db.flush()
        raise RuntimeError("notification insert failed")

    monkeypatch.setattr(application, "create_notification", fail_after_add)
    with pytest.raises(RuntimeError, match="notification insert failed"):
        application.follow_user(db, alice, bob.id)

    assert count(db, Follow) == 0
    assert count(db, Notification) == 0


def test_follow_commit_failure_rolls_back_follow_and_notification(users_db):
    db, (alice, bob, _), _, _ = users_db

    def fail_commit(session):
        session.flush()
        raise RuntimeError("commit failed")

    event.listen(db, "before_commit", fail_commit, once=True)
    with pytest.raises(RuntimeError, match="commit failed"):
        application.follow_user(db, alice, bob.id)

    assert count(db, Follow) == 0
    assert count(db, Notification) == 0


def test_profile_update_commits_once_and_normalizes_fields(users_db):
    db, (alice, _, _), _, _ = users_db
    committed = commits(db)

    result = application.update_my_profile(
        db,
        alice,
        UpdateProfileRequest(
            full_name="  Alice Example  ",
            bio="  About me  ",
            avatar_url=" ",
            major="  Computer Science ",
            academic_year=None,
            career_goal=" Research ",
            interest_tags=[" Python ", "python", " AI ", "  "],
        ),
    )

    assert committed == [True]
    assert result.full_name == "Alice Example"
    assert result.bio == "About me"
    assert result.avatar_url is None
    assert result.interest_tags == ["python", "ai"]
    assert alice.interest_tags == "python,ai"


def test_user_visibility_and_bookmark_permissions_remain_scoped(users_db):
    db, (alice, bob, admin), _, active = users_db

    assert [post.title for post in application.get_user_posts(db, bob, "alice")] == ["Alice post"]
    assert [post.title for post in application.get_user_posts(db, alice, "alice")] == [
        "Alice post", "[Chá» duyá»‡t] Alice draft",
    ]
    assert [post.title for post in application.get_user_posts(db, admin, "alice")] == [
        "Alice post", "[Chá» duyá»‡t] Alice draft",
    ]
    assert [post.id for post in application.get_user_bookmarks(db, alice, "alice")] == [active.id]
    with pytest.raises(ApplicationError) as denied:
        application.get_user_bookmarks(db, bob, "alice")
    assert denied.value.status_code == 403
