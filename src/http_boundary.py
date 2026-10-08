"""Bounded request buffering and privacy-preserving API errors."""
import uuid

from starlette.responses import JSONResponse

MAX_BODY_BYTES = 2 * 1024 * 1024


class RequestBoundary:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request_id = uuid.uuid4().hex
        scope.setdefault('state', {})['request_id'] = request_id
        chunks, size = [], 0
        headers = dict(scope.get('headers', []))
        declared = headers.get(b'content-length', b'0')
        try:
            length = int(declared)
        except ValueError:
            length = -1
        code = 400 if length < 0 else 413 if length > MAX_BODY_BYTES else None
        if not code:
            while True:
                event = await receive()
                if event['type'] == 'http.disconnect':
                    return
                data = event.get('body', b'')
                size += len(data)
                if size > MAX_BODY_BYTES:
                    code = 413
                    break
                chunks.append(data)
                if not event.get('more_body'):
                    break
        if code:
            response = JSONResponse(status_code=code, content={
                'error_code': 'PAYLOAD_TOO_LARGE' if code == 413 else 'INVALID_CONTENT_LENGTH',
                'field': None, 'detail': 'Request rejected by size boundary', 'request_id': request_id,
            }, headers={'X-Request-ID': request_id})
            return await response(scope, receive, send)
        consumed = False

        async def buffered_receive():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}
            return await receive()

        await self.app(scope, buffered_receive, send)
