"""Post policy and content rules, independent of HTTP and persistence."""

import re
import unicodedata

from app.core.exceptions import ApplicationError
from app.modules.posts.models import Post


def slugify(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value.strip().lower()).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9\s-]", "", ascii_value)
    return re.sub(r"\s+", "-", normalized).strip("-") or "post"


def normalize_tags(raw_tags: list[str] | None) -> list[str]:
    return list(dict.fromkeys(tag.strip().lower() for tag in raw_tags or [] if tag.strip()))


def is_admin(user) -> bool:
    return user.role.lower() == "admin"


def initial_status(user) -> str:
    return "active" if is_admin(user) else "pending"


def require_post(post):
    if post is None:
        raise ApplicationError(status_code=404, detail="Post not found.")
    return post


def require_visible(post, user) -> None:
    if post.status != "active" and post.user_id != user.id and not is_admin(user):
        raise ApplicationError(status_code=403, detail="Post is awaiting moderation.")


def require_owner(post, user) -> None:
    if post.user_id != user.id:
        raise ApplicationError(status_code=403, detail="Not allowed")


def require_deletable(post, user, active_comments: int) -> None:
    if post.user_id != user.id and not is_admin(user):
        raise ApplicationError(status_code=403, detail="Not authorized to delete this post.")
    if active_comments and not is_admin(user):
        raise ApplicationError(status_code=400, detail="Cannot delete a post that already has comments.")


def apply_update(post, user, data: dict) -> None:
    require_owner(post, user)
    if data.get("title"):
        post.title = data["title"].strip()
        post.slug = slugify(post.title)
    if data.get("content") is not None:
        post.content = data["content"].strip()
    if "cover_image" in data:
        post.cover_image = data["cover_image"]
    if "status" in data and is_admin(user):
        post.status = data["status"]
    elif not is_admin(user):
        post.status = "pending"


def make_shared_post(post, user, caption: str | None) -> Post:
    caption = caption.strip() if caption else None
    title = f"Shared: {post.title}"
    attribution = f"Shared from @{post.author.username or post.author.id} • Original post #{post.id}"
    content = f"{attribution}\n\n{post.content}"
    if caption:
        content = f"{caption}\n\n{content}"
    return Post(
        user_id=user.id, title=title,
        slug=slugify(f"share-{post.id}-{user.id}-{title}")[:255],
        content=content, cover_image=post.cover_image, status=initial_status(user),
        original_post_id=post.id, share_caption=caption,
    )
