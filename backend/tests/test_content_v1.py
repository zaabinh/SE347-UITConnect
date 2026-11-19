"""Frozen content routes and repeatable transitions using the production ORM."""
import json
from pathlib import Path
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, Uuid, create_engine, event
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.core.exceptions import register_exception_handlers
from app.db.base import Base
from app.db.session import get_db
from app.db.uow import UnitOfWork
from app.modules.auth.dependencies import get_current_user
from app.modules.comments import router as comments
from app.modules.comments.models import Comment
from app.modules.moderation import router as moderation
from app.modules.moderation.models import AdminAuditLog, Report
from app.modules.notifications.models import Notification
from app.modules.posts import router as posts
from app.modules.posts.models import Post, PostLike, Bookmark, PostShare, PostView
from app.modules.posts.repository import PostRepository, paginate_latest_posts_fast, paginate_trending_posts_fast
from app.modules.users.models import User


@pytest.fixture
def api():
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
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
        def user(name, role='Student'):
            return User(id=str(uuid4()), username=name, email=f'{name}@example.test', full_name=name,
                        password_hash='hash', role=role, status='active', is_verified=True)
        owner, viewer, admin = user('owner'), user('viewer'), user('admin', 'admin')
        db.add_all([owner, viewer, admin])
        db.flush()
        post = Post(user_id=owner.id, title='Original post', slug='original-post', content='Body',
                    status='active', cover_image='https://example.test/cover.png')
        db.add(post)
        db.commit()
        selected = [viewer]
        app = FastAPI(redirect_slashes=False)
        for router in [posts.router, posts.tag_router, comments.router, moderation.router]:
            app.include_router(router, prefix='/api/v1')
        register_exception_handlers(app)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: selected[0]
        with TestClient(app) as client:
            yield client, db, post, owner, viewer, admin, selected
    engine.dispose()


def test_frozen_content_openapi(api):
    client, *_ = api
    schema = client.get('/openapi.json').json()
    contract = json.loads((Path(__file__).parent / 'api_v1_contract.json').read_text())
    actual = {(method.upper(), path): value for path, methods in schema['paths'].items() for method, value in methods.items()}
    expected = {(e['method'], e['path']): e for e in contract['endpoints']
                if e['operation_id'].startswith(('posts_', 'comments_', 'admin_')) or e['operation_id'] == 'tags_list'}
    assert actual.keys() == expected.keys()
    for key, endpoint in expected.items():
        operation = actual[key]
        assert operation['operationId'] == endpoint['operation_id']
        response = operation['responses'][str(endpoint['status'])]
        if endpoint['response']:
            body = response['content']['application/json']['schema']
            if endpoint['response'].endswith('[]'):
                assert body['type'] == 'array'
                body = body['items']
            assert body['$ref'].endswith('/' + endpoint['response'].removesuffix('[]'))
        else:
            assert 'content' not in response
        if endpoint['request']:
            body = operation['requestBody']['content']['application/json']['schema']
            if endpoint['request'] == 'SharePostRequest':
                body = body['anyOf'][0]
            assert body['$ref'].endswith('/' + endpoint['request'])
    assert not any(path.endswith('/') for _, path in actual)


def test_detail_read_only_and_private_safe(api):
    client, db, post, *_ = api
    commits = []
    event.listen(db, 'after_commit', lambda _: commits.append(True))
    for _ in range(2):
        response = client.get(f'/api/v1/posts/{post.id}')
        assert response.status_code == 200
        body = response.json()
        assert body['views_count'] == 0 and body['created_at'].endswith('Z')
        assert set(body['author']) == {'id', 'username', 'full_name', 'avatar_url', 'bio', 'role'}
    assert commits == [] and db.query(PostView).count() == 0
    response = client.post(f'/api/v1/posts/{post.id}/views')
    assert response.status_code == 204 and not response.content
    assert db.query(PostView).count() == len(commits) == 1


@pytest.mark.parametrize('membership,model,key', [('likes', PostLike, 'liked'), ('bookmarks', Bookmark, 'bookmarked')])
def test_membership_idempotency(api, membership, model, key):
    client, db, post, *_ = api
    path = f'/api/v1/posts/{post.id}/{membership}/me'
    for _ in range(2):
        assert client.put(path).json() == {key: True}
    assert db.query(model).count() == 1
    assert db.query(Notification).count() == (1 if membership == 'likes' else 0)
    for _ in range(2):
        response = client.delete(path)
        assert response.status_code == 204 and not response.content
    assert db.query(model).count() == 0
    assert db.query(Notification).count() == (1 if membership == 'likes' else 0)


