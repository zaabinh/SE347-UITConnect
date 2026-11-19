from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.modules.auth.dependencies import require_active_verified_user
from app.modules.comments import application
from app.modules.comments.schemas import CommentCreate, CommentResponse
from app.modules.moderation.schemas import ReportCreate, ReportResponse
from app.modules.users.models import User


router = APIRouter(prefix='/posts/{post_id}/comments', tags=['Comments'])


@router.post('/', response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def create_comment(post_id: int, payload: CommentCreate, db: Session=Depends(get_db), current_user: User=Depends(require_active_verified_user)):
    return application.create_comment(post_id=post_id, payload=payload, db=db, current_user=current_user)


@router.get('/', response_model=list[CommentResponse])
def get_comments(post_id: int, db: Session=Depends(get_db), current_user: User=Depends(require_active_verified_user)):
    return application.get_comments(post_id=post_id, db=db, current_user=current_user)


@router.post('/{comment_id}/report', response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def report_comment(post_id: int, comment_id: int, payload: ReportCreate, db: Session=Depends(get_db), current_user: User=Depends(require_active_verified_user)):
    return application.report_comment(post_id=post_id, comment_id=comment_id, payload=payload, db=db, current_user=current_user)
