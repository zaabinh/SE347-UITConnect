"""Assemble domain routers without business logic or transaction ownership."""

from fastapi import APIRouter

from app.core.schemas import ProblemDetails
from app.modules.auth import router as auth
from app.modules.comments import router as comments
from app.modules.feed import router as feed
from app.modules.moderation import router as moderation
from app.modules.notifications import router as notifications
from app.modules.posts import router as posts
from app.modules.users import router as users, follow_router as follows
from app.modules.media import router as media

ERROR_RESPONSES = {
    status: {'model': ProblemDetails, 'description': description}
    for status, description in {
        400: 'Invalid business request', 401: 'Authentication required or invalid',
        403: 'Insufficient permission', 404: 'Resource not found', 409: 'State conflict',
        413: 'Upload too large', 422: 'Request validation failed',
        429: 'Request rate limited', 500: 'Internal server error',
    }.items()
}

router = APIRouter(prefix='/api/v1', responses=ERROR_RESPONSES)
router.include_router(auth.router)
router.include_router(auth.profile_completion_router)
router.include_router(users.router)
router.include_router(follows.router)
router.include_router(auth.public_user_router)
router.include_router(feed.router)
router.include_router(posts.tag_router)
router.include_router(posts.router)
router.include_router(comments.router)
router.include_router(notifications.router)
router.include_router(moderation.router)
router.include_router(media.router)
