from fastapi.testclient import TestClient
from app.factory import create_app
from scripts.check_api_contract import frozen_contract, validate_implementation


def test_frozen_v1_inventory_dtos_security_and_openapi():
    schema = validate_implementation(create_app())
    assert schema['openapi'].startswith('3.1.')
    contract = frozen_contract()
    legacy = {old for endpoint in contract['endpoints'] for old in endpoint['legacy']}
    assert len(legacy) == contract['legacy_endpoint_count'] == 58
    assert len(contract['endpoints']) == 60


def test_all_legacy_rest_paths_are_removed_and_never_redirected():
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        for endpoint in frozen_contract()['endpoints']:
            for old in endpoint['legacy']:
                method, path = old.split(' ', 1)
                for key in ('post_id', 'comment_id', 'tag_id', 'report_id', 'notification_id'):
                    path = path.replace('{' + key + '}', '1')
                path = path.replace('{user_id}', 'user').replace('{username}', 'student')
                response = client.request(method, path, follow_redirects=False)
                assert response.status_code == 404, old
                assert response.headers['content-type'] == 'application/problem+json'


def test_problem_responses_have_server_generated_request_ids_and_auth_headers():
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        first = client.get('/api/v1/feed', headers={'X-Request-ID': 'untrusted'})
        second = client.get('/api/v1/feed')
    assert first.status_code == second.status_code == 401
    assert first.headers['WWW-Authenticate'] == 'Bearer'
    assert first.json()['request_id'] == first.headers['X-Request-ID']
    assert first.json()['request_id'] not in {'untrusted', second.json()['request_id']}
