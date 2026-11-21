"""Supported-flow smoke tests on an isolated real DB session and production routers."""

from uuid import uuid4

import pytest
from sqlalchemy import text

from scripts.deployment_smoke import request_json, run_smoke
from test_api_security_v1 import auth, http_api  # noqa: F401 - reuse isolated HTTP/SQLite fixture


def test_supported_auth_posts_feed_tags_and_interactions(http_api):
    client, db, owner, viewer, admin, *_ = http_api
    assert db.execute(text('SELECT 1')).scalar_one() == 1
    username = 'smoke_' + uuid4().hex[:12]
    password = 'Smoke-Test-Password-2026!'
    registered = client.post('/api/v1/auth/register', json={
        'username': username, 'email': f'{username}@example.com',
        'password': password, 'full_name': 'Smoke Test',
    })
    assert registered.status_code == 201, registered.text
    login = client.post('/api/v1/auth/login', json={'identifier': username, 'password': password})
    assert login.status_code == 200, login.text
    tokens = login.json()
    headers = {'Authorization': 'Bearer ' + tokens['access_token']}
    me = client.get('/api/v1/auth/me', headers=headers)
    assert me.status_code == 200 and me.json()['username'] == username
    completed = client.put('/api/v1/users/me/profile-completion', headers=headers,
                           json={'username': username, 'full_name': 'Smoke Test', 'interest_tags': ['python']})
    assert completed.status_code == 200 and completed.json()['profile_completed'] is True
    tag_name = 'smoke-' + uuid4().hex[:12]
    tag = client.post('/api/v1/admin/tags', headers=auth(admin), json={'name': tag_name})
    assert tag.status_code == 201, tag.text
    created = client.post('/api/v1/posts', headers=headers, json={
        'title': 'Smoke compatibility post', 'content': 'Created in the disposable test database.', 'tags': [tag_name],
    })
    assert created.status_code == 201 and created.json()['status'] == 'pending', created.text
    post_id = created.json()['id']
    approved = client.put(f'/api/v1/admin/posts/{post_id}/moderation', headers=auth(admin), json={'status': 'active'})
    assert approved.status_code == 200, approved.text
    feed = client.get('/api/v1/feed', params={'tag': tag_name}, headers=headers)
    assert feed.status_code == 200 and [item['id'] for item in feed.json()['items']] == [post_id]
    liked = client.put(f'/api/v1/posts/{post_id}/likes/me', headers=headers)
    assert liked.status_code == 200, liked.text
    # Run the same read-only checks used against a deployed target through real HTTP routers.
    def request_json(url, request_headers):
        response = client.get(url.removeprefix('http://testserver'), headers=request_headers)
        return response.status_code, response.json()
    run_smoke('http://testserver', tokens['access_token'], request_json)
    refreshed = client.post('/api/v1/auth/refresh', json={'refresh_token': tokens['refresh_token']})
    assert refreshed.status_code == 200, refreshed.text
    logout = client.post('/api/v1/auth/logout', json={'refresh_token': refreshed.json()['refresh_token']})
    assert logout.status_code == 204 and logout.content == b''


def test_deployed_smoke_requires_authentication_without_sending_requests():
    with pytest.raises(ValueError, match='SMOKE_ACCESS_TOKEN'):
        run_smoke('https://api.example.test', '', lambda *_: pytest.fail('must not send requests'))


def test_deployed_smoke_fails_on_database_backed_read_without_leaking_token(capsys):
    def failed_read(url, headers):
        return (200, {'status': 'healthy'}) if url.endswith('/health') else (500, {'detail': 'secret'})
    with pytest.raises(RuntimeError, match='HTTP 500'):
        run_smoke('https://api.example.test', 'private-token', failed_read)
    assert 'private-token' not in capsys.readouterr().out


@pytest.mark.parametrize('origin', ['https://user:password@example.com', 'https://example.com/api/v1',
                                  'https://example.com?token=secret'])
def test_deployed_smoke_rejects_non_origin_urls_before_sending_requests(origin):
    with pytest.raises(ValueError, match='API origin'):
        run_smoke(origin, 'private-token', lambda *_: pytest.fail('must not send requests'))


@pytest.mark.parametrize('status', [302, 307])
def test_transport_does_not_follow_redirects_or_forward_token(status):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    paths = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            paths.append(self.path)
            self.send_response(status)
            self.send_header('Location', '/capture')
            self.end_headers()
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = request_json(f'http://127.0.0.1:{server.server_port}/redirect', {'Authorization': 'Bearer private-token'})
        assert result == (status, None)
        assert paths == ['/redirect']
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
