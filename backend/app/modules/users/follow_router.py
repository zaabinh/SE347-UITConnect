from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import require_active_verified_user
from app.modules.users import application
from app.modules.users.models import User
from app.modules.users.schemas import FollowResponse


router = APIRouter(tags=["Follows"])


@router.put("/users/{user_id}/followers/me", response_model=FollowResponse, operation_id="users_follow")
def follow_user(
    user_id: str,
    current_user: User = Depends(require_active_verified_user),
    db: Session = Depends(get_db),
):
    return application.follow_user(db, current_user, user_id)


@router.delete("/users/{user_id}/followers/me", status_code=204, response_class=Response, operation_id="users_unfollow")
def unfollow_user(
    user_id: str,
    current_user: User = Depends(require_active_verified_user),
    db: Session = Depends(get_db),
):
    application.unfollow_user(db, current_user, user_id)
    return Response(status_code=204)
