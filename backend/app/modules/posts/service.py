"""Compatibility API for feed queries and post response serialization."""

import json
from app.modules.posts.models import Post
from app.modules.posts.domain import normalize_tags, slugify
from app.modules.posts.repository import (
    Pagination, build_post_query, paginate_query, paginate_latest_posts_fast,
    paginate_trending_posts_fast, split_known_and_new_tags, sync_post_tags,
)


def serialize_post(post: Post, stats_row, current_user_id: str | None) -> dict:
    cover_image = post.cover_image
    if isinstance(cover_image, str):
        normalized_cover = cover_image.strip().lower()
        if not normalized_cover or normalized_cover.endswith("/images/uit.png"):
            cover_image = None

    requested_new_tags: list[str] = []
    if post.requested_new_tags:
        try:
            parsed = json.loads(post.requested_new_tags)
            if isinstance(parsed, list):
                requested_new_tags = [str(item) for item in parsed if str(item).strip()]
        except Exception:
            requested_new_tags = []

    return {
        "id": post.id,
        "user_id": post.user_id,
        "title": post.title,
        "content": post.content,
        "cover_image": cover_image,
        "status": post.status,
        "original_post_id": post.original_post_id,
        "share_caption": post.share_caption,
        "requested_new_tags": requested_new_tags,
        "tags": [association.tag.name for association in post.tags],
        "created_at": post.created_at,
        "author": post.author,
        "likes_count": int(stats_row.likes_count or 0),
        "comments_count": int(stats_row.comments_count or 0),
        "views_count": int(stats_row.views_count or 0),
        "shares_count": int(stats_row.shares_count or 0),
        "trending_score": int(stats_row.trending_score or 0),
        "is_liked": bool(stats_row.is_liked) if current_user_id else False,
        "is_bookmarked": bool(stats_row.is_bookmarked) if current_user_id else False,
    }
