import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .activity import ActivityBus
from .ai_router import AIRouter
from .config import GATEWAY_API_KEY, GATEWAY_HOST, GATEWAY_PORT, PROVIDERS, ROUTING_PROFILES


class ClientRequestError(ValueError):
    """An invalid client request that should receive HTTP 400."""

activity = ActivityBus()
router = AIRouter(activity)


class Handler(BaseHTTPRequestHandler):
    server_version = 'HariomAI/2.0'

    def _send(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_stream(self, payload):
        body = ('data: ' + json.dumps(payload, ensure_ascii=False) + '\n\n').encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(body)
        self.wfile.write(b'data: [DONE]\n\n')

    def _authorized(self):
        if not GATEWAY_API_KEY:
            return True
        return self.headers.get('Authorization', '') == 'Bearer ' + GATEWAY_API_KEY

    def _json_body(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except (TypeError, ValueError) as exc:
            raise ClientRequestError('Invalid Content-Length') from exc
        if length < 0 or length > 5_000_000:
            raise ClientRequestError('Request body too large')
        try:
            return json.loads(self.rfile.read(length).decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ClientRequestError('Invalid JSON body') from exc

    def do_GET(self):
        if self.path == '/health':
            self._send(200, {'status': 'ok', 'profiles': ROUTING_PROFILES, 'providers': router.status()})
            return
        if self.path == '/v1/models':
            if not self._authorized():
                self._send(401, {'error': {'message': 'Unauthorized'}})
                return
            models = []
            for provider in router.available():
                cfg = PROVIDERS[provider]
                for model in (cfg.get('models') or [cfg.get('model')]):
                    if model:
                        models.append({'id': model, 'object': 'model', 'owned_by': provider})
            models.extend({'id': p, 'object': 'model', 'owned_by': 'hariom-router'} for p in ROUTING_PROFILES)
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
            if not isinstance(payload, dict):
                raise ClientRequestError('JSON body must be an object')
            messages = payload.get('messages') or []
            if not isinstance(messages, list) or not messages:
                raise ClientRequestError('messages is required and must be a non-empty list')

            requested = payload.get('model', 'hariom/auto')
            profile = requested if requested in ROUTING_PROFILES else 'hariom/auto'
            preferred = requested if requested in router.available() else None
            tools = payload.get('tools')
            tool_choice = payload.get('tool_choice')
            response_format = payload.get('response_format')
            use_cache = not bool(payload.get('no_cache', False))

            started = time.time()
            message, provider = router.chat_request(
                messages, preferred=preferred, profile=profile,
                tools=tools, tool_choice=tool_choice,
                response_format=response_format, use_cache=use_cache,
            )
            elapsed = time.time() - started
            usage = router.health[provider].get('last_usage', {})
            usage = usage or {}

            response = {
                'id': 'hariom-' + str(int(started * 1000)),
                'object': 'chat.completion',
                'model': requested,
                'choices': [{
                    'index': 0,
                    'message': message,
                    'finish_reason': 'tool_calls' if message.get('tool_calls') else 'stop',
                }],
                'usage': usage,
                'x_hariom_provider': provider,
                'x_hariom_latency_seconds': round(elapsed, 3),
            }

            if payload.get('stream'):
                self._send_stream({
                    'id': response['id'],
                    'object': 'chat.completion.chunk',
                    'model': requested,
                    'choices': [{
                        'index': 0,
                        'delta': message,
                        'finish_reason': response['choices'][0]['finish_reason'],
                    }],
                })
            else:
                self._send(200, response)
        except ClientRequestError as exc:
            self._send(400, {'error': {'message': str(exc), 'type': 'invalid_request_error'}})
        except Exception as exc:
            self._send(502, {'error': {'message': str(exc), 'type': 'upstream_error'}})

    def log_message(self, fmt, *args):
        activity.emit('GATEWAY -> ' + (fmt % args))


def serve():
    # Never expose an unauthenticated gateway outside localhost.
    if GATEWAY_HOST not in {'127.0.0.1', 'localhost', '::1'} and not GATEWAY_API_KEY:
        raise RuntimeError('HARIOM_GATEWAY_API_KEY is required when binding outside localhost.')
    server = ThreadingHTTPServer((GATEWAY_HOST, GATEWAY_PORT), Handler)
    activity.emit(f'GATEWAY -> listening on http://{GATEWAY_HOST}:{GATEWAY_PORT}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    serve()
