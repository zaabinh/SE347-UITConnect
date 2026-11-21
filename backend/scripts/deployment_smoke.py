"""Read-only deployed API smoke checks; send a token via SMOKE_ACCESS_TOKEN, never CLI/logs."""

import argparse
import json
import os
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


def run_smoke(origin, token, request_json):
    """A protected database-backed read proves more than the liveness endpoint alone."""
    parsed = urlsplit(origin)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.path not in ('', '/') or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError('Supply an API origin such as https://api.example.test, without /api/v1 or query/fragment')
    base = origin.rstrip('/')
    checks = [('/health', False, dict), ('/api/v1/auth/me', True, dict),
              ('/api/v1/users/me', True, dict), ('/api/v1/tags', True, list),
              ('/api/v1/feed?page=1&page_size=1', True, dict)]
    if not token:
        raise ValueError('SMOKE_ACCESS_TOKEN is required for authenticated and database-backed checks')
    for path, protected, expected in checks:
        status, body = request_json(base + path, {'Authorization': f'Bearer {token}'} if protected else {})
        if status != 200 or not isinstance(body, expected):
            raise RuntimeError(f'Smoke check failed at {path}: HTTP {status} or invalid JSON representation')
        if path == '/health' and body.get('status') != 'healthy':
            raise RuntimeError('Health response is not healthy')
        if path.endswith('/me') and not body.get('id'):
            raise RuntimeError('Current user response has no identity')
        if path.startswith('/api/v1/feed') and not (isinstance(body.get('items'), list) and isinstance(body.get('meta'), dict)):
            raise RuntimeError('Feed response lacks items/meta')
        print(f'PASS GET {path}')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        return None  # Never forward the smoke bearer token to a redirected host.


def request_json(url, headers):
    request = Request(url, headers={**headers, 'Accept': 'application/json'})
    try:
        with build_opener(NoRedirect).open(request, timeout=15) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        # Avoid printing response bodies, token-bearing requests or credentials.
        return error.code, None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', required=True)
    args = parser.parse_args()
    run_smoke(args.origin, os.environ.get('SMOKE_ACCESS_TOKEN', ''), request_json)


if __name__ == '__main__':
    main()
