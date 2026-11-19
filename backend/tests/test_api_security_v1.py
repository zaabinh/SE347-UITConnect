"""Independent HTTP regressions: production routers and real JWT authorization.

Only the database transport is substituted; authentication dependencies are intact.
SQL Server concurrency is verified separately against a disposable migrated database.
"""

from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, Uuid, create_engine, event
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.security import _create_token, create_access_token, create_refresh_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.factory import create_app
from app.modules.comments.models import Comment
from app.modules.media import application as media
from app.modules.auth.models import AuthSession
from app.modules.moderation.models import AdminAuditLog
from app.modules.notifications.models import Notification
from app.modules.posts.models import Bookmark, Post, PostLike, PostView
from app.modules.users.models import Follow, User
from scripts.check_api_contract import frozen_contract


ENDPOINTS = frozen_contract()['endpoints']
PROTECTED = [endpoint for endpoint in ENDPOINTS if endpoint['security'] != 'public']
ADMIN = [endpoint for endpoint in ENDPOINTS if endpoint['security'] == 'admin']
PNG = b'\x89PNG\r\n\x1a\n'
PRIVATE = {'email', 'provider', 'status', 'is_verified', 'password_hash'}


@pytest.fixture
def http_api(tmp_path, monkeypatch):
    engine = create_engine('sqlite://', poolclass=StaticPool,
                           connect_args={'check_same_thread': False})
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        copied = table.to_metadata(metadata)
        for column in copied.columns:
            if isinstance(column.type, UNIQUEIDENTIFIER):
                column.type = Uuid(as_uuid=False)
            if column.server_default is not None and 'NEWSEQUENTIALID' in str(column.server_default.arg):
                column.server_default = None
    metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        def make_user(name, role='Student'):
            return User(id=str(uuid4()), username=name, full_name=name,
                        email=f'{name}@private.example', password_hash='private-password-hash',
                        provider='local', status='active', role=role, is_verified=True)

        owner, viewer, admin = [make_user('owner'), make_user('viewer'), make_user('admin', 'admin')]
        db.add_all([owner, viewer, admin])
        db.flush()
        post = Post(user_id=owner.id, title='Visible post', content='Visible content',
                    status='active', cover_image='https://example.test/cover.png')
        db.add(post)
        db.flush()
        db.add(Comment(user_id=owner.id, post_id=post.id, content='Public comment', status='active'))
        notification = Notification(user_id=owner.id, actor_id=viewer.id,
                                    type='follow', title='Private notification', is_read=False)
        db.add(notification)
        db.commit()
        app = create_app()
        app.dependency_overrides[get_db] = lambda: db
        destination = tmp_path / 'images'
        monkeypatch.setattr(media, 'UPLOAD_DIR', str(destination))
        monkeypatch.setattr(media, 'PUBLIC_API_URL', '')
        # Do not start background outbox workers or use the configured source database.
        client = TestClient(app, raise_server_exceptions=False)
        try:
            yield client, db, owner, viewer, admin, post, notification, destination
        finally:
            client.close()
    engine.dispose()


def auth(user, **claims):
    token = (create_access_token(user.id, user.email, user.role) if not claims else
             _create_token({'sub': user.id, 'type': 'access', **claims}, timedelta(minutes=5)))
    return {'Authorization': f'Bearer {token}'}


def concrete_path(endpoint, user_id):
    path = endpoint['path']
    for name in ('post_id', 'comment_id', 'tag_id', 'report_id', 'notification_id'):
        path = path.replace('{' + name + '}', '1')
    return path.replace('{user_id}', user_id).replace('{username}', 'owner')


def assert_problem(response, status):
    assert response.status_code == status, response.text
    assert response.headers['content-type'] == 'application/problem+json'
    body = response.json()
    assert {'type', 'title', 'status', 'detail', 'instance', 'code', 'request_id'} <= body.keys()
    assert body['status'] == status
    assert body['request_id'] == response.headers['x-request-id']
    if status == 401:
        assert response.headers['www-authenticate'] == 'Bearer'
    return body