@pytest.mark.parametrize('state,expected', [('pending', 403), ('rejected', 403), ('deleted', 404)])
@pytest.mark.parametrize('method,suffix,body', [
    ('GET', '', None), ('POST', '/views', None), ('PUT', '/likes/me', None), ('DELETE', '/likes/me', None),
    ('PUT', '/bookmarks/me', None), ('DELETE', '/bookmarks/me', None), ('POST', '/shares', {}),
    ('POST', '/reports', {'reason': 'spam'}), ('GET', '/comments', None),
    ('POST', '/comments', {'content': 'Comment'}), ('POST', '/comments/1/reports', {'reason': 'spam'}),
])
def test_interactions_require_visibility(api, state, expected, method, suffix, body):
    client, db, post, *_ = api
    post.status = state
    db.commit()
    response = client.request(method, f'/api/v1/posts/{post.id}{suffix}', json=body)
    assert response.status_code == expected, response.text
    for model in [PostLike, Bookmark, PostView, PostShare, Report, Comment, Notification]:
        assert db.query(model).count() == 0


@pytest.mark.parametrize('who', ['owner', 'admin'])
def test_owner_and_admin_pending_visibility(api, who):
    client, db, post, owner, _, admin, selected = api
    selected[0] = owner if who == 'owner' else admin
    post.status = 'pending'
    db.commit()
    assert client.get(f'/api/v1/posts/{post.id}').status_code == 200
    assert client.get(f'/api/v1/posts/{post.id}/comments').status_code == 200
    post.status = 'deleted'
    db.commit()
    assert client.get(f'/api/v1/posts/{post.id}').status_code == 404
    assert client.put(f'/api/v1/posts/{post.id}/likes/me').status_code == 404


def test_patch_omission_and_null(api):
    client, _, post, owner, _, _, selected = api
    selected[0] = owner
    path = f'/api/v1/posts/{post.id}'
    for payload in [{}, {'title': None}, {'content': None}, {'tags': None}, {'status': None}]:
        assert client.patch(path, json=payload).status_code == 422
    response = client.patch(path, json={'title': 'Updated title'})
    assert response.status_code == 200
    assert response.json()['cover_image'] == 'https://example.test/cover.png' and response.json()['content'] == 'Body'
    response = client.patch(path, json={'cover_image': None})
    assert response.status_code == 200 and response.json()['cover_image'] is None


def test_repeat_share_has_unique_slug_and_bounded_title(api):
    client, db, post, *_ = api
    post.title = 'A' * 255
    db.commit()
    results = [client.post(f'/api/v1/posts/{post.id}/shares', json={'caption': 'hello'}) for _ in range(2)]
    assert [r.status_code for r in results] == [201, 201]
    ids = [r.json()['post_id'] for r in results]
    assert len(set(ids)) == 2
    for response in results:
        body = response.json()
        assert body['original_post_id'] == post.id
        assert response.headers['location'] == f"/api/v1/posts/{body['post_id']}"
        shared = db.get(Post, body['post_id'])
        assert len(shared.title) <= 255 and len(shared.slug) <= 255
    assert len({db.get(Post, id).slug for id in ids}) == db.query(PostShare).count() == 2


def test_comment_tree_author_privacy_and_utc(api):
    client, _, post, *_ = api
    path = f'/api/v1/posts/{post.id}/comments'
    parent = client.post(path, json={'content': 'Parent'})
    assert parent.status_code == 201
    assert client.post(path, json={'content': 'Reply', 'parent_id': parent.json()['id']}).status_code == 201
    tree = client.get(path).json()
    assert len(tree) == len(tree[0]['replies']) == 1
    for comment in [tree[0], tree[0]['replies'][0]]:
        assert comment['created_at'].endswith('Z')
        assert set(comment['author']) == {'id', 'username', 'full_name', 'avatar_url', 'bio', 'role'}


def test_post_terminal_decision_idempotency(api):
    client, db, post, _, _, admin, selected = api
    selected[0] = admin
    post.status = 'pending'
    db.commit()
    path = f'/api/v1/admin/posts/{post.id}/moderation'
    response = client.put(path, json={'status': 'active'})
    assert response.status_code == 200 and response.json()['status'] == 'active'
    assert response.json()['created_at'].endswith('Z')
    notices = db.query(Notification).count()
    assert client.put(path, json={'status': 'active'}).status_code == 200
    conflict = client.put(path, json={'status': 'rejected'})
    assert conflict.status_code == 409 and conflict.json()['code'] == 'POST_ALREADY_MODERATED'
    assert db.query(AdminAuditLog).count() == 1 and db.query(Notification).count() == notices
    assert db.get(Post, post.id).status == 'active'


