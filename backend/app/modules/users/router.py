from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import require_active_verified_user
from app.modules.users import application
from app.modules.users.models import User
# Re-export schema names previously imported from this router.
from app.modules.users.schemas import (
    CurrentProfileResponse,
    ProfileResponse,
    UpdateProfileRequest,
    UserCommentResponse,
    UserPostResponse,
)


router = APIRouter(tags=["Users"])


@router.get("/users/me", response_model=CurrentProfileResponse)
def get_my_profile(current_user: User = Depends(require_active_verified_user), db: Session = Depends(get_db)):
    return application.get_my_profile(db, current_user)


@router.put("/users/me", response_model=CurrentProfileResponse)
def update_my_profile(
    payload: UpdateProfileRequest,
    current_user: User = Depends(require_active_verified_user),
    db: Session = Depends(get_db),
):
    return application.update_my_profile(db, current_user, payload)


@router.get("/users/{username}", response_model=ProfileResponse)
def get_user_profile(
    username: str,
    current_user: User = Depends(require_active_verified_user),
    db: Session = Depends(get_db),
):
    return application.get_user_profile(db, current_user, username)


@router.get("/users/{username}/posts", response_model=list[UserPostResponse])
def get_user_posts(
    username: str,
    current_user: User = Depends(require_active_verified_user),
    db: Session = Depends(get_db),
):
    return application.get_user_posts(db, current_user, username)


@router.get("/users/{username}/comments", response_model=list[UserCommentResponse])
def get_user_comments(
    username: str,
    current_user: User = Depends(require_active_verified_user),
    db: Session = Depends(get_db),
):
    return application.get_user_comments(db, current_user, username)


@router.get("/users/{username}/bookmarks", response_model=list[UserPostResponse])
def get_user_bookmarks(
    username: str,
    current_user: User = Depends(require_active_verified_user),
    db: Session = Depends(get_db),
):
    return application.get_user_bookmarks(db, current_user, username)
