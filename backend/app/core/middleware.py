from uuid import uuid4
from starlette.datastructures import MutableHeaders


class RequestIdMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request_id = str(uuid4())
        scope.setdefault('state', {})['request_id'] = request_id

        async def send_with_id(message):
            if message['type'] == 'http.response.start':
                MutableHeaders(scope=message)['X-Request-ID'] = request_id
            await send(message)

        await self.app(scope, receive, send_with_id)
