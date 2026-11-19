"""Build the API without opening connections or writing to the filesystem."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.lifespan import lifespan
from app.core.middleware import RequestIdMiddleware
from app.core.schemas import HealthResponse, RootResponse
from app.api.v1.router import router as api_router
from app.api.openapi import configure_openapi


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
        expose_headers=['X-Request-ID', 'Location'],
    )
    app.add_middleware(RequestIdMiddleware)


def register_routers(app: FastAPI) -> None:
    app.include_router(api_router)
    app.add_api_route('/health', health_check, methods=['GET'], response_model=HealthResponse, operation_id='system_health')
    app.add_api_route('/', root, methods=['GET'], response_model=RootResponse, operation_id='system_root')


def create_app() -> FastAPI:
    app = FastAPI(
        title="UITConnect V2 REST API",
        description="REST API v1; authoritative reference: docs/API_CONTRACT.md",
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
    configure_openapi(app)
    return app
