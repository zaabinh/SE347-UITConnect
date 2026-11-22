"""Read persistence for trending, similar and personalized feeds."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, joinedload
from app.modules.comments.models import Comment
from app.modules.posts.models import Post, PostLike, PostShare, PostTag, PostView, Tag, Bookmark
from app.modules.users.models import Follow, User
from app.modules.posts.repository import (
    Pagination, build_post_query, paginate_latest_posts_fast,
    paginate_trending_posts_fast, paginate_query,
)
from app.modules.feed.domain import (
    calculate_time_decay, calculate_trending_score, get_trending_reason,
    preprocess_text, calculate_tag_similarity, calculate_text_similarity, calculate_content_similarity,
    _parse_interest_tags, calculate_user_tag_similarity, calculate_post_overlap, calculate_follow_overlap,
    _parse_tags_from_string, _extract_keywords_from_text, calculate_profile_relevance_score,
)


def get_trending_posts(
    db: Session,
    current_user_id: str | None,
    page: int = 1,
    page_size: int = 10,
    hours: int = 24,
    tag_filter: str | None = None,
    user_personalize: bool = True
) -> tuple[list, Pagination]:
    """
    Lấy danh sách bài viết trending.

    Args:
        db: Database session
        current_user_id: ID user hiện tại (nếu có)
        page: Số trang
        page_size: Số bài mỗi trang
        hours: Lấy bài viết trong bao nhiêu giờ qua (mặc định 24)
        tag_filter: Lọc theo tag cụ thể (nếu có)
        user_personalize: Personalize theo interest_tags của user

    Returns:
        (danh sách bài viết, pagination info)
    """
    page = max(1, page)
    page_size = min(max(1, page_size), 50)

    # Tính thời gian bắt đầu
    time_threshold = datetime.utcnow() - timedelta(hours=hours)

    # Tạo query lấy stats của bài viết
    likes_count = func.count(func.distinct(PostLike.user_id)).label("likes_count")
    comments_count = func.count(func.distinct(Comment.id)).label("comments_count")
    views_count = func.count(func.distinct(PostView.id)).label("views_count")
    shares_count = func.count(func.distinct(PostShare.id)).label("shares_count")

    query = (
        select(Post)
        .outerjoin(PostLike, PostLike.post_id == Post.id)
        .outerjoin(Comment, Comment.post_id == Post.id)
        .outerjoin(PostView, PostView.post_id == Post.id)
        .outerjoin(PostShare, PostShare.post_id == Post.id)
        .where(
            and_(
                Post.status == "active",
                Post.created_at >= time_threshold
            )
        )
        .group_by(Post.id)
    )

    # Nếu có tag_filter, join với tag
    if tag_filter:
        query = query.join(PostTag, PostTag.post_id == Post.id).join(
            Tag, Tag.id == PostTag.tag_id
        ).where(Tag.name.ilike(f"%{tag_filter}%"))

    # Lấy tổng số bài viết
    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()

    # Offset và limit
    offset = (page - 1) * page_size

    # Lấy bài viết
    posts = db.execute(
        query.order_by(Post.created_at.desc()).offset(offset).limit(page_size)
    ).scalars().all()

    # Load relationships
    for post in posts:
        db.refresh(post, ["author", "tags", "likes", "comments", "views", "shares"])

    if not posts:
        return [], Pagination(page=page, page_size=page_size, total=total)

    post_ids = [p.id for p in posts]

    # Lấy stats cho mỗi bài viết
    likes_map = dict(
        db.query(PostLike.post_id, func.count())
        .filter(PostLike.post_id.in_(post_ids))
        .group_by(PostLike.post_id)
        .all()
    )
    comments_map = dict(
        db.query(Comment.post_id, func.count())
        .filter(Comment.post_id.in_(post_ids))
        .group_by(Comment.post_id)
        .all()
    )
    views_map = dict(
        db.query(PostView.post_id, func.count())
        .filter(PostView.post_id.in_(post_ids))
        .group_by(PostView.post_id)
        .all()
    )
    shares_map = dict(
        db.query(PostShare.post_id, func.count())
        .filter(PostShare.post_id.in_(post_ids))
        .group_by(PostShare.post_id)
        .all()
    )

    # Lấy liked/bookmarked set của user
    liked_set = set()
    bookmarked_set = set()
    if current_user_id:
        liked_set = {
            post_id
            for (post_id,) in db.query(PostLike.post_id)
            .filter(PostLike.user_id == current_user_id, PostLike.post_id.in_(post_ids))
            .all()
        }
        bookmarked_set = {
            post_id
            for (post_id,) in db.query(Bookmark.post_id)
            .filter(Bookmark.user_id == current_user_id, Bookmark.post_id.in_(post_ids))
            .all()
        }

    # Tính trending score cho mỗi bài viết
    posts_with_scores = []
    for post in posts:
        likes = int(likes_map.get(post.id, 0))
        comments = int(comments_map.get(post.id, 0))
        views = int(views_map.get(post.id, 0))
        shares = int(shares_map.get(post.id, 0))

        score = calculate_trending_score(likes, comments, views, shares, post.created_at)
        reason = get_trending_reason(likes, comments, views, shares)

        posts_with_scores.append({
            "post": post,
            "likes": likes,
            "comments": comments,
            "views": views,
            "shares": shares,
            "score": score,
            "reason": reason,
            "is_liked": post.id in liked_set,
            "is_bookmarked": post.id in bookmarked_set
        })

    # Sắp xếp theo score giảm dần
    posts_with_scores.sort(key=lambda x: x["score"], reverse=True)

    return posts_with_scores, Pagination(page=page, page_size=page_size, total=total)



def get_trending_tags(
    db: Session,
    limit: int = 10,
    hours: int = 24
) -> list[dict]:
    """
    Lấy danh sách tag đang xu hướng.

    Args:
        db: Database session
        limit: Số tag trả về
        hours: Xem xét bài viết trong bao nhiêu giờ qua

    Returns:
        Danh sách tag trending
    """
    time_threshold = datetime.utcnow() - timedelta(hours=hours)

    # Query lấy tag và số bài viết
    trending_tags = (
        db.query(
            Tag.name,
            func.count(func.distinct(Post.id)).label("post_count"),
            func.sum(
                func.count(func.distinct(PostLike.user_id)) * 4 +
                func.count(func.distinct(Comment.id)) * 3 +
                func.count(func.distinct(PostView.id))
            ).label("trend_score")
        )
        .join(PostTag, PostTag.tag_id == Tag.id)
        .join(Post, Post.id == PostTag.post_id)
        .outerjoin(PostLike, PostLike.post_id == Post.id)
        .outerjoin(Comment, Comment.post_id == Post.id)
        .outerjoin(PostView, PostView.post_id == Post.id)
        .where(
            and_(
                Post.status == "active",
                Post.created_at >= time_threshold
            )
        )
        .group_by(Tag.id, Tag.name)
        .order_by(func.sum(
            func.count(func.distinct(PostLike.user_id)) * 4 +
            func.count(func.distinct(Comment.id)) * 3 +
            func.count(func.distinct(PostView.id))
        ).desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "tag_name": tag_name,
            "post_count": post_count or 0,
            "trend_score": float(trend_score or 0)
        }
        for tag_name, post_count, trend_score in trending_tags
    ]



def get_similar_posts(
    db: Session,
    post_id: int,
    current_user_id: str | None,
    limit: int = 5,
    min_similarity: float = 0.1
) -> list[dict]:
    """
    Lấy danh sách bài viết tương tự dựa trên nội dung.

    Args:
        db: Database session
        post_id: ID bài viết tham chiếu
        current_user_id: ID user hiện tại
        limit: Số bài trả về
        min_similarity: Điểm tương đồng tối thiểu (0-1)

    Returns:
        Danh sách bài viết tương tự
    """
    limit = min(max(1, limit), 20)
    min_similarity = max(0, min(1, min_similarity))

    # Lấy bài viết gốc
    reference_post = (
        db.query(Post)
        .options(joinedload(Post.tags).joinedload(PostTag.tag))
        .filter(Post.id == post_id, Post.status == "active")
        .first()
    )

    if not reference_post:
        return []

    # Lấy tất cả bài viết active khác
    similar_posts = (
        db.query(Post)
        .options(joinedload(Post.author), joinedload(Post.tags).joinedload(PostTag.tag))
        .filter(Post.status == "active", Post.id != post_id)
        .all()
    )

    # Tính similarity cho mỗi bài
    posts_with_similarity = []
    for post in similar_posts:
        similarity, reason = calculate_content_similarity(reference_post, post)

        if similarity >= min_similarity:
            posts_with_similarity.append({
                "post": post,
                "similarity": similarity,
                "reason": reason
            })

    # Sắp xếp theo similarity giảm dần
    posts_with_similarity.sort(key=lambda x: x["similarity"], reverse=True)

    # Lấy stats cho các bài
    post_ids = [p["post"].id for p in posts_with_similarity[:limit]]

    if not post_ids:
        return []

    likes_map = dict(
        db.query(PostLike.post_id, func.count())
        .filter(PostLike.post_id.in_(post_ids))
        .group_by(PostLike.post_id)
        .all()
    )
    comments_map = dict(
        db.query(Comment.post_id, func.count())
        .filter(Comment.post_id.in_(post_ids))
        .group_by(Comment.post_id)
        .all()
    )
    views_map = dict(
        db.query(PostView.post_id, func.count())
        .filter(PostView.post_id.in_(post_ids))
        .group_by(PostView.post_id)
        .all()
    )
    shares_map = dict(
        db.query(PostShare.post_id, func.count())
        .filter(PostShare.post_id.in_(post_ids))
        .group_by(PostShare.post_id)
        .all()
    )

    liked_set = set()
    bookmarked_set = set()
    if current_user_id:
        liked_set = {
            post_id
            for (post_id,) in db.query(PostLike.post_id)
            .filter(PostLike.user_id == current_user_id, PostLike.post_id.in_(post_ids))
            .all()
        }
        bookmarked_set = {
            post_id
            for (post_id,) in db.query(Bookmark.post_id)
            .filter(Bookmark.user_id == current_user_id, Bookmark.post_id.in_(post_ids))
            .all()
        }

    # Format kết quả
    result = []
    for item in posts_with_similarity[:limit]:
        post = item["post"]
        likes = int(likes_map.get(post.id, 0))
        comments = int(comments_map.get(post.id, 0))
        views = int(views_map.get(post.id, 0))
        shares = int(shares_map.get(post.id, 0))

        stats = SimpleNamespace(
            likes_count=likes,
            comments_count=comments,
            views_count=views,
            shares_count=shares,
            trending_score=likes * 4 + comments * 3 + views,
            is_liked=post.id in liked_set,
            is_bookmarked=post.id in bookmarked_set
        )

        result.append({
            "post": post,
            "stats": stats,
            "similarity": item["similarity"],
            "reason": item["reason"]
        })

    return result



def calculate_user_similarity(
    db: Session,
    user1_id: str,
    user2_id: str,
    weights: dict | None = None
) -> float:
    """
    Tính độ tương đồng giữa 2 user.

    Args:
        db: Database session
        user1_id: ID user 1
        user2_id: ID user 2
        weights: Trọng số cho từng thành phần

    Returns:
        Similarity score (0-1)
    """
    if weights is None:
        weights = {
            "tags": 0.25,
            "posts": 0.35,
            "follows": 0.25,
            "comments": 0.15
        }

    user1 = db.query(User).filter(User.id == user1_id).first()
    user2 = db.query(User).filter(User.id == user2_id).first()

    if not user1 or not user2:
        return 0.0

    # 1. Tag similarity (Interest tags)
    tags1 = _parse_interest_tags(user1.interest_tags)
    tags2 = _parse_interest_tags(user2.interest_tags)
    tag_sim = calculate_user_tag_similarity(tags1, tags2)

    # 2. Liked posts overlap
    liked1 = {
        post_id
        for (post_id,) in db.query(PostLike.post_id)
        .filter(PostLike.user_id == user1_id)
        .all()
    }
    liked2 = {
        post_id
        for (post_id,) in db.query(PostLike.post_id)
        .filter(PostLike.user_id == user2_id)
        .all()
    }
    posts_sim = calculate_post_overlap(liked1, liked2)

    # 3. Following overlap
    follows1 = {
        follow_id
        for (follow_id,) in db.query(Follow.following_id)
        .filter(Follow.follower_id == user1_id)
        .all()
    }
    follows2 = {
        follow_id
        for (follow_id,) in db.query(Follow.following_id)
        .filter(Follow.follower_id == user2_id)
        .all()
    }
    follows_sim = calculate_follow_overlap(follows1, follows2)

    # 4. Comments overlap (bài viết đã comment)
    comments1 = {
        post_id
        for (post_id,) in db.query(Comment.post_id)
        .filter(Comment.user_id == user1_id)
        .distinct()
        .all()
    }
    comments2 = {
        post_id
        for (post_id,) in db.query(Comment.post_id)
        .filter(Comment.user_id == user2_id)
        .distinct()
        .all()
    }
    comments_sim = calculate_post_overlap(comments1, comments2)

    # Weighted sum
    similarity = (
        weights["tags"] * tag_sim +
        weights["posts"] * posts_sim +
        weights["follows"] * follows_sim +
        weights["comments"] * comments_sim
    )

    return max(0.0, min(1.0, similarity))



def find_similar_users(
    db: Session,
    user_id: str,
    limit: int = 10,
    min_similarity: float = 0.2
) -> list[tuple[str, float]]:
    """
    Tìm những user tương tự với user hiện tại.

    Args:
        db: Database session
        user_id: ID user hiện tại
        limit: Số user trả về
        min_similarity: Điểm tương đồng tối thiểu

    Returns:
        Danh sách (user_id, similarity_score)
    """
    # Lấy tất cả user khác (limit 500 để tối ưu)
    all_users = (
        db.query(User.id)
        .filter(User.id != user_id, User.status == "active")
        .limit(500)
        .all()
    )

    user_similarities = []

    for (other_user_id,) in all_users:
        similarity = calculate_user_similarity(db, user_id, other_user_id)

        if similarity >= min_similarity:
            user_similarities.append((other_user_id, similarity))

    # Sắp xếp theo similarity giảm dần
    user_similarities.sort(key=lambda x: x[1], reverse=True)

    return user_similarities[:limit]



def get_collaborative_recommendations(
    db: Session,
    user_id: str,
    page: int = 1,
    page_size: int = 10,
    min_similarity: float = 0.2,
    days_back: int = 30
) -> tuple[list, Pagination]:
    """
    Lấy gợi ý bài viết dựa trên Collaborative Filtering.

    Thuật toán:
    1. Tìm user tương tự (user có sở thích giống)
    2. Lấy những bài mà những user tương tự yêu thích
    3. Loại bỏ những bài user hiện tại đã like/view
    4. Sắp xếp theo weighted score

    Args:
        db: Database session
        user_id: ID user hiện tại
        page: Số trang
        page_size: Bài mỗi trang
        min_similarity: Điểm tương đồng tối thiểu
        days_back: Xem xét bài viết trong bao nhiêu ngày qua

    Returns:
        (danh sách bài viết, pagination info)
    """
    page = max(1, page)
    page_size = min(max(1, page_size), 50)

    # Tìm user tương tự
    similar_users = find_similar_users(
        db,
        user_id,
        limit=20,
        min_similarity=min_similarity
    )

    if not similar_users:
        return [], Pagination(page=page, page_size=page_size, total=0)

    # Lấy những bài mà user tương tự yêu thích
    time_threshold = datetime.utcnow() - timedelta(days=days_back)
    similar_user_ids = [uid for uid, _ in similar_users]
    similarity_map = {uid: sim for uid, sim in similar_users}

    # Query bài viết được yêu thích bởi user tương tự
    liked_posts = (
        db.query(
            PostLike.post_id,
            func.count(func.distinct(PostLike.user_id)).label("like_count"),
            func.sum(
                func.case(
                    (PostLike.user_id.in_(similar_user_ids), 1),
                    else_=0
                )
            ).label("similar_user_count")
        )
        .filter(PostLike.post_id.in_(
            db.query(Post.id).filter(
                Post.status == "active",
                Post.created_at >= time_threshold
            )
        ))
        .group_by(PostLike.post_id)
        .all()
    )

    # Loại bỏ những bài user hiện tại đã like
    user_liked = {
        post_id
        for (post_id,) in db.query(PostLike.post_id)
        .filter(PostLike.user_id == user_id)
        .all()
    }

    # Loại bỏ những bài user đã view
    user_viewed = {
        post_id
        for (post_id,) in db.query(PostView.post_id)
        .filter(PostView.user_id == user_id)
        .all()
    }

    # Tính weighted score cho mỗi bài
    post_scores = []
    for post_id, like_count, similar_user_count in liked_posts:
        # Bỏ qua những bài user đã like
        if post_id in user_liked:
            continue

        # Ưu tiên những bài user chưa view
        view_penalty = 0.7 if post_id in user_viewed else 1.0

        # Tính weighted score
        # Weight = trung bình similarity của những user tương tự thích bài này
        similar_count = similar_user_count or 0
        if similar_count > 0:
            avg_similarity = similar_count / len(similar_users)
        else:
            avg_similarity = 0

        score = (like_count * avg_similarity) * view_penalty

        post_scores.append((post_id, score, similar_count))

    # Sắp xếp theo score giảm dần
    post_scores.sort(key=lambda x: x[1], reverse=True)

    # Lấy total
    total = len(post_scores)

    # Pagination
    offset = (page - 1) * page_size
    page_post_ids = [post_id for post_id, _, _ in post_scores[offset:offset + page_size]]

    if not page_post_ids:
        return [], Pagination(page=page, page_size=page_size, total=total)

    # Lấy bài viết và stats
    from sqlalchemy import case

    likes_count = func.count(func.distinct(PostLike.user_id)).label("likes_count")
    comments_count = func.count(func.distinct(Comment.id)).label("comments_count")
    views_count = func.count(func.distinct(PostView.id)).label("views_count")
    bookmarked = func.max(case((Bookmark.user_id == user_id, 1), else_=0)).label("is_bookmarked")

    posts_query = (
        select(
            Post,
            likes_count,
            comments_count,
            views_count,
            bookmarked
        )
        .outerjoin(PostLike, PostLike.post_id == Post.id)
        .outerjoin(Comment, Comment.post_id == Post.id)
        .outerjoin(PostView, PostView.post_id == Post.id)
        .outerjoin(Bookmark, Bookmark.post_id == Post.id)
        .where(Post.id.in_(page_post_ids), Post.status == "active")
        .group_by(Post.id)
    )

    posts = db.execute(posts_query).all()

    # Load relationships
    for post_data in posts:
        post = post_data[0]
        db.refresh(post, ["author", "tags"])

    # Map kết quả với score
    score_map = {post_id: score for post_id, score, _ in post_scores}

    result = []
    for post_data in posts:
        post = post_data[0]
        likes = int(post_data[1] or 0)
        comments = int(post_data[2] or 0)
        views = int(post_data[3] or 0)
        is_bookmarked = bool(post_data[4])

        # Tạo stats object
        stats = SimpleNamespace(
            likes_count=likes,
            comments_count=comments,
            views_count=views,
            shares_count=0,
            trending_score=likes * 4 + comments * 3 + views,
            is_liked=False,
            is_bookmarked=is_bookmarked
        )

        result.append({
            "post": post,
            "stats": stats,
            "cf_score": score_map.get(post.id, 0),
            "reason": "Được yêu thích bởi những người có sở thích giống bạn"
        })

    return result, Pagination(page=page, page_size=page_size, total=total)



def get_personalized_feed(
    db: Session,
    user_id: str,
    page: int = 1,
    page_size: int = 10,
    use_collab: bool = True,
    use_content: bool = True
) -> tuple[list, Pagination]:
    """
    Lấy personalized feed kết hợp Content-Based và Collaborative Filtering.

    Chiến lược:
    - 60% từ Collaborative Filtering (những user tương tự thích gì)
    - 40% từ Content-Based (bài tương tự với những bài user yêu thích)

    Args:
        db: Database session
        user_id: ID user hiện tại
        page: Số trang
        page_size: Bài mỗi trang
        use_collab: Dùng collaborative filtering
        use_content: Dùng content-based filtering

    Returns:
        (danh sách bài viết, pagination info)
    """
    # TODO: Khi có content-based service, kết hợp 2 phương pháp
    # Hiện tại dùng collaborative filtering

    return get_collaborative_recommendations(
        db,
        user_id,
        page=page,
        page_size=page_size
    )



def analyze_user_profile(db: Session, user_id: str) -> dict:
    """
    Phân tích thông tin profile của user.

    Returns:
        {
            "interest_tags": set,
            "major": str,
            "academic_year": str,
            "career_goal": str,
            "keywords": list,
            "liked_tags": set,
            "commented_tags": set
        }
    """
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {}

    # 1. Interest tags
    interest_tags = _parse_tags_from_string(user.interest_tags)

    # 2. Keywords từ Major
    major_keywords = _extract_keywords_from_text(user.major) if user.major else []

    # 3. Keywords từ Career goal
    career_keywords = _extract_keywords_from_text(user.career_goal, max_words=5)

    # 4. Keywords từ Bio
    bio_keywords = _extract_keywords_from_text(user.bio, max_words=3)

    # Merge keywords
    all_keywords = list(set(major_keywords + career_keywords + bio_keywords))

    # 5. Tags từ bài viết user đã like
    liked_tags = {
        tag_name
        for (tag_name,) in db.query(Tag.name)
        .join(PostTag, PostTag.tag_id == Tag.id)
        .join(PostLike, PostLike.post_id == PostTag.post_id)
        .filter(PostLike.user_id == user_id)
        .distinct()
        .all()
    }

    # 6. Tags từ bài viết user đã comment
    commented_tags = {
        tag_name
        for (tag_name,) in db.query(Tag.name)
        .join(PostTag, PostTag.tag_id == Tag.id)
        .join(Comment, Comment.post_id == PostTag.post_id)
        .filter(Comment.user_id == user_id)
        .distinct()
        .all()
    }

    return {
        "interest_tags": interest_tags,
        "major": user.major or "",
        "academic_year": user.academic_year or "",
        "career_goal": user.career_goal or "",
        "keywords": all_keywords,
        "liked_tags": liked_tags,
        "commented_tags": commented_tags,
    }



def get_profile_based_recommendations(
    db: Session,
    user_id: str,
    page: int = 1,
    page_size: int = 10,
    min_score: float = 0.1,
    days_back: int = 30
) -> tuple[list, Pagination]:
    """
    Lấy gợi ý bài viết dựa trên profile user.

    Args:
        db: Database session
        user_id: ID user
        page: Trang hiện tại
        page_size: Bài mỗi trang
        min_score: Điểm liên quan tối thiểu
        days_back: Bài viết trong bao nhiêu ngày qua

    Returns:
        (danh sách bài viết, pagination)
    """
    page = max(1, page)
    page_size = min(max(1, page_size), 50)

    # Phân tích profile
    profile_info = analyze_user_profile(db, user_id)

    if not profile_info:
        return [], Pagination(page=page, page_size=page_size, total=0)

    # Lấy bài viết active trong timeframe
    time_threshold = datetime.utcnow() - timedelta(days=days_back)

    posts = (
        db.query(Post)
        .options(joinedload(Post.author), joinedload(Post.tags).joinedload(PostTag.tag))
        .filter(
            Post.status == "active",
            Post.created_at >= time_threshold
        )
        .all()
    )

    if not posts:
        return [], Pagination(page=page, page_size=page_size, total=0)

    # Lấy bài user đã like
    user_liked = {
        post_id
        for (post_id,) in db.query(PostLike.post_id)
        .filter(PostLike.user_id == user_id)
        .all()
    }

    # Tính score cho mỗi bài
    posts_with_scores = []

    for post in posts:
        # Bỏ qua những bài user đã like
        if post.id in user_liked:
            continue

        score, reason = calculate_profile_relevance_score(post, profile_info)

        if score >= min_score:
            posts_with_scores.append({
                "post": post,
                "score": score,
                "reason": reason
            })

    # Sắp xếp theo score giảm dần
    posts_with_scores.sort(key=lambda x: x["score"], reverse=True)

    # Pagination
    total = len(posts_with_scores)
    offset = (page - 1) * page_size
    page_data = posts_with_scores[offset:offset + page_size]

    if not page_data:
        return [], Pagination(page=page, page_size=page_size, total=total)

    # Lấy stats
    page_post_ids = [item["post"].id for item in page_data]

    from sqlalchemy import case

    likes_count = func.count(func.distinct(PostLike.user_id)).label("likes_count")
    comments_count = func.count(func.distinct(Comment.id)).label("comments_count")
    views_count = func.count(func.distinct(PostView.id)).label("views_count")
    is_liked = func.max(case((PostLike.user_id == user_id, 1), else_=0)).label("is_liked")
    is_bookmarked = func.max(case((Bookmark.user_id == user_id, 1), else_=0)).label("is_bookmarked")

    stats_query = (
        select(
            Post.id,
            likes_count,
            comments_count,
            views_count,
            is_liked,
            is_bookmarked
        )
        .outerjoin(PostLike, PostLike.post_id == Post.id)
        .outerjoin(Comment, Comment.post_id == Post.id)
        .outerjoin(PostView, PostView.post_id == Post.id)
        .outerjoin(Bookmark, Bookmark.post_id == Post.id)
        .where(Post.id.in_(page_post_ids))
        .group_by(Post.id)
    )

    stats_rows = db.execute(stats_query).all()
    stats_map = {row[0]: row for row in stats_rows}

    # Format result
    result = []
    for item in page_data:
        post = item["post"]
        stats_row = stats_map.get(post.id)

        if stats_row:
            likes = int(stats_row[1] or 0)
            comments = int(stats_row[2] or 0)
            views = int(stats_row[3] or 0)
            is_liked = bool(stats_row[4])
            is_bookmarked = bool(stats_row[5])
        else:
            likes = comments = views = 0
            is_liked = is_bookmarked = False

        stats = SimpleNamespace(
            likes_count=likes,
            comments_count=comments,
            views_count=views,
            shares_count=0,
            trending_score=likes * 4 + comments * 3 + views,
            is_liked=is_liked,
            is_bookmarked=is_bookmarked
        )

        result.append({
            "post": post,
            "stats": stats,
            "profile_score": item["score"],
            "reason": item["reason"]
        })

    return result, Pagination(page=page, page_size=page_size, total=total)



def get_user_profile_summary(db: Session, user_id: str) -> dict:
    """
    Lấy tóm tắt profile của user để hiển thị.

    Returns:
        {
            "interest_tags": list,
            "major": str,
            "academic_year": str,
            "career_goal": str,
            "profile_strength": float,  # 0-1
            "recommendations_count": int
        }
    """
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {}

    profile_info = analyze_user_profile(db, user_id)

    # Tính "profile strength" dựa trên độ đầy đủ thông tin
    completeness_score = 0
    max_score = 5

    if user.interest_tags:
        completeness_score += 1
    if user.major:
        completeness_score += 1
    if user.academic_year:
        completeness_score += 1
    if user.career_goal:
        completeness_score += 1
    if user.bio:
        completeness_score += 1

    profile_strength = completeness_score / max_score

    # Đếm số bài viết có thể recommend
    recommendations_count = (
        db.query(Post)
        .filter(Post.status == "active")
        .filter(Post.id.notin_(
            db.query(PostLike.post_id)
            .filter(PostLike.user_id == user_id)
        ))
        .count()
    )

    return {
        "interest_tags": list(profile_info.get("interest_tags", [])),
        "major": user.major or "",
        "academic_year": user.academic_year or "",
        "career_goal": user.career_goal or "",
        "profile_strength": profile_strength,
        "recommendations_count": recommendations_count,
        "profile_completeness": {
            "has_interest_tags": bool(user.interest_tags),
            "has_major": bool(user.major),
            "has_academic_year": bool(user.academic_year),
            "has_career_goal": bool(user.career_goal),
            "has_bio": bool(user.bio),
        }
    }



def get_feed_rows(db, current_user_id, search, tag, mode, sort, page, page_size):
    if mode == "trending" or sort == "trending":
        rows, pagination = paginate_trending_posts_fast(db, current_user_id, search, tag, page, page_size)
        return rows, pagination, True
    if sort == "latest" and mode != "trending":
        rows, pagination = paginate_latest_posts_fast(db, current_user_id, search, tag, mode, page, page_size)
        return rows, pagination, True
    query = build_post_query(current_user_id, search, tag, mode, sort)
    rows, pagination = paginate_query(db, query, page, page_size)
    return rows, pagination, False
