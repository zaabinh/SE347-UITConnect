"""Versioned auth/profile transport and state-change checks."""

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import register_exception_handlers
from app.db.session import get_db
from app.modules.auth import router as auth
from app.modules.auth.application import AuthApplicationService
from app.modules.auth.dependencies import get_current_user, require_active_verified_user
from app.modules.auth.schemas import CompleteProfileRequest
from app.modules.comments.models import Comment
from app.modules.notifications.models import Notification
from app.modules.posts.models import Bookmark
from app.modules.users import application, follow_router, router as users
from app.modules.users.models import Follow
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UpdateProfileRequest
from test_users_transactions import users_db


def make_app():
    app = FastAPI()
    register_exception_handlers(app)
    for router in (auth.router, users.router, auth.profile_completion_router,
                   follow_router.router, auth.public_user_router):
        app.include_router(router, prefix="/api/v1")
    return app


@pytest.fixture
def client(users_db):
    db, (alice, _, _), _, _ = users_db
    app = make_app()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: alice
    app.dependency_overrides[require_active_verified_user] = lambda: alice
    with TestClient(app) as client:
        yield client


def test_auth_user_routes_match_frozen_contract():
    schema = make_app().openapi()
    endpoints = json.loads(Path(__file__).with_name("api_v1_contract.json").read_text())["endpoints"]
    expected = [item for item in endpoints if item["operation_id"].startswith(("auth_", "users_"))]
    assert sum(len(operations) for operations in schema["paths"].values()) == len(expected)
    for item in expected:
        operation = schema["paths"][item["path"]][item["method"].lower()]
        assert operation["operationId"] == item["operation_id"]
        response = operation["responses"][str(item["status"])]
        if item["response"] is None:
            assert "content" not in response
        else:
            response_schema = response["content"]["application/json"]["schema"]
            name = item["response"].removesuffix("[]")
            if item["response"].endswith("[]"):
                response_schema = response_schema["items"]
            assert response_schema["$ref"].endswith("/" + name)
        if item["request"]:
            request = operation["requestBody"]["content"]["application/json"]["schema"]
            assert request["$ref"].endswith("/" + item["request"])


def test_identity_is_private_but_user_lookup_is_public(client, users_db):
    _, (alice, bob, _), _, _ = users_db
    bob.username = None
    identity = client.get("/api/v1/auth/me").json()
    assert identity["email"] == alice.email
    assert identity["profile_completed"] is True
    public = client.get(f"/api/v1/users/{bob.id}")
    assert public.status_code == 200
    assert set(public.json()) == {"id", "username", "full_name", "avatar_url", "bio", "role"}
    assert public.json()["username"] is None
    profile = client.get("/api/v1/users/by-username/alice").json()
    assert not {"email", "status", "provider", "is_verified"} & profile.keys()
    assert client.get("/api/v1/users/me").json()["created_at"].endswith("Z")


def test_profile_patch_preserves_omissions_and_clears_nullable(client, users_db):
    db, (alice, _, _), _, _ = users_db
    alice.bio, alice.major, alice.interest_tags = "About", "CS", "python"
    db.commit()
    response = client.patch("/api/v1/users/me", json={"bio": None})
    assert response.status_code == 200
    assert response.json()["bio"] is None
    assert response.json()["full_name"] == "Alice"
    assert response.json()["major"] == "CS"
    assert response.json()["interest_tags"] == ["python"]
    response = client.patch("/api/v1/users/me", json={"interest_tags": []})
    assert response.json()["interest_tags"] == []
    assert alice.interest_tags is None


@pytest.mark.parametrize("payload", [
    {}, {"full_name": None}, {"full_name": " "}, {"full_name": "x" * 256},
    {"major": "x" * 121}, {"academic_year": "x" * 31}, {"career_goal": "x" * 201},
    {"interest_tags": None}, {"role": "admin"},
])
def test_invalid_profile_patch_is_problem_details(client, payload):
    response = client.patch("/api/v1/users/me", json=payload)
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_bookmarks_are_only_available_for_current_user(client, users_db):
    _, _, _, active = users_db
    response = client.get("/api/v1/users/me/bookmarks")
    assert [post["id"] for post in response.json()] == [active.id]
    assert response.json()[0]["created_at"].endswith("Z")
    assert client.get("/api/v1/users/by-username/alice/bookmarks").status_code == 404
    assert client.get("/api/v1/users/alice/bookmarks").status_code == 404


def test_profile_activity_hides_posts_viewer_cannot_access(users_db):
    db, (alice, bob, admin), draft, active = users_db
    db.add_all([
        Comment(user_id=alice.id, post_id=draft.id, content="Private", status="active"),
        Comment(user_id=alice.id, post_id=active.id, content="Public", status="active"),
        Bookmark(user_id=bob.id, post_id=draft.id),
        Bookmark(user_id=alice.id, post_id=draft.id),
    ])
    db.commit()
    assert [item.content for item in application.get_user_comments(db, bob, "alice")] == ["Public"]
    assert {item.content for item in application.get_user_comments(db, alice, "alice")} == {"Private", "Public"}
    assert {item.content for item in application.get_user_comments(db, admin, "alice")} == {"Private", "Public"}
    assert application.get_user_bookmarks(db, bob) == []
    assert {item.id for item in application.get_user_bookmarks(db, alice)} == {draft.id, active.id}


