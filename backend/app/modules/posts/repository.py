"""SQLAlchemy persistence for posts, tags and feed reads."""

import math
from dataclasses import dataclass
from types import SimpleNamespace
from datetime import datetime
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload
from app.db.repository import Repository
from app.modules.posts.domain import normalize_tags, slugify
from app.modules.posts.models import Bookmark, Post, PostLike, PostShare, PostTag, PostView, Tag
from app.modules.comments.models import Comment
from app.modules.moderation.models import Report
from app.modules.users.models import Follow, User


def split_known_and_new_tags(db: Session, raw_tags: list[str] | None) -> tuple[list[str], list[str]]:
    desired_names = normalize_tags(raw_tags)
    if not desired_names:
        return [], []
    existing_tags = db.query(Tag).filter(Tag.name.in_(desired_names)).all()
    existing_names = {tag.name for tag in existing_tags}
    known = [name for name in desired_names if name in existing_names]
    new_tags = [name for name in desired_names if name not in existing_names]
    return known, new_tags


def sync_post_tags(db: Session, post: Post, raw_tags: list[str] | None, create_missing: bool = True) -> None:
    desired_names = normalize_tags(raw_tags)
    current_names = {association.tag.name: association for association in post.tags}

    for name, association in list(current_names.items()):
        if name not in desired_names:
            db.delete(association)

    for name in desired_names:
        if name in current_names:
            continue
        slug = slugify(name)
        tag = db.query(Tag).filter(Tag.slug == slug).first()
        if not tag:
            if not create_missing:
                continue
            tag = Tag(name=name, slug=slug)
            db.add(tag)
            db.flush()
        db.add(PostTag(post_id=post.id, tag_id=tag.id))


@dataclass
class Pagination:
    page: int
    page_size: int
    total: int

    @property
    def total_pages(self) -> int:
        return math.ceil(self.total / self.page_size) if self.page_size else 0
    
hours_old = 12
def build_post_query(current_user_id: str | None, search: str | None, tag: str | None, mode: str, sort: str):
    likes_count = func.count(func.distinct(PostLike.user_id)).label("likes_count")
    comments_count = func.count(func.distinct(Comment.id)).label("comments_count")
    views_count = func.count(func.distinct(PostView.id)).label("views_count")
    shares_count = func.count(func.distinct(PostShare.id)).label("shares_count")
    
    time_decay = math.exp(-hours_old / 24)
    trending_score = ((likes_count * 4 + comments_count * 3 + views_count)*time_decay).label("trending_score")
    is_liked = func.max(case((PostLike.user_id == current_user_id, 1), else_=0)).label("is_liked")
    is_bookmarked = func.max(case((Bookmark.user_id == current_user_id, 1), else_=0)).label("is_bookmarked")

    query = (
        select(
            Post,
            likes_count,
            comments_count,
            views_count,
            shares_count,
            trending_score,
            is_liked,
            is_bookmarked,
        )
        .outerjoin(PostLike, PostLike.post_id == Post.id)
        .outerjoin(Comment, (Comment.post_id == Post.id) & (Comment.status == "active"))
        .outerjoin(PostView, PostView.post_id == Post.id)
        .outerjoin(PostShare, PostShare.post_id == Post.id)
        .outerjoin(Bookmark, Bookmark.post_id == Post.id)
        .where(Post.status == "active")
        .group_by(
            Post.id,
            Post.user_id,
            Post.title,
            Post.slug,
            Post.content,
            Post.cover_image,
            Post.status,
            Post.original_post_id,
            Post.share_caption,
            Post.requested_new_tags,
            Post.created_at,
        )
    )

    if search:
        term = f"%{search.strip()}%"
        query = query.where((Post.title.ilike(term)) | (Post.content.ilike(term)))

    if tag:
        query = query.join(PostTag, PostTag.post_id == Post.id).join(Tag, Tag.id == PostTag.tag_id).where(Tag.slug == slugify(tag))

    if mode == "following" and current_user_id:
        query = query.join(Follow, Follow.following_id == Post.user_id).where(Follow.follower_id == current_user_id)

    if sort == "trending" or mode == "trending":
        query = query.order_by(trending_score.desc(), Post.created_at.desc(), Post.id.desc())
    elif sort == "most-liked":
        query = query.order_by(likes_count.desc(), Post.created_at.desc(), Post.id.desc())
    elif sort == "most-commented":
        query = query.order_by(comments_count.desc(), Post.created_at.desc(), Post.id.desc())
    else:
        query = query.order_by(Post.created_at.desc(), Post.id.desc())

    return query


