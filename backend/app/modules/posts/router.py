from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.modules.auth.dependencies import require_active_verified_user
from app.modules.users.models import User
from app.modules.auth.schemas import MessageResponse
from app.modules.posts.schemas import PostCreate, PostResponse, PostUpdate, SharePostRequest
from app.modules.moderation.schemas import ReportCreate, ReportResponse
from app.modules.posts import application


router = APIRouter(prefix="/posts", tags=["Posts"])

@router.post("/", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def create_post(payload: PostCreate, db: Session = Depends(get_db), current_user: User = Depends(require_active_verified_user)):
    return application.create_post(db, current_user, payload)


@router.get("/tags")
def get_tags(db: Session = Depends(get_db), current_user: User = Depends(require_active_verified_user)):
    return application.get_tags(db, current_user)


@router.get("/{post_id}", response_model=PostResponse)
def get_post_detail(post_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_active_verified_user)):
    return application.get_post_detail(db, current_user, post_id)


@router.put("/{post_id}", response_model=PostResponse)
def update_post(post_id: int, payload: PostUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_active_verified_user)):
    return application.update_post(db, current_user, post_id, payload)


@router.delete("/{post_id}", response_model=MessageResponse)
def delete_post(post_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_active_verified_user)):
    return application.delete_post(db, current_user, post_id)


@router.post("/{post_id}/like", response_model=MessageResponse)
def toggle_like(post_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_active_verified_user)):
    return application.toggle_like(db, current_user, post_id)


@router.post("/{post_id}/bookmark", response_model=MessageResponse)
def toggle_bookmark(post_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_active_verified_user)):
    return application.toggle_bookmark(db, current_user, post_id)


@router.post("/{post_id}/share", response_model=MessageResponse)
def share_post(
    post_id: int,
    payload: SharePostRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_verified_user),
):
    return application.share_post(db, current_user, post_id, payload)


@router.post("/{post_id}/report", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def report_post(post_id: int, payload: ReportCreate, db: Session = Depends(get_db), current_user: User = Depends(require_active_verified_user)):
    return application.report_post(db, current_user, post_id, payload)
