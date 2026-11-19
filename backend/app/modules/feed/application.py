"""Read use cases and response assembly for feed endpoints."""

from datetime import datetime
from app.modules.feed.schemas import (
    TrendingPostResponse, SimilarPostResponse, CollaborativePostResponse,
    ProfileBasedPostResponse, UserProfileSummary, ProfileAnalysisResponse,
)
from app.modules.posts.service import serialize_post
from app.modules.feed.repository import (
    get_feed_rows, get_trending_posts, get_trending_tags, get_similar_posts,
    get_collaborative_recommendations, get_profile_based_recommendations, get_user_profile_summary,
)


def get_posts_feed(db, current_user, page=1, page_size=10, search=None, tag=None, mode='for-you', sort='latest'):
    current_user_id = current_user.id if current_user else None
    rows, pagination, use_fast_path = get_feed_rows(
        db, current_user_id, search, tag, mode, sort, page, page_size,
    )

    if use_fast_path:
        items = [serialize_post(row[0], row[1], current_user_id) for row in rows]
    else:
        items = [serialize_post(row[0], row, current_user_id) for row in rows]
    return {
        "items": items,
        "meta": {
            "page": pagination.page,
            "page_size": pagination.page_size,
            "total": pagination.total,
            "total_pages": pagination.total_pages,
        },
    }



def get_trending_suggestions(db, current_user, page=1, page_size=10, hours=24, tag=None):
    """
    Lấy danh sách bài viết gợi ý theo xu hướng.

    - **page**: Trang hiện tại (mặc định 1)
    - **page_size**: Số bài mỗi trang (mặc định 10, tối đa 50)
    - **hours**: Lấy bài viết trong bao nhiêu giờ qua (mặc định 24, tối đa 168)
    - **tag**: Lọc theo tag cụ thể (nếu có)

    Ví dụ:
    - GET /posts/trending/suggestions → Top 10 trending posts 24h
    - GET /posts/trending/suggestions?hours=7&page_size=20 → Top 20 trending posts 7 ngày
    - GET /posts/trending/suggestions?tag=python → Trending posts về Python
    """
    current_user_id = current_user.id if current_user else None

    posts_with_scores, pagination = get_trending_posts(
        db=db,
        current_user_id=current_user_id,
        page=page,
        page_size=page_size,
        hours=hours,
        tag_filter=tag,
        user_personalize=True
    )

    items = []
    for idx, post_data in enumerate(posts_with_scores, start=1):
        post = post_data["post"]

        # Tạo stats object
        stats = type("Stats", (), {
            "likes_count": post_data["likes"],
            "comments_count": post_data["comments"],
            "views_count": post_data["views"],
            "shares_count": post_data["shares"],
            "trending_score": int(post_data["score"]),
            "is_liked": post_data["is_liked"],
            "is_bookmarked": post_data["is_bookmarked"]
        })()

        # Serialize post
        post_response = serialize_post(post, stats, current_user_id)

        # Tạo trending response
        trending_response = TrendingPostResponse(
            post=post_response,
            trend_rank=(page - 1) * page_size + idx,
            hot_score=post_data["score"],
            trending_reason=post_data["reason"]
        )
        items.append(trending_response)

    return {
        "items": items,
        "meta": {
            "page": pagination.page,
            "page_size": pagination.page_size,
            "total": pagination.total,
            "total_pages": pagination.total_pages,
        },
    }



def get_trending_tags_endpoint(db, current_user, limit=10, hours=24):
    """
    Lấy danh sách tag đang xu hướng.

    - **limit**: Số tag trả về (mặc định 10, tối đa 50)
    - **hours**: Xem xét bài viết trong bao nhiêu giờ qua (mặc định 24)

    Ví dụ:
    - GET /posts/trending/tags → Top 10 trending tags
    - GET /posts/trending/tags?limit=20&hours=7 → Top 20 tags trong 7 ngày
    """
    _ = current_user  # Đảm bảo user đã xác thực

    trending_tags = get_trending_tags(db, limit=limit, hours=hours)

    return {
        "items": trending_tags,
        "updated_at": datetime.utcnow().isoformat()
    }



