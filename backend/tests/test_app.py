import json
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import configure_mappers

from app import factory
from app.core import lifespan as lifecycle
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.main import app


@pytest.fixture
def runtime_app(monkeypatch, tmp_path):
    upload_dir = tmp_path / "uploads"
    config = settings.model_copy(update={"upload_dir": str(upload_dir)})
    monkeypatch.setattr(factory, "settings", config)
    database = MagicMock()
    monkeypatch.setattr(lifecycle, "engine", database)
    monkeypatch.setattr(Base.metadata, "create_all", Mock(side_effect=AssertionError("DDL during startup")))
    return factory.create_app(), database, upload_dir


def test_public_routes_are_preserved():
    expected = json.loads(Path(__file__).with_name("api_routes.json").read_text())
    actual = sorted(
        [method.upper(), path]
        for path, operations in app.openapi()["paths"].items()
        if path not in {"/", "/health"}
        for method in operations
        if method in {"get", "post", "put", "patch", "delete", "head", "options"}
    )
    assert actual == expected


def test_all_models_share_one_registry():
    configure_mappers()
    assert len(Base.metadata.tables) == 18
    assert "media" in Base.metadata.tables
    for table in Base.metadata.tables.values():
        for foreign_key in table.foreign_keys:
            assert foreign_key.column.table.metadata is Base.metadata


def test_factory_creates_independent_apps_without_io(monkeypatch):
    connect = Mock(side_effect=AssertionError("DB connection during app construction"))
    mkdir = Mock(side_effect=AssertionError("Filesystem write during app construction"))
    monkeypatch.setattr(engine, "connect", connect)
    monkeypatch.setattr(Path, "mkdir", mkdir)
    first = factory.create_app()
    second = factory.create_app()
    assert first is not second
    assert first.debug is False
    assert first.openapi()["paths"] == second.openapi()["paths"]
    assert len(first.user_middleware) == len(second.user_middleware) == 1
    first.add_api_route("/only-first", lambda: {})
    assert "/only-first" not in second.openapi()["paths"]
    connect.assert_not_called()
    mkdir.assert_not_called()


def test_startup_health_and_openapi(runtime_app):
    application, database, upload_dir = runtime_app
    assert not upload_dir.exists()
    with TestClient(application) as client:
        assert upload_dir.is_dir()
        connection = database.connect.return_value.__enter__.return_value
        assert str(connection.execute.call_args.args[0]) == "SELECT 1"
        database.dispose.assert_not_called()
        assert client.get("/health").json()["status"] == "healthy"
        assert client.get("/").status_code == 200
        assert client.get("/openapi.json").status_code == 200
        response = client.get("/api/posts/feed")
        assert response.status_code == 401
        assert response.json()["detail"] == "Authentication credentials were not provided."
    database.dispose.assert_called_once_with()


def test_failed_startup_releases_database_resources(runtime_app):
    application, database, _ = runtime_app
    database.connect.side_effect = RuntimeError("Database unavailable")
    with pytest.raises(RuntimeError, match="Database unavailable"):
        with TestClient(application):
            pytest.fail("Application accepted requests after failed startup")
    database.dispose.assert_called_once_with()


def test_static_uploads_are_available_after_startup(runtime_app):
    application, _, upload_dir = runtime_app
    with TestClient(application) as client:
        (upload_dir / "example.txt").write_text("uploaded content")
        response = client.get("/uploads/example.txt")
        assert response.status_code == 200
        assert response.text == "uploaded content"


def test_http_errors_keep_status_detail_and_headers(runtime_app):
    application, _, _ = runtime_app

    @application.get("/test-rate-limit")
    def rate_limit():
        raise HTTPException(429, "Try again later.", headers={"Retry-After": "30"})

    with TestClient(application) as client:
        response = client.get("/test-rate-limit")
        assert response.status_code == 429
        assert response.json() == {"detail": "Try again later."}
        assert response.headers["Retry-After"] == "30"
        assert client.get("/missing").json() == {"detail": "Not Found"}


def test_validation_errors_do_not_echo_credentials(runtime_app):
    application, _, _ = runtime_app
    with TestClient(application) as client:
        response = client.post("/auth/register", json={
            "username": "valid-user",
            "email": "invalid-private-email",
            "password": "s3cr!",
            "full_name": "Test User",
        })
    assert response.status_code == 422
    assert "invalid-private-email" not in response.text
    assert "s3cr!" not in response.text
    for error in response.json()["detail"]:
        assert set(error) == {"loc", "msg", "type"}


@pytest.mark.parametrize("origin", [None, "https://untrusted.example"])
def test_unhandled_errors_are_generic_logged_and_respect_cors(runtime_app, caplog, origin):
    application, _, _ = runtime_app
    origin = origin or settings.cors_allowed_origins[0]

    @application.get("/test-internal-error")
    def internal_error():
        raise RuntimeError("private internal information")

    with TestClient(application, raise_server_exceptions=False) as client:
        response = client.get("/test-internal-error", headers={"Origin": origin})
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error."}
    assert "private internal information" not in response.text
    assert any(record.exc_info for record in caplog.records if "Unhandled error" in record.message)
    if origin in settings.cors_allowed_origins:
        assert response.headers["Access-Control-Allow-Origin"] == origin
        assert response.headers["Access-Control-Allow-Credentials"] == "true"
        assert "Origin" in response.headers["Vary"]
    else:
        assert "Access-Control-Allow-Origin" not in response.headers


def test_cors_preflight_is_registered(runtime_app):
    application, _, _ = runtime_app
    origin = settings.cors_allowed_origins[0]
    with TestClient(application) as client:
        response = client.options("/api/posts/feed", headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        })
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == origin
