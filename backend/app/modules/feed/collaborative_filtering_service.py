"""Service Collaborative Filtering - Gợi ý bài viết dựa trên hành vi của những user tương tự

Compatibility exports; implementation lives in domain and repository.
"""

from app.modules.feed.domain import (
    _parse_interest_tags,
    calculate_user_tag_similarity as calculate_tag_similarity,
    calculate_post_overlap,
    calculate_follow_overlap,
)
from app.modules.feed.repository import (
    calculate_user_similarity,
    find_similar_users,
    get_collaborative_recommendations,
    get_personalized_feed,
)