def get_similar_posts_endpoint(db, current_user, post_id, limit=5, min_similarity=0.1):
    """
    Lấy danh sách bài viết tương tự dựa trên nội dung (Content-Based Filtering).

    Thuật toán:
    - So sánh tiêu đề, nội dung, và tags
    - Sử dụng TF (Term Frequency) và Cosine Similarity
    - Weighted: title(20%) + content(40%) + tags(40%)

    Parameters:
    - **post_id**: ID bài viết tham chiếu (bắt buộc)
    - **limit**: Số bài tương tự trả về (mặc định 5, tối đa 20)
    - **min_similarity**: Điểm tương đồng tối thiểu (mặc định 0.1, từ 0 tới 1)

    Ví dụ:
    - GET /posts/1/similar → 5 bài tương tự bài #1
    - GET /posts/1/similar?limit=10&min_similarity=0.2 → 10 bài có tương đồng ≥ 0.2
    """
    similar_posts_data = get_similar_posts(
        db=db,
        post_id=post_id,
        current_user_id=current_user.id,
        limit=limit,
        min_similarity=min_similarity
    )

    items = []
    for item in similar_posts_data:
        post = item["post"]
        post_response = serialize_post(post, item["stats"], current_user.id)

        similar_response = SimilarPostResponse(
            post=post_response,
            similarity_score=round(item["similarity"], 3),
            similarity_reason=item["reason"]
        )
        items.append(similar_response)

    return {
        "items": items,
        "meta": {
            "page": 1,
            "page_size": len(items),
            "total": len(items),
            "total_pages": 1,
        },
    }



def get_collaborative_recommendations_endpoint(db, current_user, page=1, page_size=10, min_similarity=0.2, days_back=30):
    """
    Lấy gợi ý bài viết dựa trên Collaborative Filtering (User-Based).

    Thuật toán:
    1. Tìm những user có sở thích giống bạn dựa trên:
       - Interest tags (30%)
       - Bài viết yêu thích (35%)
       - Những user đang theo dõi (25%)
       - Bài viết đã comment (10%)

    2. Lấy những bài mà những user này yêu thích
    3. Gợi ý những bài bạn chưa thích/xem

    Parameters:
    - **page**: Trang hiện tại (mặc định 1)
    - **page_size**: Bài mỗi trang (mặc định 10, tối đa 50)
    - **min_similarity**: Điểm tương đồng tối thiểu (mặc định 0.2, từ 0 tới 1)
    - **days_back**: Xem xét bài viết trong bao nhiêu ngày (mặc định 30, tối đa 365)

    Ví dụ:
    - GET /posts/recommendations/collaborative → Top 10 gợi ý
    - GET /posts/recommendations/collaborative?page_size=20&days_back=7 → 20 bài trong 7 ngày
    - GET /posts/recommendations/collaborative?min_similarity=0.3 → Chỉ những user rất tương tự
    """
    collab_posts, pagination = get_collaborative_recommendations(
        db=db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        min_similarity=min_similarity,
        days_back=days_back
    )

    items = []
    for item in collab_posts:
        post = item["post"]
        post_response = serialize_post(post, item["stats"], current_user.id)

        collab_response = CollaborativePostResponse(
            post=post_response,
            cf_score=round(item["cf_score"], 3),
            cf_reason=item["reason"],
            similar_user_count=0  # TODO: Thêm vào service
        )
        items.append(collab_response)

    return {
        "items": items,
        "meta": {
            "page": pagination.page,
            "page_size": pagination.page_size,
            "total": pagination.total,
            "total_pages": pagination.total_pages,
        },
    }



