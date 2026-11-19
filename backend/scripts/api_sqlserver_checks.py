"""HTTP and concurrency checks restricted to the disposable migration database."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker


def verify_api(engine):
    assert engine.dialect.name == 'mssql'
    assert engine.url.database.startswith('UITConnect_Alembic_Verify_')
    from app.factory import create_app
    from app.core.security import create_access_token
    from app.db.session import get_db
    from app.modules.users.models import User
    from app.modules.posts.models import PostLike, PostShare, PostView
    from app.modules.moderation.models import AdminAuditLog, Report
    from app.modules.notifications.models import Notification

    sessions = sessionmaker(engine, expire_on_commit=False)
    accounts = [User(id=str(uuid4()), username=f'api_probe_{index}',
                     email=f'api_probe_{index}@example.test', full_name=f'API probe {index}',
                     password_hash='not-a-login-hash', role='admin' if index == 0 else 'Student',
                     status='active', provider='local', is_verified=True) for index in range(3)]
    with sessions.begin() as db:
        db.add_all(accounts)

    app = create_app()
    def get_test_db():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = get_test_db
    headers = [{'Authorization': 'Bearer ' + create_access_token(user.id, user.email, user.role)} for user in accounts]

    def count(model):
        with sessions() as db:
            return db.scalar(select(func.count()).select_from(model))

    # No lifespan is entered: every request session is explicitly bound to the scratch DB.
    with TestClient(app, raise_server_exceptions=False) as client:
        created = client.post('/api/v1/posts', headers=headers[1], json={
            'title': 'SQL Server contract probe', 'content': 'Contract verification', 'tags': [],
        })
        assert created.status_code == 201, created.text
        post_id = created.json()['id']
        path = f'/api/v1/posts/{post_id}'
        assert client.get(path, headers=headers[2]).status_code == 403
        moderation = f'/api/v1/admin/posts/{post_id}/moderation'
        approved = client.put(moderation, headers=headers[0], json={'status': 'active'})
        assert approved.status_code == 200, approved.text
        audit_count, notice_count = count(AdminAuditLog), count(Notification)
        assert client.put(moderation, headers=headers[0], json={'status': 'active'}).status_code == 200
        assert count(AdminAuditLog) == audit_count and count(Notification) == notice_count
        assert client.put(moderation, headers=headers[0], json={'status': 'rejected'}).status_code == 409
        before = count(PostView)
        detail = client.get(path, headers=headers[2])
        assert detail.status_code == 200, detail.text
        assert 'email' not in detail.json()['author']
        assert detail.json()['created_at'].endswith('Z')
        assert count(PostView) == before
        assert client.post(path + '/views', headers=headers[2]).status_code == 204
        assert count(PostView) == before + 1

        def like(_):
            with TestClient(app, raise_server_exceptions=False) as requester:
                return requester.put(path + '/likes/me', headers=headers[2])
        likes_before = count(PostLike)
        notices_before = count(Notification)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(like, range(2)))
        assert [response.status_code for response in results] == [200, 200], [response.text for response in results]
        assert count(PostLike) == likes_before + 1
        assert count(Notification) == notices_before + 1
        for _ in range(2):
            removed = client.delete(path + '/likes/me', headers=headers[2])
            assert removed.status_code == 204 and removed.content == b''

        shares_before = count(PostShare)
        shares = [client.post(path + '/shares', headers=headers[2], json={'caption': 'Probe'}) for _ in range(2)]
        assert [response.status_code for response in shares] == [201, 201], [response.text for response in shares]
        assert shares[0].json()['post_id'] != shares[1].json()['post_id']
        assert count(PostShare) == shares_before + 2

        comment = client.post(path + '/comments', headers=headers[2], json={'content': 'SQL Server comment probe'})
        assert comment.status_code == 201, comment.text
        assert 'email' not in comment.json()['author']
        assert comment.json()['created_at'].endswith('Z')

        def report(_):
            with TestClient(app, raise_server_exceptions=False) as requester:
                return requester.post(path + '/reports', headers=headers[2], json={'reason': 'spam'})
        reports_before = count(Report)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(report, range(2)))
        assert sorted(response.status_code for response in results) == [201, 409], [response.text for response in results]
        assert count(Report) == reports_before + 1
    print('PASS: real SQL Server HTTP contracts, private DTO filtering, read-only GET, atomic shares and concurrent idempotent likes/reports.')
