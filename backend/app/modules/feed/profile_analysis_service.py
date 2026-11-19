"""Service phân tích Profile User và gợi ý bài viết liên quan.
Gợi ý dựa trên:
1. Interest tags (quan tâm)
2. Major (chuyên ngành)
3. Academic year (năm học)
4. Career goal (mục tiêu)
5. Bio (tiểu sử)

Compatibility exports; implementation lives in domain and repository.
"""

from app.modules.feed.domain import (
    _parse_tags_from_string,
    _extract_keywords_from_text,
    calculate_profile_relevance_score,
)
from app.modules.feed.repository import (
    analyze_user_profile,
    get_profile_based_recommendations,
    get_user_profile_summary,
)