@pytest.mark.parametrize('endpoint', PROTECTED, ids=lambda item: item['operation_id'])
def test_every_protected_route_rejects_anonymous_http(http_api, endpoint):
    client, _, owner, *_ = http_api
    response = client.request(endpoint['method'], concrete_path(endpoint, owner.id))
    assert_problem(response, 401)


@pytest.mark.parametrize('endpoint', ADMIN, ids=lambda item: item['operation_id'])
def test_every_admin_route_uses_database_role_not_elevated_jwt_claim(http_api, endpoint):
    client, _, _, viewer, *_ = http_api
    response = client.request(endpoint['method'], concrete_path(endpoint, viewer.id),
                              headers=auth(viewer, role='admin'))
    assert_problem(response, 403)


@pytest.mark.parametrize('token_kind', ['malformed', 'expired', 'refresh', 'missing-user'])
def test_invalid_jwt_never_authenticates(http_api, token_kind):
    client, _, _, viewer, *_ = http_api
    token = {
        'malformed': 'secret-invalid-token',
        'expired': _create_token({'sub': viewer.id, 'type': 'access'}, timedelta(seconds=-1)),
        'refresh': create_refresh_token(viewer.id)[0],
        'missing-user': create_access_token(str(uuid4()), viewer.email, 'admin'),
    }[token_kind]
    response = client.get('/api/v1/users/me', headers={'Authorization': f'Bearer {token}'})
    assert_problem(response, 401)
    assert token not in response.text


@pytest.mark.parametrize('status,expected', [('banned', 403), ('inactive', 403), ('deleted', 404)])
def test_account_state_is_rechecked_after_token_issuance(http_api, status, expected):
    client, db, _, viewer, *_ = http_api
    headers = auth(viewer)
    viewer.status = status
    db.commit()
    assert_problem(client.get('/api/v1/feed', headers=headers), expected)


def test_public_http_dtos_never_leak_private_account_fields(http_api):
    client, _, owner, viewer, _, post, *_ = http_api
    headers = auth(viewer)
    for path in (f'/api/v1/users/{owner.id}', '/api/v1/users/by-username/owner'):
        response = client.get(path, headers=headers)
        assert response.status_code == 200, response.text
        assert not PRIVATE & response.json().keys()
    for path in (f'/api/v1/posts/{post.id}', '/api/v1/feed', f'/api/v1/posts/{post.id}/comments'):
        response = client.get(path, headers=headers)
        assert response.status_code == 200, response.text
        payload = response.json()
        items = payload['items'] if isinstance(payload, dict) and 'items' in payload else payload
        items = items if isinstance(items, list) else [items]
        assert items
        for item in items:
            assert not PRIVATE & item['author'].keys()
        assert owner.email not in response.text
        assert 'private-password-hash' not in response.text
    assert client.get('/api/v1/users/me', headers=headers).json()['email'] == viewer.email


def test_resource_ownership_is_enforced_after_real_jwt_authentication(http_api):
    client, db, owner, viewer, _, post, notification, *_ = http_api
    for method, path, payload, expected in [
        ('PATCH', f'/api/v1/posts/{post.id}', {'title': 'stolen'}, 403),
        ('DELETE', f'/api/v1/posts/{post.id}', None, 403),
        ('PUT', f'/api/v1/notifications/{notification.id}/read', None, 404),
        ('DELETE', f'/api/v1/notifications/{notification.id}', None, 404),
    ]:
        assert_problem(client.request(method, path, json=payload, headers=auth(viewer)), expected)
    db.refresh(post)
    db.refresh(notification)
    assert post.title == 'Visible post' and post.status == 'active'
    assert notification.is_read is False
    assert client.get('/api/v1/notifications', headers=auth(viewer)).json() == []
    assert client.get('/api/v1/notifications', headers=auth(owner)).json()[0]['id'] == notification.id


