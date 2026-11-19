"""User-facing profile and follow rules, independent of HTTP and persistence."""

from app.core.exceptions import ApplicationError


def parse_interest_tags(raw_tags: str | None) -> list[str]:
    if not raw_tags:
        return []
    return [tag for item in raw_tags.split(",") if (tag := item.strip())]


def normalize_optional(value: str | None) -> str | None:
    return value.strip() if value and value.strip() else None


def normalize_interest_tags(tags: list[str]) -> str | None:
    normalized = dict.fromkeys(tag.strip().lower() for tag in tags if tag.strip())
    return ",".join(normalized) or None


def can_view_non_active_posts(current_user, profile_user) -> bool:
    return current_user.id == profile_user.id or current_user.role.lower() == "admin"


def may_view_bookmarks(current_user, profile_user) -> bool:
    return current_user.id == profile_user.id


def require_follow_target(current_user, target_user_id: str) -> None:
    if target_user_id == current_user.id:
        raise ApplicationError(status_code=400, detail="You cannot follow yourself.")


def profile_payload(user, current_user, *, followers_count, following_count, posts_count, is_following):
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "avatar_url": user.avatar_url,
        "bio": user.bio,
        "major": user.major,
        "academic_year": user.academic_year,
        "career_goal": user.career_goal,
        "interest_tags": parse_interest_tags(user.interest_tags),
        "followers_count": followers_count,
        "following_count": following_count,
        "posts_count": posts_count,
        "is_following": is_following,
        "is_current_user": current_user.id == user.id,
    }


def follow_response_state(state: str) -> tuple[str, bool]:
    return {
        "already": ("Already following this user.", True),
        "followed": ("Followed user successfully.", True),
        "missing": ("You are not following this user.", False),
        "unfollowed": ("Unfollowed user successfully.", False),
    }[state]
