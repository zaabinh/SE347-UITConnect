from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.modules.auth.dependencies import require_active_verified_user
from app.modules.comments import application
from app.modules.comments.schemas import CreateCommentRequest, CommentResponse
from app.modules.moderation.schemas import CreateReportRequest, ReportResponse
from app.modules.users.models import User


router = APIRouter(prefix='/posts/{post_id}/comments', tags=['Comments'])


@router.post('', response_model=CommentResponse, status_code=201, operation_id='comments_create')
def create_comment(post_id: int, payload: CreateCommentRequest, db: Session=Depends(get_db), current_user: User=Depends(require_active_verified_user)):
    return application.create_comment(post_id=post_id, payload=payload, db=db, current_user=current_user)


@router.get('', response_model=list[CommentResponse], operation_id='comments_list')
def get_comments(post_id: int, db: Session=Depends(get_db), current_user: User=Depends(require_active_verified_user)):
    return application.get_comments(post_id=post_id, db=db, current_user=current_user)


@router.post('/{comment_id}/reports', response_model=ReportResponse, status_code=201, operation_id='comments_create_report')
def report_comment(post_id: int, comment_id: int, payload: CreateReportRequest, db: Session=Depends(get_db), current_user: User=Depends(require_active_verified_user)):
    return application.report_comment(post_id=post_id, comment_id=comment_id, payload=payload, db=db, current_user=current_user)
