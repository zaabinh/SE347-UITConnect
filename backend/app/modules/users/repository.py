"""SQLAlchemy persistence for profiles, follows, and user activity."""

from sqlalchemy import func, or_

from app.db.repository import Repository
from app.modules.comments.models import Comment
from app.modules.posts.models import Bookmark, Post
from app.modules.users.models import Follow, User


class UserRepository(Repository):
    def by_id(self, user_id):
        return self.query(User).filter(User.id == user_id).first()

    def by_username(self, username):
        return self.query(User).filter(User.username == username).first()

    def followers_count(self, user_id):
        return self.query(func.count()).select_from(Follow).filter(Follow.following_id == user_id).scalar() or 0

    def following_count(self, user_id):
        return self.query(func.count()).select_from(Follow).filter(Follow.follower_id == user_id).scalar() or 0

    def posts_count(self, user_id, include_non_active):
        query = self.query(func.count()).select_from(Post).filter(Post.user_id == user_id, Post.status != "deleted")
        if not include_non_active:
            query = query.filter(Post.status == "active")
        return query.scalar() or 0

    def is_following(self, follower_id, following_id):
        return self.query(Follow).filter(
            Follow.follower_id == follower_id, Follow.following_id == following_id,
        ).first() is not None

    def user_posts(self, user_id, include_non_active):
        query = self.query(Post).filter(Post.user_id == user_id, Post.status != "deleted")
        if not include_non_active:
            query = query.filter(Post.status == "active")
        return query.order_by(Post.created_at.desc(), Post.id.desc()).all()

    def user_comments(self, user_id, viewer):
        query = (
            self.query(Comment, Post.title.label("post_title"))
            .join(Post, Post.id == Comment.post_id)
            .filter(Comment.user_id == user_id, Comment.status == "active", Post.status != "deleted")
        )
        if viewer.role.lower() != "admin":
            query = query.filter(or_(Post.status == "active", Post.user_id == viewer.id))
        return query.order_by(Comment.created_at.desc(), Comment.id.desc()).all()

    def user_bookmarks(self, user_id, viewer):
        query = (
            self.query(Post)
            .join(Bookmark, Bookmark.post_id == Post.id)
            .filter(Bookmark.user_id == user_id, Post.status != "deleted")
        )
        if viewer.role.lower() != "admin":
            query = query.filter(or_(Post.status == "active", Post.user_id == viewer.id))
        return query.order_by(Bookmark.created_at.desc(), Post.id.desc()).all()

    def follow(self, follower_id, following_id):
        return self.query(Follow).filter(
            Follow.follower_id == follower_id, Follow.following_id == following_id,
        ).first()

    def add_follow(self, follower_id, following_id):
        return self.add(Follow(follower_id=follower_id, following_id=following_id))
