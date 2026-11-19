from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.schemas import PaginationMeta, UtcDateTime
from app.db.session import get_db
from app.modules.auth.dependencies import require_role
from app.modules.moderation import application
from app.modules.moderation.schemas import ModerateReportRequest, ReportResponse, ModeratePostRequest, BanUserRequest
from app.modules.posts.tag_schemas import CreateTagRequest, TagResponse, UpdateTagRequest
from app.modules.users.models import User


router = APIRouter(prefix="/admin", tags=["Admin"])


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str | None
    email: str
    full_name: str
    role: str
    status: str
    created_at: UtcDateTime


class AdminUsersListResponse(BaseModel):
    items: list[AdminUserResponse]
    meta: PaginationMeta


class AdminReportsListResponse(BaseModel):
    items: list[ReportResponse]
    meta: PaginationMeta


class AdminPostModerationResponse(BaseModel):
    id: int
    user_id: str
    title: str
    status: str
    requested_new_tags: list[str] = []
    created_at: UtcDateTime


class AdminPostsListResponse(BaseModel):
    items: list[AdminPostModerationResponse]
    meta: PaginationMeta


class AdminAnalyticsResponse(BaseModel):
    users_today: int
    users_week: int
    posts_today: int
    posts_week: int
    comments_today: int
    comments_week: int
    reports_today: int
    reports_week: int
    pending_reports: int
    pending_posts: int


@router.get("/users", response_model=AdminUsersListResponse, operation_id="admin_list_users")
def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, pattern="^(active|banned|deleted)$"),
    sort_by: str = Query(default="created_at", pattern="^(created_at|username|email)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    return AdminUsersListResponse(**application.list_users(db, page, page_size, search, status_filter, sort_by, sort_order))


@router.put("/users/{user_id}/ban", response_model=AdminUserResponse, operation_id="admin_ban_user")
def ban_user(
    user_id: str,
    payload: BanUserRequest,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    return application.ban_user(db, current_user, user_id, payload.reason)


@router.delete("/users/{user_id}/ban", response_model=AdminUserResponse, operation_id="admin_unban_user")
def unban_user(
    user_id: str,
    reason: str | None = Query(default=None),
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    return application.unban_user(db, current_user, user_id, reason)


@router.get("/reports", response_model=AdminReportsListResponse, operation_id="admin_list_reports")
def list_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, pattern="^(pending|reviewed|dismissed|resolved)$"),
    reason: str | None = Query(default=None),
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    return AdminReportsListResponse(**application.list_reports(db, page, page_size, status_filter, reason))


@router.put("/reports/{report_id}/moderation", response_model=ReportResponse, operation_id="admin_moderate_report")
def moderate_report(
    report_id: int,
    payload: ModerateReportRequest,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    return application.moderate_report(db, current_user, report_id, payload)


@router.get("/posts/pending", response_model=AdminPostsListResponse, operation_id="admin_list_pending_posts")
def list_pending_posts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    return AdminPostsListResponse(**application.list_pending_posts(db, page, page_size))


@router.put("/posts/{post_id}/moderation", response_model=AdminPostModerationResponse, operation_id="admin_moderate_post")
def moderate_post(
    post_id: int,
    payload: ModeratePostRequest,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    return application.moderate_post(db, current_user, post_id, payload.status)


@router.get("/analytics/overview", response_model=AdminAnalyticsResponse, operation_id="admin_get_analytics")
def analytics_overview(
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    return AdminAnalyticsResponse(**application.analytics_overview(db))


@router.get("/tags", response_model=list[TagResponse], operation_id="admin_list_tags")
def list_tags(
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    return application.list_tags(db)


@router.post("/tags", response_model=TagResponse, status_code=status.HTTP_201_CREATED, operation_id="admin_create_tag")
def create_tag(
    payload: CreateTagRequest,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    return application.create_tag(db, payload)


@router.patch("/tags/{tag_id}", response_model=TagResponse, operation_id="admin_update_tag")
def update_tag(
    tag_id: int,
    payload: UpdateTagRequest,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    return application.update_tag(db, tag_id, payload)


@router.delete("/tags/{tag_id}", status_code=204, operation_id="admin_delete_tag")
def delete_tag(
    tag_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    application.delete_tag(db, tag_id)
    return Response(status_code=204)
