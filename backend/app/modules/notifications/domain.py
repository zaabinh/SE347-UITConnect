from app.core.exceptions import ApplicationError


def require_notification(notification):
    if notification is None:
        raise ApplicationError(404, 'Notification not found.')
    return notification


def require_read(notification):
    if not notification.is_read:
        raise ApplicationError(400, 'Only read notifications can be deleted.')
