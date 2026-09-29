import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .ai_router import AIRouter
from .activity import ActivityBus
from .config import GATEWAY_API_KEY, GATEWAY_HOST, GATEWAY_PORT


activity = ActivityBus()
router = AIRouter(activity)


class Handler(BaseHTTPRequestHandler):
    server_version = 'HariomAI/1.0'

    def _send(self, status, payload):
        body = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self):
        if not GATEWAY_API_KEY:
            return True
        header = self.headers.get('Authorization', '')
        return header == 'Bearer ' + GATEWAY_API_KEY

    def _json_body(self):
        length = int(self.headers.get('Content-Length', '0'))
        if length > 5_000_000:
            raise ValueError('Request body too large')
        raw = self.rfile.read(length)
        return json.loads(raw.decode('utf-8'))

    def do_GET(self):
        if self.path == '/health':
            self._send(200, {
                'status': 'ok',
                'providers': router.status(),
            })
            return

        if self.path == '/v1/models':
            if not self._authorized():
                self._send(401, {'error': {'message': 'Unauthorized'}})
                return

            models = []
            for provider in router.available():
                cfg = router.PROVIDERS[provider] if hasattr(router, 'PROVIDERS') else None
                models.append({
                    'id': provider,
                    'object': 'model',
                    'owned_by': 'hariom-ai',
                })
            self._send(200, {'object': 'list', 'data': models})
            return

        self._send(404, {'error': {'message': 'Not found'}})

    def do_POST(self):
        if self.path != '/v1/chat/completions':
            self._send(404, {'error': {'message': 'Not found'}})
            return

        if not self._authorized():
            self._send(401, {'error': {'message': 'Unauthorized'}})
            return

        try:
            payload = self._json_body()
            messages = payload.get('messages') or []
            if not messages:
                raise ValueError('messages is required')

            preferred = None
            requested_model = payload.get('model', '')
            if requested_model in router.available():
                preferred = requested_model

            text, provider = router.chat_messages(
                messages,
                preferred=preferred,
            )

            self._send(200, {
                'id': 'hariom-chat-completion',
                'object': 'chat.completion',
                'model': requested_model or provider,
                'choices': [{
                    'index': 0,
                    'message': {
                        'role': 'assistant',
                        'content': text,
                    },
                    'finish_reason': 'stop',
                }],
                'usage': {
                    'prompt_tokens': 0,
                    'completion_tokens': 0,
                    'total_tokens': 0,
                },
                'x_hariom_provider': provider,
            })
        except Exception as exc:
            self._send(502, {
                'error': {
                    'message': str(exc),
                    'type': 'upstream_error',
                }
            })

    def log_message(self, fmt, *args):
        activity.emit('GATEWAY -> ' + (fmt % args))


def serve():
    server = ThreadingHTTPServer((GATEWAY_HOST, GATEWAY_PORT), Handler)
    activity.emit(
        f'GATEWAY -> listening on http://{GATEWAY_HOST}:{GATEWAY_PORT}'
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    serve()
