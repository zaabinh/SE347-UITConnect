"""Post use cases; each write and its notifications share one transaction."""

import json

from app.core.exceptions import ApplicationError
from app.db.uow import UnitOfWork
from app.modules.auth.schemas import MessageResponse
from app.modules.moderation.models import Report
from app.modules.moderation.schemas import ReportResponse
from app.modules.moderation.service import normalize_report_reason
from app.modules.notifications.service import create_notification, notify_admins, notify_followers
from app.modules.posts import domain
from app.modules.posts.models import Bookmark, Post, PostLike, PostShare, PostView
from app.modules.posts.repository import PostRepository
from app.modules.posts.schemas import PostResponse, SharePostResponse, LikeResponse, BookmarkResponse
from app.modules.posts.service import serialize_post


def get_post_or_404(repo, post_id):
    return domain.require_post(repo.get(post_id))


def _response(repo, post, current_user, *, persist=True):
    if persist:
        repo.flush()
        repo.refresh(post)
    if post.status == "active":
        row = repo.active_row(post.id, current_user.id)
        domain.require_post(row)
        result = serialize_post(row[0], row, current_user.id)
    else:
        result = serialize_post(post, repo.stats(post.id, current_user.id), current_user.id)
    return PostResponse.model_validate(result)


def _sync_tags(repo, post, user, tags):
    if domain.is_admin(user):
        repo.sync_tags(post, tags, create_missing=True)
        post.requested_new_tags = None
    else:
        known, requested = repo.split_tags(tags)
        repo.sync_tags(post, known, create_missing=False)
        post.requested_new_tags = json.dumps(requested, ensure_ascii=False) if requested else None


def create_post(db, current_user, payload):
    with UnitOfWork(db) as uow:
        uow.lock("tags")
        repo = PostRepository(db)
        post = Post(
            user_id=current_user.id, title=payload.title.strip(),
            slug=domain.slugify(payload.title.strip()), content=payload.content.strip(),
            cover_image=payload.cover_image, status=domain.initial_status(current_user),
        )
        repo.add(post)
        repo.flush()
        _sync_tags(repo, post, current_user, payload.tags)
        if not domain.is_admin(current_user):
            notify_admins(
                db, actor_id=current_user.id, notification_type="post_pending",
                title="New post awaiting approval",
                message=f'{current_user.username} submitted "{post.title}" for moderation.', post_id=post.id,
            )
        if post.status == "active":
            notify_followers(
                db, author_id=current_user.id, notification_type="new_post",
                title="New post from someone you follow",
                message=f'{current_user.username} published "{post.title}".', post_id=post.id,
            )
        return _response(repo, post, current_user)


def get_tags(db, current_user):
    return PostRepository(db).tags(ordered=True)


def get_post_detail(db, current_user, post_id):
    repo = PostRepository(db)
    post = get_post_or_404(repo, post_id)
    domain.require_visible(post, current_user)
    return _response(repo, post, current_user, persist=False)


def record_view(db, current_user, post_id):
    with UnitOfWork(db) as uow:
        uow.lock(f"post:{post_id}")
        repo = PostRepository(db)
        post = get_post_or_404(repo, post_id)
        domain.require_visible(post, current_user)
        repo.add(PostView(post_id=post.id, user_id=current_user.id))


def update_post(db, current_user, post_id, payload):
    with UnitOfWork(db) as uow:
        uow.lock(f"post:{post_id}")
        if "tags" in payload.model_fields_set:
            uow.lock("tags")
        repo = PostRepository(db)
        post = get_post_or_404(repo, post_id)
        domain.require_visible(post, current_user)
        data = payload.model_dump(exclude_unset=True)
        domain.apply_update(post, current_user, data)
        if "tags" in data:
            _sync_tags(repo, post, current_user, data["tags"])
        return _response(repo, post, current_user)


