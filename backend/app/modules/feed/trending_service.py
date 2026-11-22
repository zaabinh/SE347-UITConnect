"""Service để gợi ý bài viết theo xu hướng

Compatibility exports; implementation lives in domain and repository.
"""

from app.modules.feed.domain import (
    calculate_time_decay,
    calculate_trending_score,
    get_trending_reason,
    preprocess_text,
    calculate_tag_similarity,
    calculate_text_similarity,
    calculate_content_similarity,
)
from app.modules.feed.repository import (
    get_trending_posts,
    get_trending_tags,
    get_similar_posts,
)
