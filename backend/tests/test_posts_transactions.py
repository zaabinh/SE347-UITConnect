"""Real database checks for post transaction boundaries and preserved policies."""

import pytest
from sqlalchemy import MetaData, Uuid, create_engine, event, func, select
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.db.base import Base
from app.modules.comments.models import Comment
from app.modules.notifications.models import Notification
from app.modules.posts import application
from app.modules.posts.models import Bookmark, Post, PostLike, PostShare, PostTag, PostView, Tag
from app.modules.posts.schemas import PostCreate, PostUpdate, SharePostRequest
from app.modules.users.models import Follow, User


@pytest.fixture
def posts_db(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'posts.db'}")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    # Adapt only DDL; the production ORM models and repository queries run unchanged.
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        copied = table.to_metadata(metadata)
        for column in copied.columns:
            if isinstance(column.type, UNIQUEIDENTIFIER):
                column.type = Uuid(as_uuid=False)
            if column.server_default is not None and "NEWSEQUENTIALID" in str(column.server_default.arg):
                column.server_default = None
    metadata.create_all(engine)
    with Session(engine) as db:
        users = [
            User(id=f"00000000-0000-0000-0000-{number:012d}", username=name,
                 email=f"{name}@example.com", full_name=name, password_hash="hash",
                 role=role, status="active", is_verified=True)
            for number, name, role in [(1, "author", "Student"), (2, "sharer", "admin"), (3, "follower", "Student")]
        ]
        db.add_all(users)
        db.flush()
        author, sharer, follower = users
        post = Post(user_id=author.id, title="Original post", slug="original-post", content="Original body", status="active")
        tag = Tag(name="python", slug="python")
        db.add_all([post, tag, Follow(follower_id=follower.id, following_id=sharer.id)])
        db.flush()
        db.add(PostTag(post_id=post.id, tag_id=tag.id))
        db.commit()
        yield db, author, sharer, follower, post
    engine.dispose()


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def assert_no_share(db):
    assert count(db, Post) == 1
    assert count(db, PostShare) == 0
    assert count(db, PostTag) == 1
    assert count(db, Notification) == 0


@pytest.mark.parametrize("failure", ["tags", "followers", "author", "response", "commit"])
def test_share_failure_rolls_back_post_tags_share_and_notifications(posts_db, monkeypatch, failure):
    db, _, sharer, _, post = posts_db
    post_id = post.id
    # Authentication has already autobegun the request transaction.
    db.query(User).filter(User.id == sharer.id).one()

    def fail_after(original):
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            db.flush()
            raise RuntimeError(f"injected {failure} failure")
        return fail

    if failure == "tags":
        monkeypatch.setattr(application.PostRepository, "sync_tags", fail_after(application.PostRepository.sync_tags))
    elif failure == "followers":
        monkeypatch.setattr(application, "notify_followers", fail_after(application.notify_followers))
    elif failure == "author":
        monkeypatch.setattr(application, "create_notification", fail_after(application.create_notification))
    elif failure == "response":
        def invalid_response(**kwargs):
            db.flush()
            raise RuntimeError("injected response failure")
        monkeypatch.setattr(application, "MessageResponse", invalid_response)
    else:
        def reject_commit(_):
            raise RuntimeError("injected commit failure")
        event.listen(db, "before_commit", reject_commit, once=True)

    with pytest.raises(RuntimeError, match=f"injected {failure} failure"):
        application.share_post(db, sharer, post_id, SharePostRequest(caption=" Caption "))
    assert_no_share(db)


def test_share_success_commits_once_with_tags_and_both_notifications(posts_db):
    db, author, sharer, follower, post = posts_db
    commits = []
    event.listen(db, "after_commit", lambda _: commits.append(True))

    response = application.share_post(db, sharer, post.id, SharePostRequest(caption=" Caption "))

    assert commits == [True]
    shared = db.get(Post, int(response.message.rsplit("/", 1)[1]))
    assert shared.original_post_id == post.id
    assert shared.status == "active"
    assert shared.share_caption == "Caption"
    assert shared.content == f"Caption\n\nShared from @author • Original post #{post.id}\n\nOriginal body"
    assert [association.tag.name for association in shared.tags] == ["python"]
    assert count(db, PostShare) == 1
    notifications = db.query(Notification).all()
    assert {(notification.type, notification.user_id, notification.post_id) for notification in notifications} == {
        ("new_post", follower.id, shared.id), ("post_share", author.id, post.id),
    }


def test_student_share_stays_pending_and_notifies_original_author(posts_db):
    db, author, _, follower, post = posts_db
    response = application.share_post(db, follower, post.id)
    shared = db.get(Post, int(response.message.rsplit("/", 1)[1]))
    assert shared.status == "pending"
    assert [(notice.type, notice.user_id) for notice in db.query(Notification).all()] == [("post_share", author.id)]


def test_owner_update_returns_pending_post_and_requests_unknown_tags(posts_db):
    db, author, _, _, post = posts_db
    response = application.update_post(db, author, post.id, PostUpdate(title="Edited title", tags=[" PYTHON ", "new-tag"]))
    assert response.title == "Edited title"
    assert response.status == "pending"
    assert response.tags == ["python"]
    assert response.requested_new_tags == ["new-tag"]
    assert count(db, Tag) == 1


def test_create_and_detail_include_persisted_tags_and_view_count(posts_db):
    db, _, sharer, _, _ = posts_db
    created = application.create_post(db, sharer, PostCreate(title="Fresh post", content=" Body ", tags=["new-tag"]))
    assert created.tags == ["new-tag"]
    assert created.status == "active"
    detail = application.get_post_detail(db, sharer, created.id)
    assert detail.views_count == 1
    assert count(db, PostView) == 1


def test_student_cannot_view_another_pending_post_or_update_as_admin(posts_db):
    db, _, sharer, follower, post = posts_db
    post.status = "pending"
    db.commit()
    with pytest.raises(ApplicationError) as hidden:
        application.get_post_detail(db, follower, post.id)
    assert hidden.value.status_code == 403
    assert count(db, PostView) == 0
    with pytest.raises(ApplicationError) as forbidden:
        application.update_post(db, sharer, post.id, PostUpdate(title="Admin cannot edit"))
    assert forbidden.value.status_code == 403
    assert db.get(Post, post.id).title == "Original post"


def test_post_with_comments_requires_admin_to_delete(posts_db):
    db, author, sharer, _, post = posts_db
    db.add(Comment(post_id=post.id, user_id=author.id, content="Comment", status="active"))
    db.commit()
    with pytest.raises(ApplicationError) as forbidden:
        application.delete_post(db, author, post.id)
    assert forbidden.value.status_code == 400
    assert db.get(Post, post.id).status == "active"
    application.delete_post(db, sharer, post.id)
    assert db.get(Post, post.id).status == "deleted"
    assert db.query(Notification).one().type == "post_moderation"


def test_like_and_bookmark_toggle_both_ways(posts_db):
    db, _, _, follower, post = posts_db
    application.toggle_like(db, follower, post.id)
    application.toggle_bookmark(db, follower, post.id)
    assert count(db, PostLike) == count(db, Bookmark) == 1
    assert db.query(Notification).one().type == "post_like"
    application.toggle_like(db, follower, post.id)
    application.toggle_bookmark(db, follower, post.id)
    assert count(db, PostLike) == count(db, Bookmark) == 0
