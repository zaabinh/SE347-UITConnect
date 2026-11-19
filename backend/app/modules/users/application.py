"""User profile, activity, and follow use cases."""

from app.core.exceptions import ApplicationError
from app.db.uow import UnitOfWork
from app.modules.notifications.service import create_notification
from app.modules.users import domain
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import (
    CurrentProfileResponse,
    FollowResponse,
    ProfileResponse,
    UpdateProfileRequest,
    UserCommentResponse,
    UserPostResponse,
)


def _require_user(user):
    if user is None:
        raise ApplicationError(status_code=404, detail="User not found.")
    return user


def _profile(repo, user, current_user):
    return ProfileResponse(**domain.profile_payload(
        user,
        current_user,
        followers_count=repo.followers_count(user.id),
        following_count=repo.following_count(user.id),
        posts_count=repo.posts_count(user.id, domain.can_view_non_active_posts(current_user, user)),
        is_following=repo.is_following(current_user.id, user.id),
    ))


def _current_profile(repo, user):
    profile = _profile(repo, user, user)
    return CurrentProfileResponse(
        email=user.email,
        role=user.role,
        status=user.status,
        created_at=user.created_at,
        **profile.model_dump(),
    )


def get_my_profile(db, current_user):
    return _current_profile(UserRepository(db), current_user)


def update_my_profile(db, current_user, payload: UpdateProfileRequest):
    with UnitOfWork(db):
        repo = UserRepository(db)
        current_user.full_name = payload.full_name.strip()
        current_user.bio = domain.normalize_optional(payload.bio)
        current_user.avatar_url = domain.normalize_optional(payload.avatar_url)
        current_user.major = domain.normalize_optional(payload.major)
        current_user.academic_year = domain.normalize_optional(payload.academic_year)
        current_user.career_goal = domain.normalize_optional(payload.career_goal)
        current_user.interest_tags = domain.normalize_interest_tags(payload.interest_tags)
        repo.add(current_user)
        repo.flush()
        repo.refresh(current_user)
        return _current_profile(repo, current_user)


def get_user_profile(db, current_user, username):
    repo = UserRepository(db)
    user = _require_user(repo.by_username(username))
    return _profile(repo, user, current_user)


def get_user_posts(db, current_user, username):
    repo = UserRepository(db)
    user = _require_user(repo.by_username(username))
    include_non_active = domain.can_view_non_active_posts(current_user, user)
    items = []
    for post in repo.user_posts(user.id, include_non_active):
        display_title = post.title
        normalized_status = (post.status or "").lower()
        if normalized_status == "pending":
            display_title = f"[Chá» duyá»‡t] {display_title}"
        elif normalized_status == "rejected":
            display_title = f"[Tá»« chá»‘i] {display_title}"
        items.append(UserPostResponse(
            id=post.id,
            title=display_title,
            content=post.content,
            cover_image=post.cover_image,
            status=post.status,
            created_at=post.created_at,
        ))
    return items


def get_user_comments(db, current_user, username):
    repo = UserRepository(db)
    user = _require_user(repo.by_username(username))
    # Access still requires a verified active user; comments remain public by username.
    _ = current_user.id
    return [
        UserCommentResponse(
            id=comment.id,
            post_id=comment.post_id,
            post_title=post_title,
            content=comment.content,
            created_at=comment.created_at,
        )
        for comment, post_title in repo.user_comments(user.id)
    ]


def get_user_bookmarks(db, current_user, username):
    repo = UserRepository(db)
    user = _require_user(repo.by_username(username))
    if not domain.may_view_bookmarks(current_user, user):
        raise ApplicationError(status_code=403, detail="You can only view your own bookmarks.")
    return repo.user_bookmarks(user.id)


def follow_user(db, current_user, user_id):
    with UnitOfWork(db):
        domain.require_follow_target(current_user, user_id)
        repo = UserRepository(db)
        target_user = _require_user(repo.by_id(user_id))
        if repo.follow(current_user.id, user_id):
            message, following = domain.follow_response_state("already")
            return FollowResponse(message=message, following=following)
        repo.add_follow(current_user.id, user_id)
        create_notification(
            db,
            user_id=target_user.id,
            actor_id=current_user.id,
            notification_type="follow",
            title="You have a new follower",
            message=f"{current_user.username} started following you.",
        )
        message, following = domain.follow_response_state("followed")
        return FollowResponse(message=message, following=following)


def unfollow_user(db, current_user, user_id):
    with UnitOfWork(db):
        repo = UserRepository(db)
        follow = repo.follow(current_user.id, user_id)
        if not follow:
            message, following = domain.follow_response_state("missing")
            return FollowResponse(message=message, following=following)
        repo.delete(follow)
        message, following = domain.follow_response_state("unfollowed")
        return FollowResponse(message=message, following=following)
