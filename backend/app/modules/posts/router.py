from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.modules.auth.dependencies import require_active_verified_user
from app.modules.users.models import User
from app.modules.posts.schemas import (
    CreatePostRequest, PostResponse, UpdatePostRequest, SharePostRequest,
    SharePostResponse, LikeResponse, BookmarkResponse,
)
from app.modules.posts.tag_schemas import TagResponse
from app.modules.moderation.schemas import CreateReportRequest, ReportResponse
from app.modules.posts import application


router = APIRouter(prefix="/posts", tags=["Posts"])
tag_router = APIRouter(prefix="/tags", tags=["Tags"])


@router.post("", response_model=PostResponse, status_code=201, operation_id="posts_create")
def create_post(payload: CreatePostRequest, response: Response, db: Session = Depends(get_db), current_user: User = Depends(require_active_verified_user)):
    post = application.create_post(db, current_user, payload)
    response.headers["Location"] = f"/api/v1/posts/{post.id}"
    return post


@tag_router.get("", response_model=list[TagResponse], operation_id="tags_list")
def get_tags(db: Session = Depends(get_db), current_user: User = Depends(require_active_verified_user)):
    return application.get_tags(db, current_user)


@router.get("/{post_id}", response_model=PostResponse, operation_id="posts_get_by_id")
def get_post_detail(post_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_active_verified_user)):
    return application.get_post_detail(db, current_user, post_id)


@router.post("/{post_id}/views", status_code=204, operation_id="posts_record_view")
def record_view(post_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_active_verified_user)):
    application.record_view(db, current_user, post_id)
    return Response(status_code=204)


@router.patch("/{post_id}", response_model=PostResponse, operation_id="posts_update")
def update_post(post_id: int, payload: UpdatePostRequest, db: Session = Depends(get_db), current_user: User = Depends(require_active_verified_user)):
    return application.update_post(db, current_user, post_id, payload)


@router.delete("/{post_id}", status_code=204, operation_id="posts_delete")
def delete_post(post_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_active_verified_user)):
    application.delete_post(db, current_user, post_id)
    return Response(status_code=204)


@router.put("/{post_id}/likes/me", response_model=LikeResponse, operation_id="posts_like")
def like_post(post_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_active_verified_user)):
    return application.set_like(db, current_user, post_id)


@router.delete("/{post_id}/likes/me", status_code=204, operation_id="posts_unlike")
def unlike_post(post_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_active_verified_user)):
    application.set_like(db, current_user, post_id, False)
    return Response(status_code=204)


@router.put("/{post_id}/bookmarks/me", response_model=BookmarkResponse, operation_id="posts_bookmark")
def bookmark_post(post_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_active_verified_user)):
    return application.set_bookmark(db, current_user, post_id)


@router.delete("/{post_id}/bookmarks/me", status_code=204, operation_id="posts_unbookmark")
def unbookmark_post(post_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_active_verified_user)):
    application.set_bookmark(db, current_user, post_id, False)
    return Response(status_code=204)


@router.post("/{post_id}/shares", response_model=SharePostResponse, status_code=201, operation_id="posts_share")
def share_post(post_id: int, response: Response, payload: SharePostRequest | None = None, db: Session = Depends(get_db), current_user: User = Depends(require_active_verified_user)):
    shared = application.share_post(db, current_user, post_id, payload)
    response.headers["Location"] = f"/api/v1/posts/{shared.post_id}"
    return shared


@router.post("/{post_id}/reports", response_model=ReportResponse, status_code=201, operation_id="posts_create_report")
def report_post(post_id: int, payload: CreateReportRequest, db: Session = Depends(get_db), current_user: User = Depends(require_active_verified_user)):
    return application.report_post(db, current_user, post_id, payload)
