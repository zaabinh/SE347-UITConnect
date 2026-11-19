from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.modules.auth.dependencies import require_active_verified_user
from app.modules.users.models import User
from app.modules.auth.schemas import MessageResponse
from app.modules.notifications.schemas import NotificationResponse
from app.modules.notifications import application

router = APIRouter(prefix='', tags=['Users'])

@router.get('/users/me/notifications', response_model=list[NotificationResponse])
def get_my_notifications(unread_only: bool=Query(default=False), current_user: User=Depends(require_active_verified_user), db: Session=Depends(get_db)):
    return application.get_my_notifications(unread_only=unread_only, current_user=current_user, db=db)


@router.post('/users/me/notifications/{notification_id}/read', response_model=NotificationResponse)
def mark_notification_read(notification_id: int, current_user: User=Depends(require_active_verified_user), db: Session=Depends(get_db)):
    return application.mark_notification_read(notification_id=notification_id, current_user=current_user, db=db)


@router.delete('/users/me/notifications/{notification_id}', response_model=MessageResponse)
def delete_read_notification(notification_id: int, current_user: User=Depends(require_active_verified_user), db: Session=Depends(get_db)):
    return application.delete_read_notification(notification_id=notification_id, current_user=current_user, db=db)
