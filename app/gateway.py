import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .activity import ActivityBus
from .ai_router import AIRouter
from .config import GATEWAY_API_KEY, GATEWAY_HOST, GATEWAY_PORT, PROVIDERS, ROUTING_PROFILES
from .plan_executor import PlanExecutor
from .task_plan import TaskPlan
from .task_service import TaskService, TaskServiceError
from .task_queue import TaskQueue


class ClientRequestError(ValueError):
    """An invalid client request that should receive HTTP 400."""

activity = ActivityBus()
router = AIRouter(activity)
task_service = TaskService()
plan_executor = PlanExecutor(task_service=task_service)
task_queue = TaskQueue(max_workers=2)


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

    def _task_path(self):
        parts = [p for p in urlparse(self.path).path.split('/') if p]
        if len(parts) >= 2 and parts[0] == 'tasks':
            return parts[1], parts[2:]
        return None, []

    def _task_response(self, task):
        return {'task': task.to_dict()}

    def do_GET(self):
        task_id, suffix = self._task_path()
        if task_id:
            if not self._authorized():
                self._send(401, {'error': {'message': 'Unauthorized'}})
                return
            try:
                if suffix == []:
                    self._send(200, self._task_response(task_service.get_task(task_id)))
                elif suffix == ['events']:
                    self._send(200, {'task_id': task_id, 'events': task_service.events(task_id)})
                elif suffix == ['diff']:
                    task = task_service.get_task(task_id)
                    request_id = None
                    for event in reversed(task_service.events(task_id)):
                        if event.get('request_id'):
                            request_id = event['request_id']
                            break
                    approval = task_service.store.get_approval(request_id) if request_id else None
                    self._send(200, {'task_id': task_id, 'diff': approval.get('diff', '') if approval else ''})
                else:
                    self._send(404, {'error': {'message': 'Not found'}})
            except TaskServiceError as exc:
                self._send(404, {'error': {'message': str(exc)}})
            return
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
        parsed = urlparse(self.path)
        task_id, suffix = self._task_path()
        if task_id:
            if not self._authorized():
                self._send(401, {'error': {'message': 'Unauthorized'}})
                return
            try:
                payload = self._json_body()
                if not isinstance(payload, dict):
                    raise ClientRequestError('JSON body must be an object')
                if suffix == []:
                    plan = TaskPlan.from_dict(payload)
                    task = task_service.create_task(
                        plan.user_request or 'agent task',
                        objective=plan.objective or plan.user_request or 'agent task',
                        task_id=plan.task_id or None,
                        dependencies=tuple(plan.dependencies),
                        expected_files=tuple(plan.expected_files),
                        test_commands=tuple(plan.test_commands),
                        risk_level=plan.risk_level,
                        required_approvals=tuple(plan.required_approvals),
                        rollback_strategy=plan.rollback_strategy,
                        max_retries=plan.max_retries,
                        plan=plan.to_dict(),
                    )
                    self._send(201, self._task_response(task))
                elif suffix == ['validate']:
                    plan = TaskPlan.from_dict(payload)
                    self._send(200, {'ok': True, 'task_id': task_id, 'plan': plan.to_dict()})
                elif suffix == ['execute']:
                    if payload.get('background') is True:
                        task_queue.submit(
                            task_id,
                            plan_executor.prepare,
                            payload,
                            task_id,
                        )
                        self._send(202, {"ok": True, "task_id": task_id, "status": "queued"})
                    else:
                        result = plan_executor.prepare(payload, task_id=task_id)
                        self._send(200 if result.get('ok') else 422, result)
                elif suffix == ['queue']:
                    self._send(200, task_queue.status(task_id))
                elif suffix == ['cancel']:
                    reason = payload.get('reason', 'cancelled by user')
                    task = task_service.cancel_task(task_id, reason=reason)
                    self._send(200, self._task_response(task))
                elif suffix == ['approve']:
                    request_id = payload.get('request_id')
                    message = payload.get('message')
                    if not request_id or not message:
                        raise ClientRequestError('request_id and message are required')
                    approval = task_service.store.get_approval(request_id)
                    if not approval or approval.get('task_id') != task_id:
                        raise ClientRequestError('Approval request does not belong to this task')
                    result = plan_executor.approve(request_id, message)
                    self._send(200, result)
                elif suffix == ['reject']:
                    request_id = payload.get('request_id')
                    reason = payload.get('reason', 'rejected by user')
                    if not request_id:
                        raise ClientRequestError('request_id is required')
                    approval = task_service.store.get_approval(request_id)
                    if not approval or approval.get('task_id') != task_id:
                        raise ClientRequestError('Approval request does not belong to this task')
                    result = plan_executor.workflow.reject(request_id, reason)
                    task_service.cancel_task(task_id, reason=reason)
                    self._send(200, result)
                else:
                    self._send(404, {'error': {'message': 'Not found'}})
            except ClientRequestError as exc:
                self._send(400, {'error': {'message': str(exc), 'type': 'invalid_request_error'}})
            except (TaskServiceError, ValueError) as exc:
                self._send(400, {'error': {'message': str(exc)}})
            except Exception as exc:
                self._send(409, {'error': {'message': str(exc), 'type': 'task_error'}})
            return

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
