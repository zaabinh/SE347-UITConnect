"""Moderation persistence; transaction ownership belongs to the application."""

from sqlalchemy import and_, func

from app.db.repository import Repository
from app.modules.comments.models import Comment
from app.modules.moderation.models import AdminAuditLog, Report
from app.modules.posts.models import Post, PostTag, Tag
from app.modules.users.models import User


class ModerationRepository(Repository):
    def user(self, user_id: str):
        return self.query(User).filter(User.id == user_id).first()

    def post(self, post_id: int):
        return self.query(Post).filter(Post.id == post_id).first()

    def comment(self, comment_id: int):
        return self.query(Comment).filter(Comment.id == comment_id).first()

    def report(self, report_id: int):
        return self.query(Report).filter(Report.id == report_id).first()

    def latest_report_audit(self, report_id: int):
        return self.query(AdminAuditLog).filter(
            AdminAuditLog.action_type == "moderate_report", AdminAuditLog.target_type == "report",
            AdminAuditLog.target_id == str(report_id),
        ).order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc()).first()

    def tag(self, tag_id: int):
        return self.query(Tag).filter(Tag.id == tag_id).first()

    def tag_by_name_or_slug(self, name: str, slug: str):
        return self.query(Tag).filter((Tag.slug == slug) | (Tag.name == name)).first()

    def list_users(self, page, page_size, search, status_filter, sort_by, sort_order):
        query = self.query(User)
        if search:
            term = f"%{search.strip()}%"
            query = query.filter(User.username.ilike(term) | User.email.ilike(term) | User.full_name.ilike(term))
        if status_filter:
            query = query.filter(func.lower(User.status) == status_filter.lower())
        column = {"created_at": User.created_at, "username": User.username, "email": User.email}[sort_by]
        query = query.order_by(column.asc() if sort_order == "asc" else column.desc(), User.id.asc())
        return self._page(query, page, page_size)

    def list_reports(self, page, page_size, status_filter, reason):
        query = self.query(Report)
        if status_filter:
            query = query.filter(Report.status == status_filter)
        if reason:
            query = query.filter(Report.reason == reason)
        return self._page(query.order_by(Report.created_at.desc(), Report.id.desc()), page, page_size)

    def pending_posts(self, page, page_size):
        query = self.query(Post).filter(Post.status == "pending").order_by(Post.created_at.desc(), Post.id.desc())
        return self._page(query, page, page_size)

    def _page(self, query, page, page_size):
        total = query.count()
        return query.offset((page - 1) * page_size).limit(page_size).all(), total

    def list_tags(self):
        return self.query(Tag).order_by(Tag.name.asc()).all()

    def add_tag(self, name: str, slug: str):
        tag = self.add(Tag(name=name, slug=slug))
        self.flush()
        return tag

    def link_tag(self, post, tag):
        if not any(association.tag_id == tag.id for association in post.tags):
            self.add(PostTag(post_id=post.id, tag_id=tag.id))

    def add_audit_log(self, admin_user_id, action_type, target_type, target_id, notes=None):
        self.add(AdminAuditLog(
            admin_user_id=admin_user_id, action_type=action_type,
            target_type=target_type, target_id=target_id, notes=notes,
        ))

    def analytics(self, day_start, week_start):
        def count(model, *filters):
            return self.query(func.count()).select_from(model).filter(*filters).scalar() or 0

        return {
            "users_today": count(User, User.created_at >= day_start),
            "users_week": count(User, User.created_at >= week_start),
            "posts_today": count(Post, and_(Post.created_at >= day_start, Post.status == "active")),
            "posts_week": count(Post, and_(Post.created_at >= week_start, Post.status == "active")),
            "comments_today": count(Comment, Comment.created_at >= day_start),
            "comments_week": count(Comment, Comment.created_at >= week_start),
            "reports_today": count(Report, Report.created_at >= day_start),
            "reports_week": count(Report, Report.created_at >= week_start),
            "pending_reports": count(Report, Report.status == "pending"),
            "pending_posts": count(Post, Post.status == "pending"),
        }
