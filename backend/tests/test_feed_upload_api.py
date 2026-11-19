"""HTTP checks backed by SQLite and real temporary upload files."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.db.session import get_db
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.modules.feed.router import router as feed_router
from app.modules.media.router import router as media_router
from app.modules.notifications.router import router as notifications_router
from app.modules.auth.dependencies import require_active_verified_user
from app.modules.media import application as upload_application
from app.modules.posts.models import Post, PostLike, PostTag
from test_posts_transactions import posts_db  # noqa: F401 - reuse the real database fixture


PNG = b'\x89PNG\r\n\x1a\nimage bytes'
JPEG = b'\xff\xd8\xffimage bytes'


def create_discovery_app():
    app = FastAPI(redirect_slashes=False)
    app.state.settings = settings
    register_exception_handlers(app)
    for router in (feed_router, media_router, notifications_router):
        app.include_router(router, prefix='/api/v1')
    return app


@pytest.fixture
def feed_client(posts_db):
    db, _, sharer, follower, original = posts_db
    second = Post(user_id=sharer.id, title="Python followup", slug="python-followup",
                  content="Original body", status="active")
    hidden = Post(user_id=sharer.id, title="Pending python", slug="pending-python",
                  content="Original body", status="pending")
    db.add_all([second, hidden])
    db.flush()
    db.add(PostTag(post_id=second.id, tag_id=original.tags[0].tag_id))
    db.commit()
    app = create_discovery_app()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_active_verified_user] = lambda: follower
    client = TestClient(app)
    yield client, db, follower, original, second
    client.close()


@pytest.mark.parametrize("query", ["", "?sort=most-liked", "?sort=most-commented", "?mode=trending"])
def test_feed_returns_only_active_posts_with_pagination_without_commit(feed_client, query):
    client, db, _, original, second = feed_client
    commits = []
    event.listen(db, "after_commit", lambda _: commits.append(True))
    response = client.get(f"/api/v1/feed{query}")
    assert response.status_code == 200
    body = response.json()
    assert {item["id"] for item in body["items"]} == {original.id, second.id}
    assert body["meta"] == {"page": 1, "page_size": 10, "total": 2, "total_pages": 1}
    assert commits == []


def test_feed_search_following_and_empty_tag_filters(feed_client):
    client, _, _, _, second = feed_client
    for query in ["search=followup", "mode=following", "tag=python&search=followup"]:
        response = client.get(f"/api/v1/feed?{query}")
        assert response.status_code == 200
        assert [item["id"] for item in response.json()["items"]] == [second.id]
    missing = client.get("/api/v1/feed?tag=missing").json()
    assert missing["items"] == []
    assert missing["meta"]["total"] == 0


def test_trending_and_similar_responses_preserve_scores_flags_and_vietnamese_reasons(feed_client):
    client, db, user, original, second = feed_client
    db.add(PostLike(post_id=original.id, user_id=user.id))
    db.commit()
    trending = client.get("/api/v1/recommendations/trending?tag=python")
    assert trending.status_code == 200
    top = trending.json()["items"][0]
    assert top["post"]["id"] == original.id
    assert top["post"]["is_liked"] is True
    assert top["trend_rank"] == 1
    assert top["hot_score"] > 0
    assert top["trending_reason"] == "Nổi bật do yêu thích"
    similar = client.get(f"/api/v1/recommendations/posts/{original.id}/similar")
    assert similar.status_code == 200
    item = similar.json()["items"][0]
    assert item["post"]["id"] == second.id
    assert 0 < item["similarity_score"] <= 1
    assert item["similarity_reason"] == "Cùng chủ đề"


def test_profile_recommendations_summary_and_analysis_use_existing_rules(feed_client):
    client, db, user, original, second = feed_client
    user.interest_tags = "python"
    user.major = "software engineering"
    db.commit()
    recommendations = client.get("/api/v1/recommendations/profile")
    assert recommendations.status_code == 200
    assert {item["post"]["id"] for item in recommendations.json()["items"]} == {original.id, second.id}
    assert all(item["recommendation_reason"] == "Liên quan đến sở thích của bạn" for item in recommendations.json()["items"])
    summary = client.get("/api/v1/recommendations/profile-summary")
    assert summary.status_code == 200
    assert summary.json()["interest_tags"] == ["python"]
    assert summary.json()["profile_strength"] == 0.4
    assert summary.json()["recommendations_count"] == 2
    analysis = client.get("/api/v1/recommendations/profile-analysis")
    assert analysis.status_code == 200
    assert analysis.json()["recommendation_message"] == "Hoàn thành profile bằng cách cập nhật: mục tiêu sự nghiệp để nhận được gợi ý chính xác hơn."


def test_collaborative_endpoint_handles_no_similar_users(feed_client):
    client, _, _, _, _ = feed_client
    response = client.get("/api/v1/recommendations/collaborative?min_similarity=1")
    assert response.status_code == 200
    assert response.json() == {"items": [], "meta": {"page": 1, "page_size": 10, "total": 0, "total_pages": 0}}


@pytest.mark.parametrize("query", ["page=0", "page_size=51", "mode=unknown", "sort=unknown"])
def test_feed_keeps_query_validation(feed_client, query):
    client, _, _, _, _ = feed_client
    assert client.get(f"/api/v1/feed?{query}").status_code == 422


def test_feed_still_requires_authentication():
    client = TestClient(create_discovery_app())
    response = client.get("/api/v1/feed")
    assert response.status_code == 401
    client.close()


@pytest.fixture
def upload_client(tmp_path, monkeypatch):
    destination = tmp_path / "images"
    monkeypatch.setattr(upload_application, "UPLOAD_DIR", str(destination))
    monkeypatch.setattr(upload_application, "PUBLIC_API_URL", "")
    app = create_discovery_app()
    app.dependency_overrides[require_active_verified_user] = lambda: object()
    client = TestClient(app)
    yield client, destination
    client.close()


@pytest.mark.parametrize("public_url", ["", "https://cdn.example.com"])
def test_image_upload_saves_bytes_and_uses_configured_public_url(upload_client, monkeypatch, public_url):
    client, destination = upload_client
    monkeypatch.setattr(upload_application, "PUBLIC_API_URL", public_url)
    response = client.post("/api/v1/media/images", files={"file": ("untrusted.exe", PNG, "image/png")})
    assert response.status_code == 201
    url = response.json()["url"]
    assert url.startswith(f"{public_url or 'http://testserver'}/uploads/")
    assert url.endswith(".png")
    assert (destination / Path(url).name).read_bytes() == PNG


def test_upload_rejects_other_content_types_without_writing(upload_client):
    client, destination = upload_client
    response = client.post("/api/v1/media/images", files={"file": ("image.gif", b"bytes", "image/gif")})
    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "BAD_REQUEST"
    assert not destination.exists()


def test_upload_hides_filesystem_failures_and_cleans_partial_file(upload_client, monkeypatch):
    client, destination = upload_client
    from io import BytesIO

    class FailingStream(BytesIO):
        def read(self, size):
            if self.tell():
                raise OSError("private filesystem path")
            return super().read(size)

    # Fail after the initial chunk has been written to disk.
    def failing_upload(file, base_url):
        file.file = FailingStream(JPEG)
        return original_upload(file, base_url)

    original_upload = upload_application.upload_image
    monkeypatch.setattr(upload_application, "upload_image", failing_upload)
    response = client.post("/api/v1/media/images", files={"file": ("image.jpg", JPEG, "image/jpeg")})
    assert response.status_code == 500
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"] == "Internal server error."
    assert "filesystem" not in response.text
    assert list(destination.iterdir()) == []