def test_report_terminal_decision_compares_action(api):
    client, db, post, _, _, admin, selected = api
    created = client.post(f'/api/v1/posts/{post.id}/reports', json={'reason': 'spam'})
    assert created.status_code == 201
    selected[0] = admin
    path = f"/api/v1/admin/reports/{created.json()['id']}/moderation"
    payload = {'status': 'resolved', 'action': 'hide_post'}
    assert client.put(path, json=payload).status_code == 200
    notices = db.query(Notification).count()
    assert client.put(path, json={**payload, 'notes': 'repeat'}).status_code == 200
    for payload in [{'status': 'dismissed'}, {'status': 'resolved', 'action': 'ban_author'}]:
        response = client.put(path, json=payload)
        assert response.status_code == 409 and response.json()['code'] == 'REPORT_ALREADY_MODERATED'
    assert db.query(AdminAuditLog).count() == 1 and db.query(Notification).count() == notices


def test_ban_unban_retry_and_deleted_user(api):
    client, db, _, owner, _, admin, selected = api
    selected[0] = admin
    path = f'/api/v1/admin/users/{owner.id}/ban'
    for _ in range(2):
        response = client.put(path, json={'reason': 'spam'})
        assert response.status_code == 200 and response.json()['status'] == 'banned'
    assert db.query(AdminAuditLog).count() == db.query(Notification).count() == 1
    for _ in range(2):
        response = client.delete(path)
        assert response.status_code == 200 and response.json()['status'] == 'active'
    assert db.query(AdminAuditLog).count() == db.query(Notification).count() == 2
    owner.status = 'deleted'
    db.commit()
    assert client.delete(path).status_code == 404
    assert client.put(path, json={'reason': None}).status_code == 404
    assert db.get(User, owner.id).status == 'deleted'


def test_tag_routes_and_empty_pages(api):
    client, _, _, _, _, admin, selected = api
    selected[0] = admin
    created = client.post('/api/v1/admin/tags', json={'name': 'Python'})
    assert created.status_code == 201 and created.json()['created_at'].endswith('Z')
    tag_id = created.json()['id']
    assert client.get('/api/v1/tags').json() == [created.json()]
    assert client.patch(f'/api/v1/admin/tags/{tag_id}', json={}).status_code == 422
    updated = client.patch(f'/api/v1/admin/tags/{tag_id}', json={'name': 'Databases'})
    assert updated.status_code == 200 and updated.json()['name'] == 'databases'
    deleted = client.delete(f'/api/v1/admin/tags/{tag_id}')
    assert deleted.status_code == 204 and not deleted.content
    assert client.get('/api/v1/tags').json() == []
    assert client.get('/api/v1/admin/posts/pending').json()['meta']['total_pages'] == 0


def test_ranked_pagination_reports_only_servable_candidates(api):
    _, db, post, owner, viewer, *_ = api
    db.add_all([Post(user_id=owner.id, title=f'Candidate {i}', content='Body', status='active',
                     created_at=post.created_at) for i in range(310)])
    db.commit()
    latest, latest_meta = paginate_latest_posts_fast(db, viewer.id, None, None, 'for-you', 4, 50)
    assert latest_meta.total == 200 and latest_meta.total_pages == 4
    assert len(latest) == 50
    assert [row[0].id for row in latest] == sorted([row[0].id for row in latest], reverse=True)
    assert paginate_latest_posts_fast(db, viewer.id, None, None, 'for-you', 5, 50)[0] == []
    trending, trending_meta = paginate_trending_posts_fast(db, viewer.id, None, None, 6, 50)
    assert trending_meta.total == 300 and trending_meta.total_pages == 6
    assert len(trending) == 50
    assert [row[0].id for row in trending] == sorted([row[0].id for row in trending], reverse=True)
    assert paginate_trending_posts_fast(db, viewer.id, None, None, 7, 50)[0] == []


def test_post_lock_is_acquired_before_membership_reads(api, monkeypatch):
    client, _, post, *_ = api
    locks = []
    original_lock, original_get = UnitOfWork.lock, PostRepository.get
    def lock(uow, resource):
        locks.append(resource)
        return original_lock(uow, resource)
    def get(repo, post_id):
        assert f'post:{post_id}' in locks
        return original_get(repo, post_id)
    monkeypatch.setattr(UnitOfWork, 'lock', lock)
    monkeypatch.setattr(PostRepository, 'get', get)
    assert client.put(f'/api/v1/posts/{post.id}/likes/me').status_code == 200