def delete_post(db, current_user, post_id):
    with UnitOfWork(db) as uow:
        uow.lock(f"post:{post_id}")
        repo = PostRepository(db)
        post = get_post_or_404(repo, post_id)
        domain.require_visible(post, current_user)
        domain.require_deletable(post, current_user, repo.active_comment_count(post.id))
        if domain.is_admin(current_user) and post.user_id != current_user.id:
            create_notification(
                db, user_id=post.user_id, actor_id=current_user.id, notification_type="post_moderation",
                title="Your post was removed",
                message=f'Your post "{post.title}" was removed by an administrator.', post_id=post.id,
            )
        post.status = "deleted"
        return MessageResponse(message="Post deleted successfully.")


def set_like(db, current_user, post_id, liked=True):
    with UnitOfWork(db) as uow:
        uow.lock(f"post:{post_id}")
        repo = PostRepository(db)
        post = get_post_or_404(repo, post_id)
        domain.require_visible(post, current_user)
        existing = repo.like(post.id, current_user.id)
        if existing and not liked:
            repo.delete(existing)
        if existing or not liked:
            return LikeResponse(liked=liked)
        repo.add(PostLike(post_id=post.id, user_id=current_user.id))
        if post.user_id != current_user.id:
            create_notification(
                db, user_id=post.user_id, actor_id=current_user.id, notification_type="post_like",
                title="Your post was liked", message=f"{current_user.username} liked your post.", post_id=post.id,
            )
        return LikeResponse(liked=True)


def set_bookmark(db, current_user, post_id, bookmarked=True):
    with UnitOfWork(db) as uow:
        uow.lock(f"post:{post_id}")
        repo = PostRepository(db)
        post = get_post_or_404(repo, post_id)
        domain.require_visible(post, current_user)
        existing = repo.bookmark(post_id, current_user.id)
        if existing and not bookmarked:
            repo.delete(existing)
        if existing or not bookmarked:
            return BookmarkResponse(bookmarked=bookmarked)
        repo.add(Bookmark(user_id=current_user.id, post_id=post_id))
        return BookmarkResponse(bookmarked=True)


def share_post(db, current_user, post_id, payload=None):
    with UnitOfWork(db) as uow:
        uow.lock(f"post:{post_id}")
        uow.lock("tags")
        repo = PostRepository(db)
        post = get_post_or_404(repo, post_id)
        domain.require_visible(post, current_user)
        repo.add(PostShare(post_id=post.id, user_id=current_user.id))
        shared_post = domain.make_shared_post(post, current_user, payload.caption if payload else None)
        repo.add(shared_post)
        repo.flush()
        repo.sync_tags(shared_post, [association.tag.name for association in post.tags if association.tag])
        if shared_post.status == "active":
            notify_followers(
                db, author_id=current_user.id, notification_type="new_post",
                title="New post from someone you follow",
                message=f'{current_user.username} shared "{post.title}".', post_id=shared_post.id,
            )
        if post.user_id != current_user.id:
            create_notification(
                db, user_id=post.user_id, actor_id=current_user.id, notification_type="post_share",
                title="Your post was shared", message=f"{current_user.username} shared your post.", post_id=post.id,
            )
        return SharePostResponse(post_id=shared_post.id, original_post_id=post.id)


def report_post(db, current_user, post_id, payload):
    with UnitOfWork(db) as uow:
        uow.lock(f"post:{post_id}")
        repo = PostRepository(db)
        post = get_post_or_404(repo, post_id)
        domain.require_visible(post, current_user)
        if repo.report(post_id, current_user.id):
            raise ApplicationError(status_code=409, detail="You already reported this post.")
        report = Report(
            reporter_id=current_user.id, post_id=post_id, reason=normalize_report_reason(payload.reason),
            details=payload.details.strip() if payload.details else None,
        )
        repo.add(report)
        repo.flush()
        notify_admins(
            db, actor_id=current_user.id, notification_type="post_report", title="New post report",
            message=f"{current_user.username} reported post #{post.id}.", post_id=post.id, report_id=report.id,
        )
        if post.user_id != current_user.id:
            create_notification(
                db, user_id=post.user_id, actor_id=None, notification_type="post_reported",
                title="Your post was reported",
                message=f'Your post "{post.title}" has been reported and is awaiting review.',
                post_id=post.id, report_id=report.id,
            )
        repo.refresh(report)
        return ReportResponse.model_validate(report)
