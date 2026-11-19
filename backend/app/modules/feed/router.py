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
    """List active posts created within the last `hours`, ranked by engagement and age.

    The optional `tag` matches part of a tag name, case-insensitively.
    Ranking precedes offset pagination; equal scores use descending post IDs.
    `hours=7` selects the last seven hours.
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
    """List tags on active posts created within the last `hours`.

    Tags are ranked by the sum of each post's weighted likes, comments and views.
    Equal scores use descending tag IDs. `hours=7` selects the last seven hours.
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
    """List active posts with content similar to an active reference post.

    Similarity compares title, content and tags. Results meeting `min_similarity`
    are ranked by similarity, then descending post ID, and limited by `limit`.
    A missing or non-active reference post returns an empty list with zero pages.
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
    """List active posts ranked using users with similar interests and activity.

    Similar users are selected using interest tags, liked posts, follows and
    commented posts. `min_similarity` filters this user group; `days_back` limits
    the post creation period. Posts already liked by the current user are excluded.
    Previously viewed posts receive a score penalty and remain eligible.

    Candidates are posts created in that period that have at least one like,
    including those with no likes from the similar-user group and a zero score.
    Ranking uses total likes, the fraction of the similar-user group who liked
    the post, and the view penalty. Equal scores use descending post IDs before
    offset pagination. No similar users produces an empty list.
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
    """List active posts ranked by relevance to the current user's profile.

    Relevance combines direct interest-tag matches, keywords from major, career
    goal and bio, and tags from liked or commented posts. Posts already liked by
    the current user are excluded. `days_back` limits the post creation period;
    `min_score` filters the resulting relevance score. Ranking precedes offset
    pagination, with descending post IDs for equal scores.
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
    """Return the current user's profile interests, education and career fields.

    The summary includes profile completeness and the count of active posts the
    user has not liked. This count is not filtered by recommendation score or age.
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
    """Return the current user's profile summary and an improvement message.

    The message identifies missing interest tags, major and career goal fields.
    """
    return application.get_profile_analysis_endpoint(
        db=db,
        current_user=current_user,
    )