def test_patch_null_and_omission_cannot_mass_assign_private_fields(http_api):
    client, db, owner, _, _, post, *_ = http_api
    headers = auth(owner)
    response = client.patch('/api/v1/users/me', json={'bio': None}, headers=headers)
    assert response.status_code == 200 and response.json()['full_name'] == owner.full_name
    response = client.patch(f'/api/v1/posts/{post.id}', json={'cover_image': None}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['cover_image'] is None and response.json()['title'] == 'Visible post'
    for path, payload in [('/api/v1/users/me', {'full_name': None}),
                          ('/api/v1/users/me', {'role': 'admin'}),
                          ('/api/v1/users/me', {}),
                          (f'/api/v1/posts/{post.id}', {'content': None}),
                          (f'/api/v1/posts/{post.id}', {'user_id': str(uuid4())})]:
        assert_problem(client.patch(path, json=payload, headers=headers), 422)
    db.refresh(owner)
    assert owner.role == 'Student'


def test_validation_problem_discards_sensitive_input_and_query_values(http_api):
    client, _, _, viewer, *_ = http_api
    secret = 'sensitive-password-value'
    response = client.post('/api/v1/auth/register', json={'email': secret, 'password': secret})
    body = assert_problem(response, 422)
    assert secret not in response.text
    assert body['errors'] and all(set(error) == {'loc', 'msg', 'type'} for error in body['errors'])
    response = client.get('/api/v1/feed?sort=' + secret, headers=auth(viewer))
    assert_problem(response, 422)
    assert secret not in response.text
    assert response.json()['instance'] == '/api/v1/feed'


def test_http_gets_are_read_only_and_desired_state_writes_are_repeatable(http_api):
    client, db, owner, viewer, _, post, *_ = http_api
    headers = auth(viewer)
    commits = []
    event.listen(db, 'after_commit', lambda _: commits.append(True))
    for path in (f'/api/v1/posts/{post.id}', '/api/v1/feed', '/api/v1/users/me',
                 '/api/v1/notifications', '/api/v1/users/by-username/owner/comments'):
        assert client.get(path, headers=headers).status_code == 200
    assert commits == [] and db.query(PostView).count() == 0
    for path, model in [(f'/api/v1/posts/{post.id}/likes/me', PostLike),
                        (f'/api/v1/posts/{post.id}/bookmarks/me', Bookmark),
                        (f'/api/v1/users/{owner.id}/followers/me', Follow)]:
        for _ in range(2):
            response = client.put(path, headers=headers)
            assert response.status_code == 200, response.text
        assert db.query(model).count() == 1
        for _ in range(2):
            response = client.delete(path, headers=headers)
            assert response.status_code == 204 and response.content == b''
        assert db.query(model).count() == 0
    response = client.post(f'/api/v1/posts/{post.id}/views', headers=headers)
    assert response.status_code == 204 and response.content == b''
    assert db.query(PostView).count() == 1


def test_media_enforces_both_size_boundaries_mime_and_cleanup(http_api):
    client, _, _, viewer, _, _, _, destination = http_api
    headers = auth(viewer)
    response = client.post('/api/v1/media/images', files={'file': ('file.png', PNG + b'x' * (5 * 1024 * 1024 - len(PNG)), 'image/png')}, headers=headers)
    assert response.status_code == 201, response.text
    saved = destination / Path(response.json()['url']).name
    assert saved.stat().st_size == 5 * 1024 * 1024
    saved.unlink()
    for data, mime, expected in [(PNG + b'x' * (5 * 1024 * 1024), 'image/png', 413),
                                 (PNG, 'image/jpeg', 400), (PNG, 'image/gif', 400)]:
        response = client.post('/api/v1/media/images', files={'file': ('file.png', data, mime)}, headers=headers)
        assert_problem(response, expected)
        assert list(destination.iterdir()) == []
    response = client.post('/api/v1/media/images', content=b'x' * (6 * 1024 * 1024 + 1), headers=headers)
    assert_problem(response, 413)
    assert list(destination.iterdir()) == []


def test_chunked_upload_transport_limit_cannot_be_bypassed_without_content_length(http_api):
    client, _, _, viewer, _, _, _, destination = http_api
    boundary = 'independent-security-boundary'
    def chunks():
        yield (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="x.png"\r\nContent-Type: image/png\r\n\r\n').encode()
        yield PNG + b'x' * (6 * 1024 * 1024)
        yield f'\r\n--{boundary}--\r\n'.encode()
    response = client.post('/api/v1/media/images', content=chunks(),
                           headers={**auth(viewer), 'Content-Type': f'multipart/form-data; boundary={boundary}'})
    assert_problem(response, 413)
    assert not destination.exists() or list(destination.iterdir()) == []


def test_actual_login_refresh_logout_lifecycle_and_bodyless_logout(http_api):
    client, db, _, viewer, *_ = http_api
    viewer.password_hash = hash_password('correct-password')
    db.commit()
    assert_problem(client.post('/api/v1/auth/login', json={
        'identifier': viewer.username, 'password': 'incorrect-password',
    }), 401)
    response = client.post('/api/v1/auth/login', json={
        'identifier': viewer.username, 'password': 'correct-password',
    })
    assert response.status_code == 200, response.text
    tokens = response.json()
    assert set(tokens) == {'access_token', 'refresh_token', 'token_type', 'expires_in'}
    assert db.query(AuthSession).count() == 1
    headers = {'Authorization': 'Bearer ' + tokens['access_token']}
    assert client.get('/api/v1/auth/me', headers=headers).json()['id'] == viewer.id
    assert client.post('/api/v1/auth/refresh', json={
        'refresh_token': tokens['refresh_token'],
    }).status_code == 200
    for _ in range(2):
        response = client.post('/api/v1/auth/logout', json={'refresh_token': tokens['refresh_token']})
        assert response.status_code == 204 and response.content == b''
    assert db.query(AuthSession).count() == 0
    assert_problem(client.post('/api/v1/auth/refresh', json={
        'refresh_token': tokens['refresh_token'],
    }), 401)


def test_onboarding_allows_identity_and_completion_but_blocks_active_resources(http_api):
    client, db, _, viewer, *_ = http_api
    headers = auth(viewer)
    viewer.username = None
    db.commit()
    response = client.get('/api/v1/auth/me', headers=headers)
    assert response.status_code == 200 and response.json()['profile_completed'] is False
    assert_problem(client.get('/api/v1/feed', headers=headers), 403)
    response = client.put('/api/v1/users/me/profile-completion', headers=headers,
                          json={'username': 'newviewer', 'full_name': 'New Viewer'})
    assert response.status_code == 200 and response.json()['profile_completed'] is True
    assert client.get('/api/v1/feed', headers=headers).status_code == 200


def test_post_creation_terminal_moderation_and_remaining_bodyless_deletions(http_api):
    client, db, owner, viewer, admin, _, notification, *_ = http_api
    response = client.post('/api/v1/posts', headers=auth(owner),
                           json={'title': 'New draft', 'content': 'Draft body', 'tags': []})
    assert response.status_code == 201, response.text
    post_id = response.json()['id']
    assert response.headers['location'] == f'/api/v1/posts/{post_id}'
    assert_problem(client.get(response.headers['location'], headers=auth(viewer)), 403)
    path = f'/api/v1/admin/posts/{post_id}/moderation'
    response = client.put(path, headers=auth(admin), json={'status': 'active'})
    assert response.status_code == 200, response.text
    before = db.query(AdminAuditLog).count(), db.query(Notification).count()
    assert client.put(path, headers=auth(admin), json={'status': 'active'}).status_code == 200
    assert before == (db.query(AdminAuditLog).count(), db.query(Notification).count())
    assert_problem(client.put(path, headers=auth(admin), json={'status': 'rejected'}), 409)
    assert before == (db.query(AdminAuditLog).count(), db.query(Notification).count())
    response = client.delete(f'/api/v1/posts/{post_id}', headers=auth(owner))
    assert response.status_code == 204 and response.content == b''
    response = client.post('/api/v1/admin/tags', headers=auth(admin), json={'name': 'testtag'})
    assert response.status_code == 201, response.text
    response = client.delete('/api/v1/admin/tags/' + str(response.json()['id']), headers=auth(admin))
    assert response.status_code == 204 and response.content == b''
    assert_problem(client.delete(f'/api/v1/notifications/{notification.id}', headers=auth(owner)), 400)
    assert client.put(f'/api/v1/notifications/{notification.id}/read', headers=auth(owner)).status_code == 200
    response = client.delete(f'/api/v1/notifications/{notification.id}', headers=auth(owner))
    assert response.status_code == 204 and response.content == b''


def test_unhandled_server_error_is_sanitized_and_preserves_request_id_and_cors(http_api):
    client, *_ = http_api
    def unavailable_database():
        raise RuntimeError('SELECT password_hash FROM secret_table; password=private-credential')
    client.app.dependency_overrides[get_db] = unavailable_database
    response = client.get('/api/v1/auth/me', headers={'Origin': 'http://localhost:3000'})
    assert_problem(response, 500)
    assert response.json()['detail'] == 'Internal server error.'
    assert not any(value in response.text for value in ('SELECT', 'secret_table', 'private-credential'))
    assert response.headers['access-control-allow-origin'] == 'http://localhost:3000'
    assert response.headers['access-control-allow-credentials'] == 'true'


def test_nested_comment_identifiers_cannot_target_a_different_post(http_api):
    client, db, owner, viewer, _, post, *_ = http_api
    other = Post(user_id=owner.id, title='Another post', content='Body', status='active')
    db.add(other)
    db.flush()
    foreign_comment = Comment(user_id=owner.id, post_id=other.id, content='Other thread', status='active')
    db.add(foreign_comment)
    db.commit()
    headers = auth(viewer)
    response = client.post(f'/api/v1/posts/{post.id}/comments', headers=headers,
                           json={'content': 'Wrong parent', 'parent_id': foreign_comment.id})
    assert_problem(response, 404)
    response = client.post(f'/api/v1/posts/{post.id}/comments/{foreign_comment.id}/reports',
                           headers=headers, json={'reason': 'spam'})
    assert_problem(response, 404)
    assert db.query(Comment).count() == 2


def test_http_feed_preserves_follow_filter_ranking_and_pagination_totals(http_api):
    client, db, owner, viewer, admin, original, *_ = http_api
    newer = Post(user_id=owner.id, title='Matching second', content='Body', status='active',
                 created_at=original.created_at)
    hidden = Post(user_id=admin.id, title='Matching hidden', content='Body', status='pending',
                  created_at=original.created_at)
    db.add_all([newer, hidden, Follow(follower_id=viewer.id, following_id=owner.id)])
    db.flush()
    # The original's active comment must outrank an equally aged post without engagement.
    db.add(Comment(user_id=admin.id, post_id=newer.id, content='Hidden comment', status='hidden'))
    db.commit()
    headers = auth(viewer)
    for query in ('mode=for-you', 'mode=trending', 'sort=most-commented'):
        response = client.get('/api/v1/feed?' + query, headers=headers)
        assert response.status_code == 200, response.text
        assert [post['id'] for post in response.json()['items']] == [original.id, newer.id]
        assert response.json()['meta'] == {'page': 1, 'page_size': 10, 'total': 2, 'total_pages': 1}
    response = client.get('/api/v1/feed?mode=following&search=Matching&page_size=1', headers=headers)
    assert response.status_code == 200, response.text
    assert [post['id'] for post in response.json()['items']] == [newer.id]
    assert response.json()['meta'] == {'page': 1, 'page_size': 1, 'total': 1, 'total_pages': 1}
    response = client.get('/api/v1/feed?search=does-not-exist', headers=headers)
    assert response.status_code == 200 and response.json()['items'] == []
    assert response.json()['meta']['total_pages'] == response.json()['meta']['total'] == 0
