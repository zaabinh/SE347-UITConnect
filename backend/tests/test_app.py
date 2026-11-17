import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import configure_mappers

from app.db.base import Base
from app.db.session import engine
from app.main import app


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
    assert len(Base.metadata.tables) == 16
    for table in Base.metadata.tables.values():
        for foreign_key in table.foreign_keys:
            assert foreign_key.column.table.metadata is Base.metadata


def test_startup_health_and_openapi(monkeypatch):
    created_with = []
    monkeypatch.setattr(Base.metadata, "create_all", lambda bind: created_with.append(bind))
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "healthy"
        assert client.get("/").status_code == 200
        assert client.get("/openapi.json").status_code == 200
        response = client.get("/api/posts/feed")
        assert response.status_code == 401
        assert response.json()["detail"] == "Authentication credentials were not provided."
    assert created_with == [engine]
