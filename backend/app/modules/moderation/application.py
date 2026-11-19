"""Admin use cases coordinate policies and persistence in one transaction."""

from datetime import UTC, datetime, timedelta
import re

from app.core.exceptions import ApplicationError
from app.db.uow import UnitOfWork
from app.modules.moderation import domain
from app.modules.moderation.repository import ModerationRepository
from app.modules.notifications.service import create_notification, notify_followers
from app.modules.posts.service import slugify


def _page(items, total, page, page_size):
    return {
        "items": items,
        "meta": {"page": page, "page_size": page_size, "total": total,
                 "total_pages": (total + page_size - 1) // page_size},
    }


def list_users(db, page, page_size, search, status_filter, sort_by, sort_order):
    rows, total = ModerationRepository(db).list_users(page, page_size, search, status_filter, sort_by, sort_order)
    return _page(rows, total, page, page_size)


def list_reports(db, page, page_size, status_filter, reason):
    rows, total = ModerationRepository(db).list_reports(page, page_size, status_filter, reason)
    return _page(rows, total, page, page_size)


def list_pending_posts(db, page, page_size):
    rows, total = ModerationRepository(db).pending_posts(page, page_size)
    items = [
        {"id": row.id, "user_id": row.user_id, "title": row.title, "status": row.status,
         "requested_new_tags": domain.parse_requested_new_tags(row.requested_new_tags), "created_at": row.created_at}
        for row in rows
    ]
    return _page(items, total, page, page_size)


def list_tags(db):
    return ModerationRepository(db).list_tags()


def analytics_overview(db):
    now = datetime.now(UTC).replace(tzinfo=None)
    return ModerationRepository(db).analytics(now - timedelta(days=1), now - timedelta(days=7))


def ban_user(db, current_user, user_id, reason):
    repo = ModerationRepository(db)
    with UnitOfWork(db) as uow:
        uow.lock(f"user:{user_id}")
        user = domain.require_found(repo.user(user_id), "User not found.")
        domain.require_live_user(user)
        if user.status == "banned":
            return user
        domain.ban_user(user, current_user)
        repo.add_audit_log(current_user.id, "ban_user", "user", user_id, reason)
        create_notification(
            db, user_id=user.id, actor_id=current_user.id, notification_type="account_status",
            title="Your account has been banned", message="An administrator has restricted access to your account.",
        )
        repo.flush()
        repo.refresh(user)
    return user


def unban_user(db, current_user, user_id, reason):
    repo = ModerationRepository(db)
    with UnitOfWork(db) as uow:
        uow.lock(f"user:{user_id}")
        user = domain.require_found(repo.user(user_id), "User not found.")
        domain.require_live_user(user)
        if user.status == "active":
            return user
        domain.restore_user(user)
        repo.add_audit_log(current_user.id, "unban_user", "user", user_id, reason)
        create_notification(
            db, user_id=user.id, actor_id=current_user.id, notification_type="account_status",
            title="Your account has been restored", message="An administrator restored your access.",
        )
        repo.flush()
        repo.refresh(user)
    return user


def _ban_author(db, repo, target_user, current_user, report):
    domain.require_live_user(target_user)
    if target_user.status == "banned":
        return
    domain.ban_user(target_user, current_user)
    repo.add_audit_log(current_user.id, "ban_user", "user", target_user.id,
                       f"report_id={report.id}; reason={report.reason}")
    create_notification(
        db, user_id=target_user.id, actor_id=current_user.id, notification_type="account_status",
        title="Your account has been banned",
        message="An administrator has restricted access to your account after a moderation review.",
    )


def moderate_report(db, current_user, report_id, payload):
    repo = ModerationRepository(db)
    with UnitOfWork(db) as uow:
        uow.lock(f"report:{report_id}")
        report = domain.require_found(repo.report(report_id), "Report not found.")
        if report.post_id:
            uow.lock(f"post:{report.post_id}")
        action = payload.action or "none"
        if report.status != "pending":
            previous = repo.latest_report_audit(report_id)
            match = re.search(r"(?:^|; )action=([^;]+)", previous.notes or "") if previous else None
            previous_action = match.group(1) if match else ("none" if report.status != "resolved" else None)
            if report.status == payload.status and previous_action == action:
                return report
            raise ApplicationError(409, "Report has already been moderated.", "REPORT_ALREADY_MODERATED")
        domain.validate_report_action(report, payload.status, action)
        action_notes = []
        if payload.status == "resolved":
            if action in {"hide_post", "hide_post_and_ban_author"}:
                post = domain.require_found(repo.post(domain.require_post_target(report)), "Reported post not found.")
                domain.hide_post(post)
                action_notes.append(f"post_hidden={post.id}")
                if post.user_id != current_user.id:
                    create_notification(
                        db, user_id=post.user_id, actor_id=current_user.id, notification_type="post_moderation",
                        title="Your post was hidden", message=f"Post #{post.id} was hidden after a moderation review.",
                        post_id=post.id, report_id=report.id,
                    )
            if action in {"hide_comment", "hide_comment_and_ban_author"}:
                comment = domain.require_found(repo.comment(domain.require_comment_target(report)), "Reported comment not found.")
                domain.hide_comment(comment)
                action_notes.append(f"comment_hidden={comment.id}")
                if comment.user_id != current_user.id:
                    create_notification(
                        db, user_id=comment.user_id, actor_id=current_user.id, notification_type="comment_moderation",
                        title="Your comment was hidden", message=f"Comment #{comment.id} was hidden after a moderation review.",
                        post_id=comment.post_id, comment_id=comment.id, report_id=report.id,
                    )
            if action in {"ban_author", "hide_post_and_ban_author", "hide_comment_and_ban_author"}:
                target_user_id = None
                if report.comment_id:
                    comment = domain.require_found(repo.comment(report.comment_id), "Reported comment not found.")
                    target_user_id = comment.user_id
                elif report.post_id:
                    post = domain.require_found(repo.post(report.post_id), "Reported post not found.")
                    target_user_id = post.user_id
                target_user_id = domain.require_target_author(target_user_id)
                uow.lock(f"user:{target_user_id}")
                target_user = domain.require_found(repo.user(target_user_id), "Target author not found.")
                _ban_author(db, repo, target_user, current_user, report)
                action_notes.append(f"author_banned={target_user.id}")
        domain.review_report(report, payload.status, current_user.id)
        notes = [f"status={payload.status}", f"action={action}", *action_notes]
        if payload.notes:
            notes.append(f"notes={payload.notes}")
        repo.add_audit_log(current_user.id, "moderate_report", "report", str(report.id), "; ".join(notes))
        if report.reporter_id:
            create_notification(
                db, user_id=report.reporter_id, actor_id=current_user.id, notification_type="report_update",
                title="Your report has been reviewed", message=f"Report #{report.id} was marked as {payload.status}.",
                report_id=report.id,
            )
        repo.flush()
        repo.refresh(report)
    return report


def _post_response(post):
    return {"id": post.id, "user_id": post.user_id, "title": post.title, "status": post.status,
            "requested_new_tags": domain.parse_requested_new_tags(post.requested_new_tags),
            "created_at": post.created_at}


def moderate_post(db, current_user, post_id, status):
    repo = ModerationRepository(db)
    with UnitOfWork(db) as uow:
        uow.lock(f"post:{post_id}")
        post = domain.require_found(repo.post(post_id), "Post not found.")
        if post.status == "deleted":
            raise ApplicationError(404, "Post not found.")
        if post.status == status:
            return _post_response(post)
        if post.status != "pending":
            raise ApplicationError(409, "Post has already been moderated.", "POST_ALREADY_MODERATED")
        if status == "rejected":
            _reject_post(db, repo, current_user, post)
        else:
            uow.lock("tags")
            _approve_post(db, repo, current_user, post)
        repo.flush()
        return _post_response(post)


def approve_post(db, current_user, post_id):
    return moderate_post(db, current_user, post_id, "active")


def reject_post(db, current_user, post_id):
    return moderate_post(db, current_user, post_id, "rejected")


def _approve_post(db, repo, current_user, post):
    approved_tags = []
    for name in domain.parse_requested_new_tags(post.requested_new_tags):
        slug = slugify(name)
        tag = repo.tag_by_name_or_slug(name, slug)
        if not tag:
            tag = repo.add_tag(name, slug)
        approved_tags.append(tag.name)
        repo.link_tag(post, tag)
    domain.approve_post(post)
    notes = f"approved_new_tags={','.join(approved_tags)}" if approved_tags else None
    repo.add_audit_log(current_user.id, "approve_post", "post", str(post.id), notes)
    if post.user_id != current_user.id:
        create_notification(
            db, user_id=post.user_id, actor_id=current_user.id, notification_type="post_approved",
            title="Your post was approved", message=f'Your post "{post.title}" is now visible in the feed.',
            post_id=post.id,
        )
    notify_followers(
        db, author_id=post.user_id, notification_type="new_post",
        title="New post from someone you follow",
        message=f'{post.author.username if post.author else "A user"} published "{post.title}".',
        post_id=post.id,
    )


def _reject_post(db, repo, current_user, post):
    domain.reject_post(post)
    repo.add_audit_log(current_user.id, "reject_post", "post", str(post.id))
    if post.user_id != current_user.id:
        create_notification(
            db, user_id=post.user_id, actor_id=current_user.id, notification_type="post_rejected",
            title="Your post was not approved", message=f'Your post "{post.title}" was rejected by moderation.',
            post_id=post.id,
        )


def create_tag(db, payload):
    repo = ModerationRepository(db)
    with UnitOfWork(db) as uow:
        uow.lock("tags")
        name, slug = payload.name.strip().lower(), slugify(payload.name)
        domain.ensure_new_tag(repo.tag_by_name_or_slug(name, slug))
        tag = repo.add_tag(name, slug)
        repo.refresh(tag)
    return tag


def update_tag(db, tag_id, payload):
    repo = ModerationRepository(db)
    with UnitOfWork(db) as uow:
        uow.lock("tags")
        tag = domain.require_found(repo.tag(tag_id), "Tag not found.")
        duplicate = repo.tag_by_name_or_slug(payload.name.strip().lower(), slugify(payload.name))
        if duplicate is not None and duplicate.id != tag.id:
            raise ApplicationError(409, "Tag already exists.")
        tag.name = payload.name.strip().lower()
        tag.slug = slugify(payload.name)
        repo.flush()
        repo.refresh(tag)
    return tag


def delete_tag(db, tag_id):
    repo = ModerationRepository(db)
    with UnitOfWork(db) as uow:
        uow.lock("tags")
        tag = domain.require_found(repo.tag(tag_id), "Tag not found.")
        repo.delete(tag)
