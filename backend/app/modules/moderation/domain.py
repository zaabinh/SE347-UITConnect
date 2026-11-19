"""Moderation policies and state transitions, independent of transport and storage."""

import json
from datetime import UTC, datetime

from app.core.exceptions import ApplicationError


STANDARD_REPORT_REASONS = {
    "spam": "spam", "scam": "spam", "harassment": "harassment", "abuse": "harassment",
    "hate_speech": "hate_speech", "hate": "hate_speech", "violence": "violence",
    "misinformation": "misinformation", "fake_news": "misinformation", "other": "other",
}


def normalize_report_reason(reason: str) -> str:
    return STANDARD_REPORT_REASONS.get(reason.strip().lower(), "other")


def require_found(entity, detail: str):
    if entity is None:
        raise ApplicationError(404, detail)
    return entity


def ban_user(target_user, current_user) -> None:
    require_live_user(target_user)
    if target_user.id == current_user.id:
        raise ApplicationError(400, "Admin cannot ban themselves.")
    if (target_user.role or "").lower() == "admin":
        raise ApplicationError(400, "Admin accounts cannot be banned.")
    target_user.status = "banned"


def restore_user(user) -> None:
    require_live_user(user)
    user.status = "active"


def require_live_user(user) -> None:
    if user.status == "deleted":
        raise ApplicationError(404, "User not found.")


def validate_report_action(report, status: str, action: str) -> None:
    if status in {"dismissed", "reviewed", "pending"} and action != "none":
        raise ApplicationError(400, "Only resolved reports can apply moderation actions.")
    if status == "resolved" and action == "none":
        raise ApplicationError(400, "Resolved reports must include a moderation action.")
    if report.comment_id and action in {"hide_post", "hide_post_and_ban_author"}:
        raise ApplicationError(400, "Comment reports cannot use post-only actions.")
    if not report.comment_id and action in {"hide_comment", "hide_comment_and_ban_author"}:
        raise ApplicationError(400, "Post reports cannot use comment-only actions.")


def require_post_target(report) -> int:
    if not report.post_id:
        raise ApplicationError(400, "This report does not target a post.")
    return report.post_id


def require_comment_target(report) -> int:
    if not report.comment_id:
        raise ApplicationError(400, "This report does not target a comment.")
    return report.comment_id


def require_target_author(user_id: str | None) -> str:
    if not user_id:
        raise ApplicationError(400, "Report has no target author to ban.")
    return user_id


def hide_post(post) -> None:
    if post.status == "deleted":
        raise ApplicationError(404, "Reported post not found.")
    post.status = "rejected"


def hide_comment(comment) -> None:
    comment.status = "hidden"


def review_report(report, status: str, reviewer_id: str) -> None:
    report.status = status
    report.reviewed_by = reviewer_id
    report.reviewed_at = datetime.now(UTC).replace(tzinfo=None)


def parse_requested_new_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item).strip().lower() for item in parsed if str(item).strip()]
    except (ValueError, TypeError):
        pass
    return []


def approve_post(post) -> None:
    post.requested_new_tags = None
    post.status = "active"


def reject_post(post) -> None:
    post.status = "rejected"
    post.requested_new_tags = None


def ensure_new_tag(existing) -> None:
    if existing is not None:
        raise ApplicationError(400, "Tag already exists.")
