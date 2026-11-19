from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.modules.auth.dependencies import require_active_verified_user
from app.modules.users.models import User
from app.modules.posts.schemas import PostListResponse
from app.modules.feed.schemas import (
    TrendingPostListResponse, TrendingTagListResponse, SimilarPostListResponse,
    CollaborativePostListResponse, ProfileBasedPostListResponse,
    UserProfileSummary, ProfileAnalysisResponse,
)
from app.modules.feed import application


router = APIRouter(tags=['Discovery'])


@router.get("/feed", response_model=PostListResponse, operation_id="feed_list")
def get_posts_feed(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    search: str | None = None,
    tag: str | None = None,
    mode: str = Query(default="for-you", pattern="^(for-you|following|trending)$"),
    sort: str = Query(default="latest", pattern="^(latest|trending|most-liked|most-commented)$"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(require_active_verified_user),
):
    return application.get_posts_feed(
        page=page,
        page_size=page_size,
        search=search,
        tag=tag,
        mode=mode,
        sort=sort,
        db=db,
        current_user=current_user,
    )


@router.get("/recommendations/trending", response_model=TrendingPostListResponse, operation_id="recommendations_list_trending")
def get_trending_suggestions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    hours: int = Query(default=24, ge=1, le=168),
    tag: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(require_active_verified_user),
):
    """
    Lấy danh sách bài viết gợi ý theo xu hướng.

    - **page**: Trang hiện tại (mặc định 1)
    - **page_size**: Số bài mỗi trang (mặc định 10, tối đa 50)
    - **hours**: Lấy bài viết trong bao nhiêu giờ qua (mặc định 24, tối đa 168)
    - **tag**: Lọc theo tag cụ thể (nếu có)

    Ví dụ:
    - GET /api/v1/recommendations/trending → Top 10 trending posts 24h
    - GET /api/v1/recommendations/trending?hours=7&page_size=20 → Top 20 trending posts 7 ngày
    - GET /api/v1/recommendations/trending?tag=python → Trending posts về Python
    """
    return application.get_trending_suggestions(
        page=page,
        page_size=page_size,
        hours=hours,
        tag=tag,
        db=db,
        current_user=current_user,
    )


@router.get("/tags/trending", response_model=TrendingTagListResponse, operation_id="recommendations_list_trending_tags")
def get_trending_tags_endpoint(
    limit: int = Query(default=10, ge=1, le=50),
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(require_active_verified_user),
):
    """
    Lấy danh sách tag đang xu hướng.

    - **limit**: Số tag trả về (mặc định 10, tối đa 50)
    - **hours**: Xem xét bài viết trong bao nhiêu giờ qua (mặc định 24)

    Ví dụ:
    - GET /api/v1/tags/trending → Top 10 trending tags
    - GET /api/v1/tags/trending?limit=20&hours=7 → Top 20 tags trong 7 ngày
    """
    return application.get_trending_tags_endpoint(
        limit=limit,
        hours=hours,
        db=db,
        current_user=current_user,
    )


@router.get("/recommendations/posts/{post_id}/similar", response_model=SimilarPostListResponse, operation_id="recommendations_list_similar")
def get_similar_posts_endpoint(
    post_id: int,
    limit: int = Query(default=5, ge=1, le=20),
    min_similarity: float = Query(default=0.1, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_verified_user),
):
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
    - GET /api/v1/recommendations/posts/1/similar → 5 bài tương tự bài #1
    - GET /api/v1/recommendations/posts/1/similar?limit=10&min_similarity=0.2 → 10 bài có tương đồng ≥ 0.2
    """
    return application.get_similar_posts_endpoint(
        post_id=post_id,
        limit=limit,
        min_similarity=min_similarity,
        db=db,
        current_user=current_user,
    )


@router.get("/recommendations/collaborative", response_model=CollaborativePostListResponse, operation_id="recommendations_list_collaborative")
def get_collaborative_recommendations_endpoint(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    min_similarity: float = Query(default=0.2, ge=0.0, le=1.0),
    days_back: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_verified_user),
):
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
    - GET /api/v1/recommendations/collaborative → Top 10 gợi ý
    - GET /api/v1/recommendations/collaborative?page_size=20&days_back=7 → 20 bài trong 7 ngày
    - GET /api/v1/recommendations/collaborative?min_similarity=0.3 → Chỉ những user rất tương tự
    """
    return application.get_collaborative_recommendations_endpoint(
        page=page,
        page_size=page_size,
        min_similarity=min_similarity,
        days_back=days_back,
        db=db,
        current_user=current_user,
    )


@router.get("/recommendations/profile", response_model=ProfileBasedPostListResponse, operation_id="recommendations_list_profile")
def get_profile_recommendations_endpoint(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    min_score: float = Query(default=0.1, ge=0.0, le=1.0),
    days_back: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_verified_user),
):
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
    - GET /api/v1/recommendations/profile → Gợi ý mặc định
    - GET /api/v1/recommendations/profile?page_size=20 → 20 bài
    - GET /api/v1/recommendations/profile?min_score=0.3&days_back=7 → Chỉ bài liên quan cao trong 7 ngày
    """
    return application.get_profile_recommendations_endpoint(
        page=page,
        page_size=page_size,
        min_score=min_score,
        days_back=days_back,
        db=db,
        current_user=current_user,
    )


@router.get("/recommendations/profile-summary", response_model=UserProfileSummary, operation_id="recommendations_get_profile_summary")
def get_profile_summary_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_verified_user),
):
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
    - GET /api/v1/recommendations/profile-summary → Tóm tắt profile
    """
    return application.get_profile_summary_endpoint(
        db=db,
        current_user=current_user,
    )


@router.get("/recommendations/profile-analysis", response_model=ProfileAnalysisResponse, operation_id="recommendations_get_profile_analysis")
def get_profile_analysis_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_verified_user),
):
    """
    Phân tích chi tiết profile của user và đưa ra message gợi ý.

    Phân tích bao gồm:
    - Độ đầy đủ thông tin profile
    - Các lĩnh vực quan tâm
    - Mục tiêu sự nghiệp
    - Khuyến nghị về cải thiện profile

    Ví dụ:
    - GET /api/v1/recommendations/profile-analysis → Phân tích profile
    """
    return application.get_profile_analysis_endpoint(
        db=db,
        current_user=current_user,
    )