def paginate_query(db: Session, query, page: int, page_size: int):
    page = max(1, page)
    page_size = min(max(1, page_size), 50)
    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    rows = db.execute(query.offset((page - 1) * page_size).limit(page_size)).all()
    return rows, Pagination(page=page, page_size=page_size, total=total)


def _paginate_bounds(page: int, page_size: int) -> tuple[int, int]:
    normalized_page = max(1, page)
    normalized_page_size = min(max(1, page_size), 50)
    return normalized_page, normalized_page_size


def _parse_interest_tags(raw_tags: str | None) -> set[str]:
    if not raw_tags:
        return set()
    return {item.strip().lower() for item in raw_tags.split(",") if item.strip()}


def paginate_latest_posts_fast(
    db: Session,
    current_user_id: str | None,
    search: str | None,
    tag: str | None,
    mode: str,
    page: int,
    page_size: int,
):
    page, page_size = _paginate_bounds(page, page_size)
    offset = (page - 1) * page_size

    post_ids_query = select(Post.id).where(Post.status == "active")

    if search:
        term = f"%{search.strip()}%"
        post_ids_query = post_ids_query.where((Post.title.ilike(term)) | (Post.content.ilike(term)))

    if tag:
        post_ids_query = (
            post_ids_query.join(PostTag, PostTag.post_id == Post.id)
            .join(Tag, Tag.id == PostTag.tag_id)
            .where(Tag.slug == slugify(tag))
        )

    if mode == "following" and current_user_id:
        post_ids_query = post_ids_query.join(Follow, Follow.following_id == Post.user_id).where(Follow.follower_id == current_user_id)

    total = db.execute(select(func.count()).select_from(post_ids_query.distinct().subquery())).scalar_one()
    if mode == "for-you" and current_user_id:
        candidate_ids = db.execute(post_ids_query.order_by(Post.created_at.desc(), Post.id.desc()).limit(200)).scalars().all()
        total = len(candidate_ids)
        if candidate_ids:
            user = db.query(User).filter(User.id == current_user_id).first()
            preferred_tags = _parse_interest_tags(user.interest_tags if user else None)
            following_ids = {
                followed_id
                for (followed_id,) in db.query(Follow.following_id).filter(Follow.follower_id == current_user_id).all()
            }
            candidate_posts = (
                db.query(Post)
                .options(joinedload(Post.tags).joinedload(PostTag.tag))
                .filter(Post.id.in_(candidate_ids))
                .all()
            )
            post_by_id = {post.id: post for post in candidate_posts}

            likes_map = dict(db.query(PostLike.post_id, func.count()).filter(PostLike.post_id.in_(candidate_ids)).group_by(PostLike.post_id).all())
            comments_map = dict(db.query(Comment.post_id, func.count()).filter(Comment.post_id.in_(candidate_ids), Comment.status == "active").group_by(Comment.post_id).all())
            views_map = dict(db.query(PostView.post_id, func.count()).filter(PostView.post_id.in_(candidate_ids)).group_by(PostView.post_id).all())
            shares_map = dict(db.query(PostShare.post_id, func.count()).filter(PostShare.post_id.in_(candidate_ids)).group_by(PostShare.post_id).all())

            def score(post_id: int) -> float:
                post = post_by_id.get(post_id)
                if not post:
                    return 0.0
                post_tags = {assoc.tag.name.lower() for assoc in post.tags if assoc.tag and assoc.tag.name}
                tag_overlap = len(preferred_tags.intersection(post_tags))
                follow_score = 3 if post.user_id in following_ids else 0
                popularity = float(likes_map.get(post_id, 0)) * 2.0 + float(comments_map.get(post_id, 0)) * 2.5 + float(shares_map.get(post_id, 0)) * 1.5 + float(views_map.get(post_id, 0)) * 0.2
                return tag_overlap * 4.0 + follow_score + popularity

            ranked_ids = sorted(candidate_ids, key=lambda post_id: (score(post_id), post_id), reverse=True)
            page_ids = ranked_ids[offset: offset + page_size]
        else:
            page_ids = []
    else:
        page_ids = db.execute(post_ids_query.order_by(Post.created_at.desc(), Post.id.desc()).offset(offset).limit(page_size)).scalars().all()

    if not page_ids:
        return [], Pagination(page=page, page_size=page_size, total=total)

    posts = (
        db.query(Post)
        .options(joinedload(Post.author), joinedload(Post.tags).joinedload(PostTag.tag))
        .filter(Post.id.in_(page_ids))
        .all()
    )
    post_by_id = {post.id: post for post in posts}
    ordered_posts = [post_by_id[post_id] for post_id in page_ids if post_id in post_by_id]

    likes_map = dict(db.query(PostLike.post_id, func.count()).filter(PostLike.post_id.in_(page_ids)).group_by(PostLike.post_id).all())
    comments_map = dict(db.query(Comment.post_id, func.count()).filter(Comment.post_id.in_(page_ids), Comment.status == "active").group_by(Comment.post_id).all())
    views_map = dict(db.query(PostView.post_id, func.count()).filter(PostView.post_id.in_(page_ids)).group_by(PostView.post_id).all())
    shares_map = dict(db.query(PostShare.post_id, func.count()).filter(PostShare.post_id.in_(page_ids)).group_by(PostShare.post_id).all())

    liked_set: set[int] = set()
    bookmarked_set: set[int] = set()
    if current_user_id:
        liked_set = set(
            db.query(PostLike.post_id)
            .filter(PostLike.user_id == current_user_id, PostLike.post_id.in_(page_ids))
            .all()
        )
        liked_set = {post_id for (post_id,) in liked_set}

        bookmarked_set = set(
            db.query(Bookmark.post_id)
            .filter(Bookmark.user_id == current_user_id, Bookmark.post_id.in_(page_ids))
            .all()
        )
        bookmarked_set = {post_id for (post_id,) in bookmarked_set}

    rows = []
    for post in ordered_posts:
        likes_count = int(likes_map.get(post.id, 0))
        comments_count = int(comments_map.get(post.id, 0))
        views_count = int(views_map.get(post.id, 0))
        shares_count = int(shares_map.get(post.id, 0))
        stats = SimpleNamespace(
            likes_count=likes_count,
            comments_count=comments_count,
            views_count=views_count,
            shares_count=shares_count,
            trending_score=likes_count * 4 + comments_count * 3 + views_count,
            is_liked=post.id in liked_set,
            is_bookmarked=post.id in bookmarked_set,
        )
        rows.append((post, stats))

    return rows, Pagination(page=page, page_size=page_size, total=total)


