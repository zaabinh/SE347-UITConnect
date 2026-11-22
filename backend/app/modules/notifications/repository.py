from app.db.repository import Repository
from app.modules.notifications.models import Notification
from app.modules.users.models import Follow, User


class NotificationRepository(Repository):
    def for_user(self, user_id, unread_only=False):
        query = self.query(Notification).filter(Notification.user_id == user_id)
        if unread_only:
            query = query.filter(Notification.is_read.is_(False))
        return query.order_by(Notification.created_at.desc(), Notification.id.desc()).all()

    def owned(self, user_id, notification_id):
        return self.query(Notification).filter(Notification.id == notification_id,
                                                Notification.user_id == user_id).first()

    def admins(self):
        return self.query(User).filter(User.role.ilike('admin'), User.status == 'active').all()

    def followers(self, author_id):
        return self.query(Follow).filter(Follow.following_id == author_id).all()
