"""Real session tests for atomic moderation and domain permission failures."""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.exceptions import ApplicationError, application_exception_handler
from app.db.base import Base
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.moderation import application, router
from app.modules.moderation.models import AdminAuditLog, Report
from app.modules.moderation.schemas import ReportModerate
from app.modules.notifications.models import Notification
from app.modules.posts.models import Post, PostTag, Tag
from app.modules.users.models import Follow, User


@compiles(UNIQUEIDENTIFIER, "sqlite")
def compile_uuid_for_sqlite(type_, compiler, **kwargs):
    return "CHAR(32)"


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


def make_user(name, role="Student"):
    return User(id=str(uuid.uuid4()), username=name, email=f"{name}@example.com",
                full_name=name, password_hash="hash", role=role, status="active", is_verified=True)


@pytest.fixture
def moderation_data(db):
    admin, author, reporter = make_user("admin", "admin"), make_user("author"), make_user("reporter")
    db.add_all([admin, author, reporter])
    db.flush()
    post = Post(user_id=author.id, title="Review me", content="Body", status="pending",
                requested_new_tags='["new tag"]')
    db.add(post)
    db.flush()
    report = Report(reporter_id=reporter.id, post_id=post.id, reason="spam", status="pending")
    db.add(report)
    db.add(Follow(follower_id=reporter.id, following_id=author.id))
    db.commit()
    return admin, author, reporter, post, report


def assert_no_moderation_effects(db, post_id, author_id, report_id):
    db.expire_all()
    assert db.get(Post, post_id).status == "pending"
    assert db.get(User, author_id).status == "active"
    assert db.get(Report, report_id).status == "pending"
    assert db.query(AdminAuditLog).count() == 0
    assert db.query(Notification).count() == 0


def test_approval_notification_failure_rolls_back_tags_status_audit_and_notifications(db, moderation_data, monkeypatch):
    admin, author, _, post, report = moderation_data
    post_id, author_id, report_id = post.id, author.id, report.id
    original_notify_followers = application.notify_followers

    def fail_after_notifications(session, **kwargs):
        original_notify_followers(session, **kwargs)
        session.flush()
        raise RuntimeError("notification delivery failed")

    monkeypatch.setattr(application, "notify_followers", fail_after_notifications)
    # Authentication has already opened a transaction before the application use case.
    db.query(User).filter(User.id == admin.id).first()
    assert db.in_transaction()
    with pytest.raises(RuntimeError, match="notification delivery failed"):
        application.approve_post(db, admin, post_id)
    assert not db.in_transaction()
    assert_no_moderation_effects(db, post_id, author_id, report_id)
    assert db.get(Post, post_id).requested_new_tags == '["new tag"]'
    assert db.query(Tag).count() == 0
    assert db.query(PostTag).count() == 0


def test_audit_persistence_failure_rolls_back_ban_and_notification(db, moderation_data):
    admin, author, _, post, report = moderation_data
    post_id, author_id, report_id = post.id, author.id, report.id

    def fail_audit(session, flush_context, instances):
        if any(isinstance(item, AdminAuditLog) for item in session.new):
            raise RuntimeError("audit write failed")

    event.listen(db, "before_flush", fail_audit)
    try:
        with pytest.raises(RuntimeError, match="audit write failed"):
            application.ban_user(db, admin, author_id, "spam")
    finally:
        event.remove(db, "before_flush", fail_audit)
    assert not db.in_transaction()
    assert_no_moderation_effects(db, post_id, author_id, report_id)


def test_report_notification_failure_rolls_back_hidden_post_ban_audits_and_report(db, moderation_data, monkeypatch):
    admin, author, _, post, report = moderation_data
    post_id, author_id, report_id = post.id, author.id, report.id
    original_create_notification = application.create_notification

    def fail_report_update(session, **kwargs):
        notification = original_create_notification(session, **kwargs)
        if kwargs["notification_type"] == "report_update":
            session.flush()
            raise RuntimeError("report notification failed")
        return notification

    monkeypatch.setattr(application, "create_notification", fail_report_update)
    with pytest.raises(RuntimeError, match="report notification failed"):
        application.moderate_report(db, admin, report_id,
                                    ReportModerate(status="resolved", action="hide_post_and_ban_author"))
    assert not db.in_transaction()
    assert_no_moderation_effects(db, post_id, author_id, report_id)
    assert db.get(Report, report_id).reviewed_at is None


