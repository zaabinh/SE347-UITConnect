from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.modules.auth.dependencies import require_active_verified_user
from app.modules.users.models import User
from app.modules.notifications.models import Notification
from app.modules.auth.schemas import MessageResponse
from app.modules.notifications.schemas import NotificationResponse


router = APIRouter(prefix='', tags=['Users'])


@router.get("/users/me/notifications", response_model=list[NotificationResponse])
def get_my_notifications(
    unread_only: bool = Query(default=False),
    current_user: User = Depends(require_active_verified_user),
    db: Session = Depends(get_db),
):
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        query = query.filter(Notification.is_read.is_(False))
    return query.order_by(Notification.created_at.desc(), Notification.id.desc()).all()

@router.post("/users/me/notifications/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(require_active_verified_user),
    db: Session = Depends(get_db),
):
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == current_user.id)
        .first()
    )
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification

@router.delete("/users/me/notifications/{notification_id}", response_model=MessageResponse)
def delete_read_notification(
    notification_id: int,
    current_user: User = Depends(require_active_verified_user),
    db: Session = Depends(get_db),
):
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == current_user.id)
        .first()
    )
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
    if not notification.is_read:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only read notifications can be deleted.")
    db.delete(notification)
    db.commit()
    return MessageResponse(message="Notification deleted successfully.")