def paginate_trending_posts_fast(
    db: Session,
    current_user_id: str | None,
    search: str | None,
    tag: str | None,
    page: int,
    page_size: int,
):
    page, page_size = _paginate_bounds(page, page_size)
    offset = (page - 1) * page_size

    post_ids_query = select(Post.id).where(Post.status == "active")

    if search:
        term = f"%{search.strip()}%"
        post_ids_query = post_ids_query.where((Post.title.ilike(term)) | (Post.content.ilike(term)))

    if tag:
        post_ids_query = (
            post_ids_query.join(PostTag, PostTag.post_id == Post.id)
            .join(Tag, Tag.id == PostTag.tag_id)
            .where(Tag.slug == slugify(tag))
        )

    total = db.execute(select(func.count()).select_from(post_ids_query.distinct().subquery())).scalar_one()
    candidate_ids = db.execute(post_ids_query.order_by(Post.created_at.desc(), Post.id.desc()).limit(300)).scalars().all()
    total = len(candidate_ids)
    if not candidate_ids:
        return [], Pagination(page=page, page_size=page_size, total=total)

    likes_map = dict(db.query(PostLike.post_id, func.count()).filter(PostLike.post_id.in_(candidate_ids)).group_by(PostLike.post_id).all())
    comments_map = dict(db.query(Comment.post_id, func.count()).filter(Comment.post_id.in_(candidate_ids), Comment.status == "active").group_by(Comment.post_id).all())
    views_map = dict(db.query(PostView.post_id, func.count()).filter(PostView.post_id.in_(candidate_ids)).group_by(PostView.post_id).all())
    shares_map = dict(db.query(PostShare.post_id, func.count()).filter(PostShare.post_id.in_(candidate_ids)).group_by(PostShare.post_id).all())

    posts = (
        db.query(Post)
        .options(joinedload(Post.author), joinedload(Post.tags).joinedload(PostTag.tag))
        .filter(Post.id.in_(candidate_ids))
        .all()
    )
    post_by_id = {post.id: post for post in posts}

    def score(post_id: int) -> float:
        post = post_by_id.get(post_id)
        if not post:
            return 0.0
        age_hours = max((datetime.now() - post.created_at).total_seconds() / 3600, 0.0)
        decay = math.exp(-age_hours / 72)
        popularity = (
            float(likes_map.get(post_id, 0)) * 4.0
            + float(comments_map.get(post_id, 0)) * 3.0
            + float(shares_map.get(post_id, 0)) * 5.0
            + float(views_map.get(post_id, 0))
        )
        return popularity * decay

    ranked_ids = sorted(candidate_ids, key=lambda post_id: (score(post_id), post_id), reverse=True)
    page_ids = ranked_ids[offset: offset + page_size]
    ordered_posts = [post_by_id[post_id] for post_id in page_ids if post_id in post_by_id]

    liked_set: set[int] = set()
    bookmarked_set: set[int] = set()
    if current_user_id and page_ids:
        liked_set = {
            post_id
            for (post_id,) in db.query(PostLike.post_id)
            .filter(PostLike.user_id == current_user_id, PostLike.post_id.in_(page_ids))
            .all()
        }
        bookmarked_set = {
            post_id
            for (post_id,) in db.query(Bookmark.post_id)
            .filter(Bookmark.user_id == current_user_id, Bookmark.post_id.in_(page_ids))
            .all()
        }

    rows = []
    for post in ordered_posts:
        likes_count = int(likes_map.get(post.id, 0))
        comments_count = int(comments_map.get(post.id, 0))
        views_count = int(views_map.get(post.id, 0))
        shares_count = int(shares_map.get(post.id, 0))
        stats = SimpleNamespace(
            likes_count=likes_count,
            comments_count=comments_count,
            views_count=views_count,
            shares_count=shares_count,
            trending_score=int(score(post.id)),
            is_liked=post.id in liked_set,
            is_bookmarked=post.id in bookmarked_set,
        )
        rows.append((post, stats))

    return rows, Pagination(page=page, page_size=page_size, total=total)