def test_approval_commits_once_with_tag_link_audit_and_author_and_follower_notifications(db, moderation_data):
    admin, _, reporter, post, _ = moderation_data
    commits = []
    event.listen(db, "after_commit", lambda session: commits.append(True))
    application.approve_post(db, admin, post.id)
    assert len(commits) == 1
    db.expire_all()
    assert db.get(Post, post.id).status == "active"
    assert db.get(Post, post.id).requested_new_tags is None
    assert db.query(Tag).one().name == "new tag"
    assert db.query(PostTag).one().post_id == post.id
    assert db.query(AdminAuditLog).one().action_type == "approve_post"
    notifications = db.query(Notification).order_by(Notification.id).all()
    assert [item.type for item in notifications] == ["post_approved", "new_post"]
    assert notifications[1].user_id == reporter.id


@pytest.mark.parametrize("target_kind,detail", [
    ("self", "Admin cannot ban themselves."),
    ("admin", "Admin accounts cannot be banned."),
])
def test_ban_permissions_leave_no_writes(db, moderation_data, target_kind, detail):
    admin, author, _, post, report = moderation_data
    post_id, author_id, report_id = post.id, author.id, report.id
    if target_kind == "self":
        target_id = admin.id
    else:
        author.role = "AdMiN"
        db.commit()
        target_id = author.id
    with pytest.raises(ApplicationError) as error:
        application.ban_user(db, admin, target_id, None)
    assert error.value.status_code == 400
    assert error.value.detail == detail
    assert_no_moderation_effects(db, post_id, author_id, report_id)


def test_combined_report_action_rolls_back_hide_when_author_is_admin(db, moderation_data):
    admin, author, _, post, report = moderation_data
    author.role = "admin"
    db.commit()
    post_id, author_id, report_id = post.id, author.id, report.id
    with pytest.raises(ApplicationError, match="Admin accounts cannot be banned"):
        application.moderate_report(db, admin, report_id,
                                    ReportModerate(status="resolved", action="hide_post_and_ban_author"))
    assert_no_moderation_effects(db, post_id, author_id, report_id)


@pytest.mark.parametrize("status,action,detail", [
    ("reviewed", "hide_post", "Only resolved reports can apply moderation actions."),
    ("resolved", "none", "Resolved reports must include a moderation action."),
    ("resolved", "hide_comment", "Post reports cannot use comment-only actions."),
])
def test_invalid_report_actions_leave_no_writes(db, moderation_data, status, action, detail):
    admin, author, _, post, report = moderation_data
    post_id, author_id, report_id = post.id, author.id, report.id
    with pytest.raises(ApplicationError) as error:
        application.moderate_report(db, admin, report_id, ReportModerate(status=status, action=action))
    assert error.value.status_code == 400
    assert error.value.detail == detail
    assert_no_moderation_effects(db, post_id, author_id, report_id)


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/admin/users", None),
    ("PUT", "/admin/users/any/ban", {"reason": None}),
    ("DELETE", "/admin/users/any/ban", None),
    ("GET", "/admin/reports", None),
    ("PUT", "/admin/reports/1/moderation", {"status": "dismissed"}),
    ("GET", "/admin/posts/pending", None),
    ("PUT", "/admin/posts/1/moderation", {"status": "active"}),
    ("PUT", "/admin/posts/1/moderation", {"status": "rejected"}),
    ("GET", "/admin/analytics/overview", None),
    ("GET", "/admin/tags", None),
    ("POST", "/admin/tags", {"name": "tag"}),
    ("PATCH", "/admin/tags/1", {"name": "tag"}),
    ("DELETE", "/admin/tags/1", None),
])
def test_admin_endpoints_reject_non_admin(db, method, path, body):
    app = FastAPI()
    app.include_router(router.router)
    app.add_exception_handler(ApplicationError, application_exception_handler)
    app.dependency_overrides[get_current_user] = lambda: make_user("student")
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        response = client.request(method, path, json=body)
    assert response.status_code == 403
    assert response.json()["detail"] == "You do not have permission to access this resource."


def test_pending_listing_and_analytics_read_through_repository(db, moderation_data):
    _, _, _, post, report = moderation_data
    pending = application.list_pending_posts(db, 1, 20)
    assert pending["meta"] == {"page": 1, "page_size": 20, "total": 1, "total_pages": 1}
    assert pending["items"][0]["id"] == post.id
    assert pending["items"][0]["requested_new_tags"] == ["new tag"]
    reports = application.list_reports(db, 1, 20, "pending", "spam")
    assert reports["items"] == [report]
    assert application.analytics_overview(db)["pending_posts"] == 1
    assert application.analytics_overview(db)["pending_reports"] == 1
