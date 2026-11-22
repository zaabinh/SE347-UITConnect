from sqlalchemy.orm import joinedload
from app.db.repository import Repository
from app.modules.comments.models import Comment
from app.modules.moderation.models import Report
from app.modules.posts.models import Post


class CommentRepository(Repository):
    def post(self, post_id):
        return self.query(Post).filter(Post.id == post_id).first()

    def comment(self, post_id, comment_id):
        return self.query(Comment).options(joinedload(Comment.author)).filter(
            Comment.id == comment_id, Comment.post_id == post_id).first()

    def reported(self, user_id, comment_id):
        return self.query(Report).filter(Report.reporter_id == user_id, Report.comment_id == comment_id).first()

    def active_comments(self, post_id):
        return self.query(Comment).options(joinedload(Comment.author)).filter(
            Comment.post_id == post_id, Comment.status == 'active',
        ).order_by(Comment.created_at.asc(), Comment.id.asc()).all()
