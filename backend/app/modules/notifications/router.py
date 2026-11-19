from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.modules.auth.dependencies import require_active_verified_user
from app.modules.users.models import User
from app.modules.notifications.schemas import NotificationResponse
from app.modules.notifications import application

router = APIRouter(prefix='/notifications', tags=['Notifications'])

@router.get('', response_model=list[NotificationResponse], operation_id='notifications_list')
def get_my_notifications(unread_only: bool=Query(default=False), current_user: User=Depends(require_active_verified_user), db: Session=Depends(get_db)):
    return application.get_my_notifications(unread_only=unread_only, current_user=current_user, db=db)


@router.put('/{notification_id}/read', response_model=NotificationResponse, operation_id='notifications_mark_read')
def mark_notification_read(notification_id: int, current_user: User=Depends(require_active_verified_user), db: Session=Depends(get_db)):
    return application.mark_notification_read(notification_id=notification_id, current_user=current_user, db=db)


@router.delete('/{notification_id}', status_code=status.HTTP_204_NO_CONTENT, operation_id='notifications_delete')
def delete_read_notification(notification_id: int, current_user: User=Depends(require_active_verified_user), db: Session=Depends(get_db)):
    application.delete_read_notification(notification_id=notification_id, current_user=current_user, db=db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
