from sqlalchemy.orm.attributes import set_committed_value
from app.modules.comments.domain import require_found, require_unreported
from app.db.uow import UnitOfWork
from app.modules.comments.repository import CommentRepository
from app.modules.comments.models import Comment
from app.modules.moderation.models import Report
from app.modules.notifications.service import create_notification, notify_admins
from app.modules.moderation.service import normalize_report_reason


def build_comment_tree(comments) -> list[Comment]:
    by_parent: dict[int | None, list[Comment]] = {}
    for comment in comments:
        by_parent.setdefault(comment.parent_id, []).append(comment)
    for siblings in by_parent.values():
        siblings.sort(key=lambda item: (item.created_at, item.id))
    for comment in comments:
        set_committed_value(comment, 'replies', by_parent.get(comment.id, []))
    return by_parent.get(None, [])


def create_comment(post_id, payload, db, current_user):
    repo = CommentRepository(db)
    with UnitOfWork(db):
        post = require_found(repo.post(post_id), 'Post')
        parent_comment = None
        if payload.parent_id is not None:
            parent_comment = require_found(repo.comment(post_id, payload.parent_id), 'Parent comment')
        comment = Comment(post_id=post_id, user_id=current_user.id, content=payload.content.strip(), parent_id=payload.parent_id)
        repo.add(comment)
        if post.user_id != current_user.id:
            create_notification(db, user_id=post.user_id, actor_id=current_user.id, notification_type='comment', title='New comment on your post', message=f'{current_user.username} commented on your post.', post_id=post_id)
        if parent_comment and parent_comment.user_id != current_user.id:
            create_notification(db, user_id=parent_comment.user_id, actor_id=current_user.id, notification_type='reply', title='New reply to your comment', message=f'{current_user.username} replied to your comment.', post_id=post_id, comment_id=parent_comment.id)
        repo.flush()
        repo.refresh(comment)
        comment = repo.comment(post_id, comment.id)
        set_committed_value(comment, 'replies', [])
        return comment


def get_comments(post_id, db, current_user):
    repo = CommentRepository(db)
    _ = current_user.id
    comments = repo.active_comments(post_id)
    return build_comment_tree(comments)


def report_comment(post_id, comment_id, payload, db, current_user):
    repo = CommentRepository(db)
    with UnitOfWork(db):
        comment = require_found(repo.comment(post_id, comment_id), 'Comment')
        require_unreported(repo.reported(current_user.id, comment_id))
        report = Report(reporter_id=current_user.id, post_id=post_id, comment_id=comment_id, reason=normalize_report_reason(payload.reason), details=payload.details.strip() if payload.details else None)
        repo.add(report)
        repo.flush()
        notify_admins(db, actor_id=current_user.id, notification_type='comment_report', title='New comment report', message=f'{current_user.username} reported comment #{comment.id}.', post_id=post_id, comment_id=comment.id, report_id=report.id)
        if comment.user_id != current_user.id:
            create_notification(db, user_id=comment.user_id, actor_id=None, notification_type='comment_reported', title='Your comment was reported', message='Your comment has been reported and is awaiting review.', post_id=post_id, comment_id=comment.id, report_id=report.id)
        repo.flush()
        repo.refresh(report)
        return report
