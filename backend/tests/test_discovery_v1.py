"""Frozen v1 routes, read-only ranking and the upload trust boundary."""

from datetime import datetime, timedelta
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.core.exceptions import ApplicationError
from app.modules.auth.dependencies import get_current_user
from app.modules.media import application as media
from app.modules.posts.models import PostLike
from test_feed_upload_api import (JPEG, PNG, create_discovery_app, feed_client,
                                  upload_client)  # noqa: F401
from test_posts_transactions import posts_db  # noqa: F401


def test_discovery_operation_ids_and_no_legacy_aliases():
    app = create_discovery_app()
    paths = app.openapi()['paths']
    expected = {
        '/feed': ('get', 'feed_list'),
        '/recommendations/trending': ('get', 'recommendations_list_trending'),
        '/recommendations/collaborative': ('get', 'recommendations_list_collaborative'),
        '/recommendations/profile': ('get', 'recommendations_list_profile'),
        '/recommendations/posts/{post_id}/similar': ('get', 'recommendations_list_similar'),
        '/recommendations/profile-summary': ('get', 'recommendations_get_profile_summary'),
        '/recommendations/profile-analysis': ('get', 'recommendations_get_profile_analysis'),
        '/tags/trending': ('get', 'recommendations_list_trending_tags'),
        '/media/images': ('post', 'media_upload_image'),
        '/notifications': ('get', 'notifications_list'),
        '/notifications/{notification_id}/read': ('put', 'notifications_mark_read'),
        '/notifications/{notification_id}': ('delete', 'notifications_delete'),
    }
    for path, (method, operation) in expected.items():
        assert paths[f'/api/v1{path}'][method]['operationId'] == operation
    with TestClient(app) as client:
        for legacy in ('/api/posts/feed', '/api/posts/trending/suggestions',
                       '/users/me/notifications', '/upload/image', '/api/v1/feed/'):
            assert client.get(legacy).status_code == 404


def test_upload_openapi_requires_a_binary_multipart_file():
    schema = create_discovery_app().openapi()
    request = schema['paths']['/api/v1/media/images']['post']['requestBody']
    assert request['required'] is True
    assert set(request['content']) == {'multipart/form-data'}
    reference = request['content']['multipart/form-data']['schema']['$ref']
    body = schema['components']['schemas'][reference.rsplit('/', 1)[-1]]
    assert body['required'] == ['file']
    assert set(body['properties']) == {'file'}
    field = body['properties']['file']
    assert field['type'] == 'string'
    assert (field.get('format') == 'binary'
            or field.get('contentMediaType') == 'application/octet-stream')


@pytest.mark.parametrize('path', [
    '/feed', '/recommendations/trending', '/recommendations/collaborative',
    '/recommendations/profile', '/recommendations/posts/1/similar',
    '/recommendations/profile-summary', '/recommendations/profile-analysis',
    '/tags/trending', '/notifications',
])
def test_discovery_requires_authentication(path):
    with TestClient(create_discovery_app()) as client:
        response = client.get(f'/api/v1{path}')
        assert response.status_code == 401
        assert response.headers['content-type'] == 'application/problem+json'
        assert response.json()['code'] == 'UNAUTHORIZED'


@pytest.mark.parametrize('status,username', [('inactive', 'member'), ('active', '')])
def test_upload_requires_an_active_completed_account(status, username):
    app = create_discovery_app()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        status=status, username=username, is_verified=True)
    with TestClient(app) as client:
        assert client.post('/api/v1/media/images', files={'file': ('x.png', PNG, 'image/png')}).status_code == 403


def test_upload_requires_authentication():
    with TestClient(create_discovery_app()) as client:
        response = client.post('/api/v1/media/images', files={'file': ('x.png', PNG, 'image/png')})
        assert response.status_code == 401


@pytest.mark.parametrize('mime,data', [
    ('image/png', JPEG), ('image/jpeg', PNG), ('image/png', b''),
    ('image/png', b'pretend image'), ('image/jpg', JPEG),
])
def test_upload_rejects_mismatched_or_unsupported_images(upload_client, mime, data):
    client, destination = upload_client
    response = client.post('/api/v1/media/images', files={'file': ('../../evil.exe', data, mime)})
    assert response.status_code == 400
    assert not destination.exists()


