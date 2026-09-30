import base64
import json
import mimetypes
import time
from collections import defaultdict

import requests

from .cache import get as cache_get, key_for as cache_key, put as cache_put
from .config import (
    APP_DIR, CACHE_ENABLED, PROVIDERS, ROUTING_PROFILES,
    ROUTER_COOLDOWN_SECONDS, ROUTER_RETRIES, ROUTER_TIMEOUT_SECONDS,
)


class AIRouter:
    """Native gateway router: profiles, health, quota, circuit breaking, cache and fallback."""

    STATE_FILE = APP_DIR / 'router_state.json'

    def __init__(self, activity):
        self.activity = activity
        self.health = defaultdict(lambda: {
            'failures': 0, 'successes': 0, 'latency': 0.0,
            'cooldown_until': 0.0, 'disabled_until': 0.0,
            'last_error': '', 'remaining_rpm': None,
            'remaining_tpm': None, 'remaining_rpd': None,
        })
        self._load_state()

    def available(self):
        return [n for n, c in PROVIDERS.items() if self._configured(n, c)]

    def profiles(self):
        return list(ROUTING_PROFILES)

    def status(self):
        now = time.time()
        out = {}
        for name, cfg in PROVIDERS.items():
            s = self.health[name]
            out[name] = {
                'configured': self._configured(name, cfg),
                'healthy': s['cooldown_until'] <= now and s['disabled_until'] <= now,
                'failures': s['failures'], 'successes': s['successes'],
                'latency': round(s['latency'], 3),
                'cooldown_remaining': max(0, round(s['cooldown_until'] - now, 1)),
                'disabled_remaining': max(0, round(s['disabled_until'] - now, 1)),
                'last_error': s['last_error'],
                'remaining_rpm': s['remaining_rpm'],
                'remaining_tpm': s['remaining_tpm'],
                'remaining_rpd': s['remaining_rpd'],
            }
        return out

    def chat(self, prompt, system='', preferred=None, profile='hariom/auto'):
        messages = []
        if system:
            messages.append({'role': 'system', 'content': system})
        messages.append({'role': 'user', 'content': prompt})
        result, provider = self.chat_request(messages, preferred=preferred, profile=profile)
        return result.get('content', ''), provider

    def chat_messages(self, messages, preferred=None, profile='hariom/auto'):
        return self.chat_request(messages, preferred=preferred, profile=profile)

    def chat_vision(self, image_path, prompt, system='', preferred=None, profile='hariom/auto'):
        """Send one local image to a vision-capable provider."""
        from pathlib import Path
        path = Path(image_path).expanduser().resolve()
        if not path.is_file():
            raise ValueError('Vision image does not exist.')
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError('Vision prompt must be a non-empty string.')
        data = base64.b64encode(path.read_bytes()).decode('ascii')
        mime = mimetypes.guess_type(path.name)[0] or 'image/png'
        content = [
            {'type': 'text', 'text': prompt.strip()},
            {'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{data}'}},
        ]
        messages = []
        if system:
            messages.append({'role': 'system', 'content': system})
        messages.append({'role': 'user', 'content': content})
        result, provider = self.chat_request(
            messages, preferred=preferred, profile=profile, vision=True, use_cache=False
        )
        return result.get('content', ''), provider

    def chat_request(self, messages, preferred=None, profile='hariom/auto',
                     tools=None, tool_choice=None, response_format=None,
                     use_cache=True, vision=False):
        if not messages:
            raise ValueError('messages is required')
        if profile not in ROUTING_PROFILES:
            profile = 'hariom/auto'

        cacheable = (
            CACHE_ENABLED and use_cache and not tools and not tool_choice
            and not response_format
            and all(m.get('role') != 'tool' for m in messages)
        )
        key = cache_key(messages, profile)
        if cacheable:
            cached = cache_get(key)
            if cached:
                self.activity.emit('AI CACHE -> hit')
                return cached['message'], cached['provider']

        candidates = self._rank(preferred=preferred, profile=profile, tools=tools, response_format=response_format, vision=vision)
        errors = []
        if not candidates:
            raise RuntimeError('No AI provider is configured or compatible with this request.')

        for name, model in candidates:
            try:
                self.activity.emit(f'AI -> trying {name} ({model}) [{profile}]')
                started = time.monotonic()
                if name == 'gemini':
                    message, usage = self._gemini_request(
                        PROVIDERS[name], messages, model, tools=tools,
                        response_format=response_format
                    )
                else:
                    message, usage = self._compatible_request(
                        name, PROVIDERS[name], messages, model, tools=tools,
                        tool_choice=tool_choice, response_format=response_format
                    )
                latency = time.monotonic() - started
                self.health[name]['last_usage'] = usage or {}
                self._success(name, latency)
                self.activity.emit(f'AI OK -> {name} ({model}) in {latency:.1f}s')
                result = {'message': message, 'provider': name, 'usage': usage or {}}
                if cacheable and message.get('content'):
                    cache_put(key, result)
                return message, name
            except Exception as exc:
                self._failure(name, exc)
                errors.append(f'{name}/{model}: {exc}')
                self.activity.emit(f'AI FAILED -> {name} ({model})')

        raise RuntimeError('All configured AI providers failed. ' + ' | '.join(errors))

    def _rank(self, preferred=None, profile='hariom/auto', tools=None, response_format=None, vision=False):
        now = time.time()
        p = ROUTING_PROFILES.get(profile, {})
        candidates = []
        for name, cfg in PROVIDERS.items():
            if not self._configured(name, cfg):
                continue
            s = self.health[name]
            if s['cooldown_until'] > now or s['disabled_until'] > now:
                continue
            if tools and not cfg.get('supports_tools', False):
                continue
            if response_format and not cfg.get('supports_json', False):
                continue
            if vision and not cfg.get('supports_vision', False):
                continue
            models = cfg.get('models') or [cfg.get('model')]
            for index, model in enumerate(models):
                if not model:
                    continue
                score = (
                    (1000 if name == preferred else 0)
                    + s['successes'] * 5
                    - s['failures'] * 25
                    - min(s['latency'], 60)
                    - index * 3
                    + cfg.get('speed', 5) * p.get('speed', 0)
                    + cfg.get('coding', 5) * p.get('coding', 0)
                    + cfg.get('reasoning', 5) * p.get('reasoning', 0)
                    - s['latency'] * p.get('latency', 0)
                )
                if p.get('free_first'):
                    score += 20 if name in {'groq', 'cerebras', 'openrouter', 'cloudflare', 'gemini'} else 0
                if s['remaining_rpm'] is not None:
                    score -= max(0, 10 - s['remaining_rpm']) * 2
                if s['remaining_tpm'] is not None:
                    score -= max(0, 1000 - s['remaining_tpm']) / 1000
                if s['remaining_rpd'] is not None:
                    score -= max(0, 10 - s['remaining_rpd'])
                candidates.append((score, name, model))
        # Preserve provider insertion order when scores tie; preferred/scored providers still sort first.
        candidates.sort(key=lambda item: item[0], reverse=True)
        return [(n, m) for _, n, m in candidates]

    def _configured(self, name, cfg):
        return bool(cfg.get('key')) and not (cfg.get('cloudflare') and not cfg.get('account_id'))

    def _success(self, name, latency):
        s = self.health[name]
        s['successes'] += 1
        s['failures'] = max(0, s['failures'] - 1)
        s['latency'] = latency if not s['latency'] else s['latency'] * .7 + latency * .3
        s['cooldown_until'] = 0.0
        s['last_error'] = ''
        self._save_state()

    def _failure(self, name, exc):
        s = self.health[name]
        s['failures'] += 1
        s['last_error'] = str(exc)[:500]
        text = str(exc).lower()
        if '401' in text or '403' in text:
            delay = 86400
            s['disabled_until'] = time.time() + delay
        elif '429' in text:
            delay = min(ROUTER_COOLDOWN_SECONDS * (2 ** min(s['failures'] - 1, 4)), 3600)
            s['cooldown_until'] = time.time() + delay
        else:
            delay = min(ROUTER_COOLDOWN_SECONDS * (2 ** min(s['failures'] - 1, 4)), 3600)
            s['cooldown_until'] = time.time() + delay
        self._save_state()

    def _record_quota(self, name, headers):
        s = self.health[name]
        mapping = {
            'remaining_rpm': ('x-ratelimit-remaining-requests', 'x-ratelimit-remaining-rpm'),
            'remaining_tpm': ('x-ratelimit-remaining-tokens', 'x-ratelimit-remaining-tpm'),
            'remaining_rpd': ('x-ratelimit-remaining-day-requests', 'x-ratelimit-remaining-rpd'),
        }
        for field, names in mapping.items():
            for h in names:
                value = headers.get(h)
                if value is not None:
                    try:
                        s[field] = int(float(value))
                    except (TypeError, ValueError):
                        pass
                    break
        self._save_state()

    def _load_state(self):
        try:
            if self.STATE_FILE.exists():
                data = json.loads(self.STATE_FILE.read_text(encoding='utf-8'))
                for n, state in data.items():
                    self.health[n].update(state)
        except (OSError, ValueError, TypeError):
            pass

    def _save_state(self):
        try:
            self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            self.STATE_FILE.write_text(
                json.dumps({n: dict(s) for n, s in self.health.items()}, indent=2),
                encoding='utf-8'
            )
        except OSError:
            pass

    def _compatible_request(self, name, cfg, messages, model, tools=None,
                            tool_choice=None, response_format=None):
        payload = {'model': model, 'messages': messages, 'temperature': 0.2}
        if tools:
            payload['tools'] = tools
        if tool_choice:
            payload['tool_choice'] = tool_choice
        if response_format:
            payload['response_format'] = response_format
        headers = {'Authorization': 'Bearer ' + cfg['key'], 'Content-Type': 'application/json'}
        if cfg.get('openrouter'):
            headers['HTTP-Referer'] = 'https://github.com/pateljiop/hariom-ai'
            headers['X-Title'] = 'Hariom AI'
        base = cfg['base']
        if cfg.get('cloudflare'):
            base = base.format(account_id=cfg['account_id'])
            headers['cf-aig-gateway-id'] = 'default'
        return self._post_chat(name, base, headers, payload)

    def _post_chat(self, name, base, headers, payload):
        last = None
        for attempt in range(ROUTER_RETRIES + 1):
            try:
                r = requests.post(base, headers=headers, json=payload, timeout=ROUTER_TIMEOUT_SECONDS)
                self._record_quota(name, r.headers)
                if r.status_code == 429 or r.status_code >= 500:
                    if attempt < ROUTER_RETRIES:
                        retry_after = r.headers.get('Retry-After')
                        time.sleep(min(float(retry_after) if retry_after else 2 ** attempt, 10))
                        continue
                r.raise_for_status()
                data = r.json()
                choices = data.get('choices') or []
                if not choices:
                    raise RuntimeError('Provider returned no choices: ' + str(data)[:500])
                message = choices[0].get('message') or {}
                if not message.get('content') and not message.get('tool_calls'):
                    raise RuntimeError('Provider returned empty message: ' + str(data)[:500])
                return message, data.get('usage') or {}
            except (requests.RequestException, ValueError, KeyError) as exc:
                last = exc
                if attempt < ROUTER_RETRIES:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(str(last)) from last
        raise RuntimeError(str(last))

    def _gemini_request(self, cfg, messages, model, tools=None, response_format=None):
        url = 'https://generativelanguage.googleapis.com/v1beta/models/' + model + ':generateContent'
        headers = {'x-goog-api-key': cfg['key'], 'Content-Type': 'application/json'}
        contents = []
        system = []
        for m in messages:
            role = m.get('role')
            content = m.get('content')
            if role == 'system':
                if isinstance(content, str):
                    system.append(content)
                continue
            parts = []
            if isinstance(content, str):
                parts.append({'text': content})
            elif isinstance(content, list):
                for item in content:
                    if item.get('type') == 'text':
                        parts.append({'text': item.get('text', '')})
                    elif item.get('type') == 'image_url':
                        url_data = item.get('image_url', {}).get('url', '')
                        if not url_data.startswith('data:') or ';base64,' not in url_data:
                            raise RuntimeError('Gemini vision requires a base64 data URL.')
                        header, encoded = url_data.split(';base64,', 1)
                        mime = header[5:] or 'image/png'
                        parts.append({'inline_data': {'mime_type': mime, 'data': encoded}})
            if parts:
                contents.append({'role': 'model' if role == 'assistant' else 'user', 'parts': parts})
        payload = {'contents': contents}
        if system:
            payload['systemInstruction'] = {'parts': [{'text': '\n'.join(system)}]}
        if response_format and response_format.get('type') == 'json_object':
            payload['generationConfig'] = {'responseMimeType': 'application/json'}
        r = requests.post(url, headers=headers, json=payload, timeout=ROUTER_TIMEOUT_SECONDS)
        self._record_quota('gemini', r.headers)
        r.raise_for_status()
        data = r.json()
        candidates = data.get('candidates') or []
        if not candidates:
            raise RuntimeError('Gemini returned no candidates: ' + str(data.get('promptFeedback', data)))
        parts = candidates[0].get('content', {}).get('parts', [])
        text = ''.join(p.get('text', '') for p in parts if p.get('text'))
        if not text:
            raise RuntimeError('Gemini returned no text: ' + str(data))
        return {'role': 'assistant', 'content': text}, data.get('usageMetadata') or {}
