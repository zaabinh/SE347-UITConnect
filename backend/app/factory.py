"""Build the API without opening connections or writing to the filesystem."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.lifespan import lifespan
from app.modules.auth import router as auth
from app.modules.comments import router as comment
from app.modules.feed import router as feed
from app.modules.moderation import router as admin
from app.modules.notifications import router as notifications
from app.modules.posts import router as post, upload_router as upload
from app.modules.users import router as user, follow_router as follow


async def health_check():
    return {"status": "healthy", "message": "Student Forum API is running"}


async def root():
    return {
        "message": "Welcome to Student Forum API",
        "version": "1.0.0",
        "docs": "/docs",
        "openapi_schema": "/openapi.json",
    }


def register_middleware(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def register_routers(app: FastAPI) -> None:
    app.include_router(auth.router, prefix="/auth")
    app.include_router(user.router)
    # Static paths such as /posts/feed must precede /posts/{post_id}.
    app.include_router(feed.router, prefix="/api")
    app.include_router(post.router, prefix="/api")
    app.include_router(notifications.router)
    app.include_router(comment.router, prefix="/api")
    app.include_router(follow.router)
    app.include_router(admin.router, prefix="/api")
    app.include_router(upload.router)
    app.add_api_route("/health", health_check, methods=["GET"])
    app.add_api_route("/", root, methods=["GET"])


def create_app() -> FastAPI:
    app = FastAPI(
        title="Student Forum API",
        description="Backend for student forum system",
        version="1.0.0",
        debug=False,
        lifespan=lifespan,
    )
    app.state.settings = settings
    register_middleware(app)
    register_exception_handlers(app)
    register_routers(app)
    # Lifespan creates the directory before requests are accepted.
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir, check_dir=False), name="uploads")
    return app
