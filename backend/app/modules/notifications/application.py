from app.db.uow import UnitOfWork
from app.modules.notifications.domain import require_notification, require_read
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.schemas import NotificationResponse


def get_my_notifications(unread_only, current_user, db):
    return NotificationRepository(db).for_user(current_user.id, unread_only)


def mark_notification_read(notification_id, current_user, db):
    repo = NotificationRepository(db)
    with UnitOfWork(db):
        notification = require_notification(repo.owned(current_user.id, notification_id))
        notification.is_read = True
        repo.flush()
        repo.refresh(notification)
        response = NotificationResponse.model_validate(notification)
    return response


def delete_read_notification(notification_id, current_user, db):
    repo = NotificationRepository(db)
    with UnitOfWork(db):
        notification = require_notification(repo.owned(current_user.id, notification_id))
        require_read(notification)
        repo.delete(notification)
