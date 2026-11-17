"""Student Forum Backend entrypoint."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import UPLOAD_DIR, get_cors_origins
from app.db.base import Base
from app.db.session import engine
from app.modules.auth import router as auth
from app.modules.users import router as user, follow_router as follow
from app.modules.posts import router as post, upload_router as upload
from app.modules.comments import router as comment
from app.modules.moderation import router as admin
from app.modules.feed import router as feed
from app.modules.notifications import router as notifications


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    print("Student Forum API starting...")
    yield
    print("Student Forum API shutting down...")


app = FastAPI(
    title="Student Forum API",
    description="Backend for student forum system",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth")
app.include_router(user.router)
app.include_router(feed.router, prefix="/api")
app.include_router(post.router, prefix="/api")
app.include_router(notifications.router)
app.include_router(comment.router, prefix="/api")
app.include_router(follow.router)
app.include_router(admin.router, prefix="/api")
app.include_router(upload.router)
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Student Forum API is running"}


@app.get("/")
async def root():
    return {
        "message": "Welcome to Student Forum API",
        "version": "1.0.0",
        "docs": "/docs",
        "openapi_schema": "/openapi.json",
    }


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8000"))
    uvicorn.run("app.main:app", host=host, port=port, reload=True, log_level="info")