def test_follow_and_unfollow_are_idempotent_and_bodyless(client, users_db):
    db, (_, bob, _), _, _ = users_db
    path = f"/api/v1/users/{bob.id}/followers/me"
    for _ in range(2):
        response = client.put(path)
        assert response.status_code == 200
        assert response.json()["following"] is True
    assert db.query(Follow).count() == 1
    assert db.query(Notification).count() == 1
    for _ in range(2):
        response = client.delete(path)
        assert response.status_code == 204
        assert response.content == b""
    assert db.query(Follow).count() == 0


def test_follow_does_not_swallow_unrelated_integrity_failure(users_db, monkeypatch):
    db, (alice, bob, _), _, _ = users_db

    def invalid_notification(*args, **kwargs):
        raise IntegrityError("notification insert", {}, RuntimeError("invalid foreign key"))

    monkeypatch.setattr(application, "create_notification", invalid_notification)
    with pytest.raises(IntegrityError):
        application.follow_user(db, alice, bob.id)
    assert db.query(Follow).count() == 0


def test_duplicate_follow_race_succeeds_only_after_existing_membership_is_confirmed(users_db, monkeypatch):
    db, (alice, bob, _), _, _ = users_db
    db.add(Follow(follower_id=alice.id, following_id=bob.id))
    db.commit()
    real_follow = UserRepository.follow
    lookups = []

    def miss_first_lookup(repo, follower_id, following_id):
        lookups.append(True)
        if len(lookups) == 1:
            return None
        return real_follow(repo, follower_id, following_id)

    monkeypatch.setattr(UserRepository, "follow", miss_first_lookup)
    result = application.follow_user(db, alice, bob.id)
    assert result.following is True
    assert result.message == "Already following this user."
    assert len(lookups) == 2
    assert db.query(Follow).count() == 1
    assert db.query(Notification).count() == 0


def test_profile_patch_commit_failure_restores_fields(users_db):
    db, (alice, _, _), _, _ = users_db

    def fail_commit(session):
        session.flush()
        raise RuntimeError("commit failed")

    event.listen(db, "before_commit", fail_commit, once=True)
    with pytest.raises(RuntimeError, match="commit failed"):
        application.update_my_profile(db, alice, UpdateProfileRequest(bio="new"))
    assert alice.bio is None
    assert alice.full_name == "Alice"


def test_onboarding_routes_accept_authenticated_incomplete_user(client, users_db):
    db, (alice, _, _), _, _ = users_db
    alice.username = None
    db.commit()
    # Keep active-user dependency intact so the distinct onboarding security is exercised.
    client.app.dependency_overrides.pop(require_active_verified_user)
    assert client.get("/api/v1/auth/me").json()["profile_completed"] is False
    assert client.get("/api/v1/users/me").status_code == 403
    response = client.put("/api/v1/users/me/profile-completion", json={
        "username": "alice", "full_name": "Alice Updated",
    })
    assert response.status_code == 200
    assert response.json()["profile_completed"] is True
    assert client.get("/api/v1/users/me").status_code == 200


def test_logout_is_bodyless_and_forgot_password_is_generic_queued(client, monkeypatch):
    calls = []
    monkeypatch.setattr(AuthApplicationService, "logout", lambda self, token: calls.append(token))
    monkeypatch.setattr(AuthApplicationService, "forgot_password", lambda self, email: calls.append(email))
    response = client.post("/api/v1/auth/logout", json={"refresh_token": "refresh-token"})
    assert response.status_code == 204
    assert response.content == b""
    response = client.post("/api/v1/auth/forgot-password", json={"email": "unknown@example.com"})
    assert response.status_code == 202
    assert "queued" in response.json()["message"]
    assert set(response.json()) == {"message"}
    assert calls == ["refresh-token", "unknown@example.com"]


def test_google_endpoints_return_declared_redirects(client, monkeypatch):
    target = "https://accounts.google.com/example"
    monkeypatch.setattr(AuthApplicationService, "google_login", staticmethod(lambda: target))
    monkeypatch.setattr(AuthApplicationService, "google_callback", lambda self, *args, **kwargs: target)
    for path in ("/google/login", "/google/callback?code=code"):
        response = client.get("/api/v1/auth" + path, follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == target
        assert response.content == b""


@pytest.mark.parametrize("request_type", [UpdateProfileRequest, CompleteProfileRequest])
def test_profile_requests_apply_database_limits_and_reject_unknown_fields(request_type):
    from pydantic import ValidationError

    valid = {"full_name": "Student"}
    if request_type is CompleteProfileRequest:
        valid["username"] = "student"
    for invalid in ({"major": "x" * 121}, {"role": "admin"}):
        with pytest.raises(ValidationError):
            request_type(**(valid | invalid))