@pytest.mark.parametrize('mime,header,extension', [('image/png', PNG, '.png'), ('image/jpeg', JPEG, '.jpg')])
def test_upload_enforces_exact_size_boundary_and_cleans_rejection(upload_client, mime, header, extension):
    client, destination = upload_client
    data = header + b'x' * (media.MAX_IMAGE_BYTES - len(header))
    accepted = client.post('/api/v1/media/images', files={'file': ('wrong.exe', data, mime)})
    assert accepted.status_code == 201
    assert accepted.json()['url'].endswith(extension)
    saved = list(destination.iterdir())
    assert len(saved) == 1
    assert saved[0].read_bytes() == data
    rejected = client.post('/api/v1/media/images', files={'file': ('x.png', data + b'x', mime)})
    assert rejected.status_code == 413
    assert rejected.json()['code'] == 'PAYLOAD_TOO_LARGE'
    assert list(destination.iterdir()) == saved


def test_upload_bounds_reads_when_stream_is_larger_than_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(media, 'UPLOAD_DIR', str(tmp_path))

    class BoundedStream(BytesIO):
        def read(self, size=-1):
            assert 0 < size <= media.CHUNK_BYTES
            return super().read(size)

    stream = BoundedStream(PNG + b'x' * media.MAX_IMAGE_BYTES)
    with pytest.raises(ApplicationError) as error:
        media.upload_image(SimpleNamespace(content_type='image/png', file=stream), 'http://test')
    assert error.value.status_code == 413
    assert stream.tell() == media.MAX_IMAGE_BYTES + 1
    assert list(tmp_path.iterdir()) == []


def test_trending_scores_before_offset_and_has_stable_id_ties(feed_client):
    client, db, user, original, second = feed_client
    original.created_at = datetime.utcnow() - timedelta(hours=2)
    db.add(PostLike(post_id=original.id, user_id=user.id))
    db.commit()
    first = client.get('/api/v1/recommendations/trending?page_size=1').json()
    next_page = client.get('/api/v1/recommendations/trending?page_size=1&page=2').json()
    assert first['items'][0]['post']['id'] == original.id
    assert next_page['items'][0]['post']['id'] == second.id
    assert next_page['items'][0]['trend_rank'] == 2
    assert first['meta']['total'] == 2
    db.query(PostLike).delete()
    db.commit()
    tied = client.get('/api/v1/recommendations/trending?page_size=1').json()
    assert tied['items'][0]['post']['id'] == second.id


def test_nonempty_trending_tags_aggregate_each_post_without_commit(feed_client):
    client, db, user, original, second = feed_client
    db.add_all([PostLike(post_id=original.id, user_id=user.id),
                PostLike(post_id=second.id, user_id=user.id)])
    db.commit()
    commits = []
    event.listen(db, 'after_commit', lambda _: commits.append(True))
    response = client.get('/api/v1/tags/trending')
    assert response.status_code == 200
    assert response.json()['items'] == [{'tag_name': 'python', 'post_count': 2, 'trend_score': 8.0}]
    assert response.json()['updated_at'].endswith('Z')
    assert commits == []


def test_nonempty_collaborative_keeps_ranking_flags_and_offset(feed_client):
    client, db, user, original, second = feed_client
    user.interest_tags = 'python'
    second.author.interest_tags = 'python'
    db.add_all([PostLike(post_id=original.id, user_id=second.user_id),
                PostLike(post_id=second.id, user_id=second.user_id)])
    db.commit()
    commits = []
    event.listen(db, 'after_commit', lambda _: commits.append(True))
    first = client.get('/api/v1/recommendations/collaborative?page_size=1')
    next_page = client.get('/api/v1/recommendations/collaborative?page_size=1&page=2')
    assert first.status_code == next_page.status_code == 200
    assert first.json()['items'][0]['post']['id'] == second.id
    assert next_page.json()['items'][0]['post']['id'] == original.id
    assert first.json()['items'][0]['cf_score'] > 0
    assert first.json()['items'][0]['post']['is_liked'] is False
    assert first.json()['meta'] == {'page': 1, 'page_size': 1, 'total': 2, 'total_pages': 2}
    assert commits == []


def test_feed_and_recommendation_author_dtos_are_public_and_utc(feed_client):
    client, _, _, original, _ = feed_client
    paths = ['/feed', '/recommendations/trending', '/recommendations/profile?min_score=0',
             f'/recommendations/posts/{original.id}/similar?min_similarity=0']
    for path in paths:
        response = client.get(f'/api/v1{path}')
        assert response.status_code == 200
        items = response.json()['items']
        assert items
        for item in items:
            post = item.get('post', item)
            assert set(post['author']) == {'id', 'username', 'full_name', 'avatar_url', 'bio', 'role'}
            assert post['created_at'].endswith('Z')


def test_empty_similar_and_trending_lists_have_zero_pages(feed_client):
    client, _, _, _, _ = feed_client
    for path in ('/recommendations/posts/999999/similar', '/recommendations/trending?tag=missing'):
        response = client.get(f'/api/v1{path}')
        assert response.status_code == 200
        assert response.json()['items'] == []
        assert response.json()['meta']['total_pages'] == 0
