"""Application errors and safe HTTP exception responses."""

import logging

from fastapi import FastAPI, Request
from http import HTTPStatus
from uuid import uuid4
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from app.core.schemas import ProblemDetails

logger = logging.getLogger("uvicorn.error")


class ConfigurationError(RuntimeError):
    """Required runtime configuration is missing or invalid."""


class ApplicationError(Exception):
    """A transport-independent use case rejection."""

    def __init__(self, status_code: int, detail: str, code: str | None = None):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.code = code


def problem(request, status, detail, code=None, errors=None, headers=None):
    request_id = getattr(request.state, 'request_id', None) or str(uuid4())
    request.state.request_id = request_id
    try:
        title = HTTPStatus(status).phrase
    except ValueError:
        title = 'Request failed'
    codes = {400: 'BAD_REQUEST', 401: 'UNAUTHORIZED', 403: 'FORBIDDEN', 404: 'NOT_FOUND',
             405: 'METHOD_NOT_ALLOWED', 409: 'CONFLICT', 413: 'PAYLOAD_TOO_LARGE',
             422: 'VALIDATION_ERROR', 429: 'RATE_LIMITED', 500: 'INTERNAL_ERROR'}
    payload = ProblemDetails(type='about:blank', title=title, status=status,
                             detail='Internal server error.' if status >= 500 else detail,
                             instance=request.url.path, code=code or codes.get(status, f'HTTP_{status}'),
                             request_id=request_id, errors=errors)
    response_headers = dict(headers or {})
    response_headers['X-Request-ID'] = request_id
    if status == 401:
        response_headers.setdefault('WWW-Authenticate', 'Bearer')
    return JSONResponse(status_code=status, content=payload.model_dump(exclude_none=True),
                        media_type='application/problem+json', headers=response_headers)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return problem(request, exc.status_code, exc.detail if isinstance(exc.detail, str) else 'Request failed.', headers=exc.headers)


async def application_exception_handler(request: Request, exc: ApplicationError) -> JSONResponse:
    return problem(request, exc.status_code, exc.detail, exc.code)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Input and validation context may contain passwords or other private values.
    errors = [{'loc': list(error['loc']), 'type': error['type'],
               'msg': 'Field required.' if error['type'] == 'missing' else 'Invalid value.'} for error in exc.errors()]
    return problem(request, 422, 'Request validation failed.', errors=errors)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled error during %s %s",
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    response = problem(request, 500, 'Internal server error.')
    # ServerErrorMiddleware sits outside CORSMiddleware, so its responses need CORS here.
    origin = request.headers.get("origin")
    if origin in request.app.state.settings.cors_allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers.add_vary_header("Origin")
    return response


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApplicationError, application_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
