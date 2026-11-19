"""HTTP checks backed by SQLite and real temporary upload files."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.db.session import get_db
from app.factory import create_app
from app.modules.auth.dependencies import require_active_verified_user
from app.modules.posts import upload_application
from app.modules.posts.models import Post, PostLike, PostTag
from test_posts_transactions import posts_db  # noqa: F401 - reuse the real database fixture


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
    app = create_app()
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
    response = client.get(f"/api/posts/feed{query}")
    assert response.status_code == 200
    body = response.json()
    assert {item["id"] for item in body["items"]} == {original.id, second.id}
    assert body["meta"] == {"page": 1, "page_size": 10, "total": 2, "total_pages": 1}
    assert commits == []


def test_feed_search_following_and_empty_tag_filters(feed_client):
    client, _, _, _, second = feed_client
    for query in ["search=followup", "mode=following", "tag=python&search=followup"]:
        response = client.get(f"/api/posts/feed?{query}")
        assert response.status_code == 200
        assert [item["id"] for item in response.json()["items"]] == [second.id]
    missing = client.get("/api/posts/feed?tag=missing").json()
    assert missing["items"] == []
    assert missing["meta"]["total"] == 0


def test_trending_and_similar_responses_preserve_scores_flags_and_vietnamese_reasons(feed_client):
    client, db, user, original, second = feed_client
    db.add(PostLike(post_id=original.id, user_id=user.id))
    db.commit()
    trending = client.get("/api/posts/trending/suggestions?tag=python")
    assert trending.status_code == 200
    top = trending.json()["items"][0]
    assert top["post"]["id"] == original.id
    assert top["post"]["is_liked"] is True
    assert top["trend_rank"] == 1
    assert top["hot_score"] > 0
    assert top["trending_reason"] == "Nổi bật do yêu thích"
    similar = client.get(f"/api/posts/{original.id}/similar")
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
    recommendations = client.get("/api/posts/recommendations/profile")
    assert recommendations.status_code == 200
    assert {item["post"]["id"] for item in recommendations.json()["items"]} == {original.id, second.id}
    assert all(item["recommendation_reason"] == "Liên quan đến sở thích của bạn" for item in recommendations.json()["items"])
    summary = client.get("/api/posts/profile/summary")
    assert summary.status_code == 200
    assert summary.json()["interest_tags"] == ["python"]
    assert summary.json()["profile_strength"] == 0.4
    assert summary.json()["recommendations_count"] == 2
    analysis = client.get("/api/posts/profile/analysis")
    assert analysis.status_code == 200
    assert analysis.json()["recommendation_message"] == "Hoàn thành profile bằng cách cập nhật: mục tiêu sự nghiệp để nhận được gợi ý chính xác hơn."


def test_collaborative_endpoint_handles_no_similar_users(feed_client):
    client, _, _, _, _ = feed_client
    response = client.get("/api/posts/recommendations/collaborative?min_similarity=1")
    assert response.status_code == 200
    assert response.json() == {"items": [], "meta": {"page": 1, "page_size": 10, "total": 0, "total_pages": 1}}


@pytest.mark.parametrize("query", ["page=0", "page_size=51", "mode=unknown", "sort=unknown"])
def test_feed_keeps_query_validation(feed_client, query):
    client, _, _, _, _ = feed_client
    assert client.get(f"/api/posts/feed?{query}").status_code == 422


def test_feed_still_requires_authentication():
    client = TestClient(create_app())
    response = client.get("/api/posts/feed")
    assert response.status_code == 401
    client.close()


@pytest.fixture
def upload_client(tmp_path, monkeypatch):
    destination = tmp_path / "images"
    monkeypatch.setattr(upload_application, "UPLOAD_DIR", str(destination))
    monkeypatch.setattr(upload_application, "PUBLIC_API_URL", "")
    client = TestClient(create_app())
    yield client, destination
    client.close()


@pytest.mark.parametrize("public_url", ["", "https://cdn.example.com"])
def test_image_upload_saves_bytes_and_uses_configured_public_url(upload_client, monkeypatch, public_url):
    client, destination = upload_client
    monkeypatch.setattr(upload_application, "PUBLIC_API_URL", public_url)
    response = client.post("/upload/image", files={"file": ("image.PNG", b"image bytes", "image/png")})
    assert response.status_code == 200
    url = response.json()["url"]
    assert url.startswith(f"{public_url or 'http://testserver'}/uploads/")
    assert url.endswith(".png")
    assert (destination / Path(url).name).read_bytes() == b"image bytes"


def test_upload_rejects_other_content_types_without_writing(upload_client):
    client, destination = upload_client
    response = client.post("/upload/image", files={"file": ("image.gif", b"bytes", "image/gif")})
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid file type. Only JPG and PNG are accepted."}
    assert not destination.exists()


def test_upload_preserves_filesystem_failure_response(upload_client, monkeypatch):
    client, _ = upload_client

    def disk_full(*args):
        raise OSError("disk full")

    monkeypatch.setattr(upload_application.shutil, "copyfileobj", disk_full)
    response = client.post("/upload/image", files={"file": ("image.jpg", b"bytes", "image/jpeg")})
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to save file: disk full"}