def build_stats_for_post(db: Session, post_id: int, current_user_id: str):
    # Số lượt like
    likes_count = db.query(func.count(PostLike.user_id)).filter(PostLike.post_id == post_id).scalar() or 0
    # Số lượt comment
    comments_count = db.query(func.count(Comment.id)).filter(Comment.post_id == post_id, Comment.status == "active").scalar() or 0
    # Số lượt view
    views_count = db.query(func.count(PostView.id)).filter(PostView.post_id == post_id).scalar() or 0
    # Số lượt share
    shares_count = db.query(func.count(PostShare.id)).filter(PostShare.post_id == post_id).scalar() or 0
    # Bài viết đã được người dùng hiện tại thích chưa
    is_liked = (
        db.query(PostLike)
        .filter(PostLike.post_id == post_id, PostLike.user_id == current_user_id)
        .first()
        is not None
    )
    # Bài viết đã được người dùng hiện tại lưu chưa
    is_bookmarked = (
        db.query(Bookmark)
        .filter(Bookmark.post_id == post_id, Bookmark.user_id == current_user_id)
        .first()
        is not None
    )
    return type(
        "Stats",
        (),
        {
            "likes_count": likes_count,
            "comments_count": comments_count,
            "views_count": views_count,
            "shares_count": shares_count,
            "trending_score": likes_count * 4 + comments_count * 3 + views_count,
            "is_liked": is_liked,
            "is_bookmarked": is_bookmarked,
        },
    )()


class PostRepository(Repository):
    def get(self, post_id: int):
        return (
            self.query(Post)
            .options(joinedload(Post.author), joinedload(Post.tags).joinedload(PostTag.tag))
            .filter(Post.id == post_id)
            .first()
        )

    def stats(self, post_id: int, current_user_id: str):
        return build_stats_for_post(self, post_id, current_user_id)

    def active_row(self, post_id: int, current_user_id: str):
        query = build_post_query(current_user_id, None, None, "for-you", "latest").where(Post.id == post_id)
        return self.execute(query).first()

    def tags(self, ordered: bool = False):
        query = self.query(Tag)
        return query.order_by(Tag.name.asc()).all() if ordered else query.all()

    def tag_by_slug(self, slug: str):
        return self.query(Tag).filter(Tag.slug == slug).first()

    def active_comment_count(self, post_id: int):
        return self.query(Comment).filter(Comment.post_id == post_id, Comment.status == "active").count()

    def like(self, post_id: int, user_id: str):
        return self.query(PostLike).filter(PostLike.post_id == post_id, PostLike.user_id == user_id).first()

    def bookmark(self, post_id: int, user_id: str):
        return self.query(Bookmark).filter(Bookmark.user_id == user_id, Bookmark.post_id == post_id).first()

    def report(self, post_id: int, reporter_id: str):
        return self.query(Report).filter(Report.reporter_id == reporter_id, Report.post_id == post_id, Report.comment_id.is_(None)).first()

    def split_tags(self, raw_tags):
        return split_known_and_new_tags(self, raw_tags)

    def sync_tags(self, post, raw_tags, create_missing=True):
        sync_post_tags(self, post, raw_tags, create_missing)
