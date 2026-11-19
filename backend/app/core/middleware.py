from uuid import uuid4
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.exceptions import HTTPException
from app.core.exceptions import apply_error_cors, problem

MEDIA_REQUEST_LIMIT = 6 * 1024 * 1024


class RequestIdMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request_id = str(uuid4())
        scope.setdefault('state', {})['request_id'] = request_id

        media_upload = scope['path'] == '/api/v1/media/images' and scope['method'] == 'POST'
        if media_upload:
            length = dict(scope.get('headers', [])).get(b'content-length', b'0')
            try:
                oversized = int(length) > MEDIA_REQUEST_LIMIT
            except ValueError:
                oversized = False
            if oversized:
                request = Request(scope)
                response = apply_error_cors(request, problem(request, 413, 'Upload request exceeds 6 MiB.'))
                return await response(scope, receive, send)

        received = 0
        async def bounded_receive():
            nonlocal received
            message = await receive()
            if media_upload and message['type'] == 'http.request':
                received += len(message.get('body', b''))
                if received > MEDIA_REQUEST_LIMIT:
                    raise HTTPException(413, 'Upload request exceeds 6 MiB.')
            return message

        async def send_with_id(message):
            if message['type'] == 'http.response.start':
                MutableHeaders(scope=message)['X-Request-ID'] = request_id
            await send(message)

        await self.app(scope, bounded_receive, send_with_id)