def get_profile_recommendations_endpoint(db, current_user, page=1, page_size=10, min_score=0.1, days_back=30):
    """
    Lấy gợi ý bài viết dựa trên thông tin Profile của user.

    Phân tích dựa trên:
    1. Interest tags (30%)
    2. Keywords từ major, career goal, bio (40%)
    3. Hành vi (like/comment history) (30%)

    Parameters:
    - **page**: Trang hiện tại (mặc định 1)
    - **page_size**: Bài mỗi trang (mặc định 10, tối đa 50)
    - **min_score**: Điểm liên quan tối thiểu (mặc định 0.1, từ 0 tới 1)
    - **days_back**: Bài viết trong bao nhiêu ngày (mặc định 30, tối đa 365)

    Ví dụ:
    - GET /posts/recommendations/profile → Gợi ý mặc định
    - GET /posts/recommendations/profile?page_size=20 → 20 bài
    - GET /posts/recommendations/profile?min_score=0.3&days_back=7 → Chỉ bài liên quan cao trong 7 ngày
    """
    profile_posts, pagination = get_profile_based_recommendations(
        db=db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        min_score=min_score,
        days_back=days_back
    )

    items = []
    for item in profile_posts:
        post = item["post"]
        post_response = serialize_post(post, item["stats"], current_user.id)

        profile_response = ProfileBasedPostResponse(
            post=post_response,
            profile_score=round(item["profile_score"], 3),
            recommendation_reason=item["reason"]
        )
        items.append(profile_response)

    return {
        "items": items,
        "meta": {
            "page": pagination.page,
            "page_size": pagination.page_size,
            "total": pagination.total,
            "total_pages": pagination.total_pages,
        },
    }



def get_profile_summary_endpoint(db, current_user):
    """
    Lấy tóm tắt profile của user hiện tại.

    Trả về:
    - Interest tags
    - Major (chuyên ngành)
    - Academic year (năm học)
    - Career goal (mục tiêu sự nghiệp)
    - Profile strength (độ đầy đủ: 0-1)
    - Recommendations count (số bài có thể gợi ý)

    Ví dụ:
    - GET /posts/profile/summary → Tóm tắt profile
    """
    profile_summary = get_user_profile_summary(db, current_user.id)

    if not profile_summary:
        profile_summary = {
            "interest_tags": [],
            "major": "",
            "academic_year": "",
            "career_goal": "",
            "profile_strength": 0.0,
            "recommendations_count": 0,
            "profile_completeness": {}
        }

    return profile_summary



def get_profile_analysis_endpoint(db, current_user):
    """
    Phân tích chi tiết profile của user và đưa ra message gợi ý.

    Phân tích bao gồm:
    - Độ đầy đủ thông tin profile
    - Các lĩnh vực quan tâm
    - Mục tiêu sự nghiệp
    - Khuyến nghị về cải thiện profile

    Ví dụ:
    - GET /posts/profile/analysis → Phân tích profile
    """
    profile_summary = get_user_profile_summary(db, current_user.id)

    if not profile_summary:
        profile_summary = {
            "interest_tags": [],
            "major": "",
            "academic_year": "",
            "career_goal": "",
            "profile_strength": 0.0,
            "recommendations_count": 0,
            "profile_completeness": {}
        }

    # Tạo message khuyến nghị
    completeness = profile_summary.get("profile_completeness", {})
    missing_fields = []

    if not completeness.get("has_interest_tags"):
        missing_fields.append("sở thích")
    if not completeness.get("has_major"):
        missing_fields.append("chuyên ngành")
    if not completeness.get("has_career_goal"):
        missing_fields.append("mục tiêu sự nghiệp")

    if missing_fields:
        recommendation_message = f"Hoàn thành profile bằng cách cập nhật: {', '.join(missing_fields)} để nhận được gợi ý chính xác hơn."
    else:
        recommendation_message = "Profile của bạn đầy đủ! Chúng tôi sẽ gợi ý những bài viết phù hợp nhất."

    return ProfileAnalysisResponse(
        user_id=current_user.id,
        profile_summary=UserProfileSummary(**profile_summary),
        recommendation_message=recommendation_message
    )



