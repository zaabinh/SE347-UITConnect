from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import require_active_verified_user
from app.modules.users import application
from app.modules.users.models import User
from app.modules.users.schemas import FollowResponse


router = APIRouter(tags=["Follows"])


@router.post("/follow/{user_id}", response_model=FollowResponse, status_code=status.HTTP_201_CREATED)
def follow_user(
    user_id: str,
    current_user: User = Depends(require_active_verified_user),
    db: Session = Depends(get_db),
):
    return application.follow_user(db, current_user, user_id)


@router.delete("/follow/{user_id}", response_model=FollowResponse)
def unfollow_user(
    user_id: str,
    current_user: User = Depends(require_active_verified_user),
    db: Session = Depends(get_db),
):
    return application.unfollow_user(db, current_user, user_id)
