from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.db.base import Base
from app.db.uow import UnitOfWork
from app.modules.comments import application
from app.modules.comments.models import Comment
from app.modules.comments.schemas import CommentCreate
from app.modules.moderation.models import Report
from app.modules.moderation.schemas import ReportCreate
from app.modules.notifications import application as notifications
from app.modules.notifications.models import Notification
from app.modules.posts.models import Post
from app.modules.users.models import User


@compiles(UNIQUEIDENTIFIER, 'sqlite')
def sqlite_identifier(type_, compiler, **kwargs):
    return 'VARCHAR(36)'


@pytest.fixture
def db():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def seed(db):
    with UnitOfWork(db):
        users = [User(id=str(uuid4()), username=f'user{i}', email=f'user{i}@example.test',
                      full_name=f'User {i}', password_hash='hash', role='Student', status='active') for i in range(3)]
        db.add_all(users)
        post = Post(user_id=users[0].id, title='Title', content='Body', status='active')
        db.add(post)
        db.flush()
        parent = Comment(post_id=post.id, user_id=users[1].id, content='Parent')
        db.add(parent)
    return users, post, parent


def test_reply_notification_failure_rolls_back_comment_and_first_notification(db, monkeypatch):
    users, post, parent = seed(db)
    original = application.create_notification
    def fail_second(db, **kwargs):
        if kwargs['notification_type'] == 'reply':
            db.flush()
            raise RuntimeError('reply notification unavailable')
        return original(db, **kwargs)
    monkeypatch.setattr(application, 'create_notification', fail_second)
    with pytest.raises(RuntimeError, match='reply notification'):
        application.create_comment(post.id, CommentCreate(content='Reply', parent_id=parent.id), db, users[2])
    assert db.query(Comment).count() == 1
    assert db.query(Notification).count() == 0


def test_reply_success_and_comment_tree_do_not_delete_existing_replies(db):
    users, post, parent = seed(db)
    reply = application.create_comment(post.id, CommentCreate(content='Reply', parent_id=parent.id), db, users[2])
    assert reply.parent_id == parent.id
    assert db.query(Notification).count() == 2
    tree = application.get_comments(post.id, db, users[2])
    assert [item.id for item in tree[0].replies] == [reply.id]
    with UnitOfWork(db):
        parent.content = 'Updated'
    assert db.query(Comment).count() == 2


def test_comment_report_failure_rolls_back_report_and_notifications(db, monkeypatch):
    users, post, parent = seed(db)
    def fail(db, **kwargs):
        db.flush()
        raise RuntimeError('notification unavailable')
    monkeypatch.setattr(application, 'create_notification', fail)
    with pytest.raises(RuntimeError, match='notification unavailable'):
        application.report_comment(post.id, parent.id, ReportCreate(reason='spam'), db, users[2])
    assert db.query(Report).count() == 0
    assert db.query(Notification).count() == 0


def test_comment_report_duplicate_and_parent_post_scope(db):
    users, post, parent = seed(db)
    application.report_comment(post.id, parent.id, ReportCreate(reason='spam'), db, users[2])
    with pytest.raises(ApplicationError) as rejection:
        application.report_comment(post.id, parent.id, ReportCreate(reason='spam'), db, users[2])
    assert rejection.value.status_code == 409
    with pytest.raises(ApplicationError) as rejection:
        application.create_comment(post.id + 1, CommentCreate(content='Reply', parent_id=parent.id), db, users[2])
    assert rejection.value.status_code == 404
    assert db.query(Report).count() == 1


def test_notification_ownership_and_read_before_delete(db):
    users, post, parent = seed(db)
    with UnitOfWork(db):
        notice = Notification(user_id=users[0].id, type='comment', title='New comment', is_read=False)
        db.add(notice)
    notice_id = notice.id
    with pytest.raises(ApplicationError) as rejection:
        notifications.mark_notification_read(notice_id, users[1], db)
    assert rejection.value.status_code == 404
    with pytest.raises(ApplicationError) as rejection:
        notifications.delete_read_notification(notice_id, users[0], db)
    assert rejection.value.status_code == 400
    notifications.mark_notification_read(notice_id, users[0], db)
    notifications.delete_read_notification(notice_id, users[0], db)
    assert db.query(Notification).count() == 0
