import json
import time
from collections import defaultdict
from pathlib import Path

import requests

from .config import (
    APP_DIR,
    PROVIDERS,
    ROUTER_COOLDOWN_SECONDS,
    ROUTER_RETRIES,
    ROUTER_TIMEOUT_SECONDS,
)


class AIRouter:
    """Native smart router with health, quota, cooldown and model fallback."""

    STATE_FILE = APP_DIR / 'router_state.json'

    def __init__(self, activity):
        self.activity = activity
        self.health = defaultdict(
            lambda: {
                'failures': 0,
                'successes': 0,
                'latency': 0.0,
                'cooldown_until': 0.0,
                'remaining_rpm': None,
                'remaining_tpm': None,
                'remaining_rpd': None,
            }
        )
        self._load_state()

    def available(self):
        return [
            name for name, cfg in PROVIDERS.items()
            if self._configured(name, cfg)
        ]

    def status(self):
        now = time.time()
        result = {}
        for name, cfg in PROVIDERS.items():
            state = self.health[name]
            result[name] = {
                'configured': self._configured(name, cfg),
                'healthy': state['cooldown_until'] <= now,
                'failures': state['failures'],
                'successes': state['successes'],
                'latency': round(state['latency'], 3),
                'cooldown_remaining': max(
                    0, round(state['cooldown_until'] - now, 1)
                ),
                'remaining_rpm': state['remaining_rpm'],
                'remaining_tpm': state['remaining_tpm'],
                'remaining_rpd': state['remaining_rpd'],
            }
        return result

    def chat(self, prompt, system='', preferred=None):
        candidates = self._rank(preferred)
        errors = []

        if not candidates:
            raise RuntimeError(
                'No AI provider is configured. Add at least one API key to .env.'
            )

        for name, model in candidates:
            try:
                self.activity.emit(f'AI -> trying {name} ({model})')
                started = time.monotonic()

                text = (
                    self._gemini(PROVIDERS[name], prompt, system, model)
                    if name == 'gemini'
                    else self._compatible(PROVIDERS[name], prompt, system, model)
                )

                latency = time.monotonic() - started
                self._success(name, latency)
                self.activity.emit(
                    f'AI OK -> {name} ({model}) in {latency:.1f}s'
                )
                return text, name

            except Exception as exc:
                self._failure(name)
                errors.append(f'{name}/{model}: {exc}')
                self.activity.emit(f'AI FAILED -> {name} ({model})')

        raise RuntimeError(
            'All configured AI providers failed. ' + ' | '.join(errors)
        )

    def chat_messages(self, messages, preferred=None):
        """OpenAI-style message entry point for the local gateway."""
        system_parts = [
            m.get('content', '')
            for m in messages
            if m.get('role') == 'system' and isinstance(m.get('content'), str)
        ]
        user_parts = [
            m.get('content', '')
            for m in messages
            if m.get('role') in ('user', 'tool') and isinstance(m.get('content'), str)
        ]
        system = '\n'.join(system_parts)
        prompt = '\n\n'.join(user_parts)
        return self.chat(prompt, system=system, preferred=preferred)

    def _rank(self, preferred=None):
        now = time.time()
        candidates = []

        for name, cfg in PROVIDERS.items():
            if not self._configured(name, cfg):
                continue

            state = self.health[name]
            if state['cooldown_until'] > now:
                self.activity.emit(
                    f'AI -> skipping {name} '
                    f'({state["cooldown_until"] - now:.0f}s cooldown)'
                )
                continue

            models = cfg.get('models') or [cfg.get('model')]
            for index, model in enumerate(models):
                if not model:
                    continue

                preferred_bonus = 1000 if name == preferred else 0
                failure_penalty = state['failures'] * 25
                latency_penalty = min(state['latency'], 60)
                model_penalty = index * 3

                quota_penalty = 0
                if state['remaining_rpm'] is not None:
                    quota_penalty += max(0, 10 - state['remaining_rpm']) * 2
                if state['remaining_tpm'] is not None:
                    quota_penalty += max(0, 1000 - state['remaining_tpm']) / 1000
                if state['remaining_rpd'] is not None:
                    quota_penalty += max(0, 10 - state['remaining_rpd'])

                score = (
                    preferred_bonus
                    + state['successes'] * 5
                    - failure_penalty
                    - latency_penalty
                    - model_penalty
                    - quota_penalty
                )
                candidates.append((score, name, model))

        candidates.sort(key=lambda item: item[0], reverse=True)
        return [(name, model) for _, name, model in candidates]

    def _configured(self, name, cfg):
        if not cfg.get('key'):
            return False
        if cfg.get('cloudflare') and not cfg.get('account_id'):
            return False
        return True

    def _success(self, name, latency):
        state = self.health[name]
        state['successes'] += 1
        state['failures'] = max(0, state['failures'] - 1)
        if state['latency'] == 0:
            state['latency'] = latency
        else:
            state['latency'] = (state['latency'] * 0.7) + (latency * 0.3)
        state['cooldown_until'] = 0.0
        self._save_state()

    def _failure(self, name):
        state = self.health[name]
        state['failures'] += 1
        # Exponential cooldown, capped so a transient error does not permanently
        # remove a provider from the pool.
        delay = min(
            ROUTER_COOLDOWN_SECONDS * (2 ** min(state['failures'] - 1, 4)),
            3600,
        )
        state['cooldown_until'] = time.time() + delay
        self._save_state()

    def _record_quota(self, name, headers):
        state = self.health[name]
        mapping = {
            'remaining_rpm': (
                'x-ratelimit-remaining-requests',
                'x-ratelimit-remaining-rpm',
            ),
            'remaining_tpm': (
                'x-ratelimit-remaining-tokens',
                'x-ratelimit-remaining-tpm',
            ),
            'remaining_rpd': (
                'x-ratelimit-remaining-day-requests',
                'x-ratelimit-remaining-rpd',
            ),
        }

        for field, names in mapping.items():
            for header_name in names:
                value = headers.get(header_name)
                if value is not None:
                    try:
                        state[field] = int(float(value))
                    except (TypeError, ValueError):
                        pass
                    break

        self._save_state()

    def _load_state(self):
        try:
            if not self.STATE_FILE.exists():
                return
            data = json.loads(self.STATE_FILE.read_text(encoding='utf-8'))
            for name, state in data.items():
                self.health[name].update(state)
        except (OSError, ValueError, TypeError):
            # Corrupt state must never stop the AI router.
            return

    def _save_state(self):
        try:
            payload = {name: dict(state) for name, state in self.health.items()}
            self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            self.STATE_FILE.write_text(
                json.dumps(payload, indent=2),
                encoding='utf-8',
            )
        except OSError:
            # Health persistence is optional; routing must keep working.
            return

    def _compatible(self, cfg, prompt, system, model):
        messages = []
        if system:
            messages.append({'role': 'system', 'content': system})
        messages.append({'role': 'user', 'content': prompt})

        payload = {
            'model': model,
            'messages': messages,
            'temperature': 0.2,
        }

        headers = {
            'Authorization': 'Bearer ' + cfg['key'],
            'Content-Type': 'application/json',
        }

        if cfg.get('openrouter'):
            headers['HTTP-Referer'] = 'https://github.com/pateljiop/hariom-ai'
            headers['X-Title'] = 'Hariom AI'

        base = cfg['base']
        if cfg.get('cloudflare'):
            base = base.format(account_id=cfg['account_id'])
            headers['cf-aig-gateway-id'] = 'default'

        return self._post_chat(base, headers, payload, provider=cfg)

    def _post_chat(self, base, headers, payload, provider=None):
        last_error = None

        for attempt in range(ROUTER_RETRIES + 1):
            try:
                response = requests.post(
                    base,
                    headers=headers,
                    json=payload,
                    timeout=ROUTER_TIMEOUT_SECONDS,
                )

                if provider is not None:
                    self._record_quota(
                        next(
                            (
                                name for name, cfg in PROVIDERS.items()
                                if cfg is provider
                            ),
                            'unknown',
                        ),
                        response.headers,
                    )

                if response.status_code == 429 or response.status_code >= 500:
                    retry_after = response.headers.get('Retry-After')
                    if attempt < ROUTER_RETRIES:
                        delay = float(retry_after) if retry_after else 2 ** attempt
                        time.sleep(min(delay, 10))
                        continue

                response.raise_for_status()
                data = response.json()
                choices = data.get('choices') or []

                if not choices:
                    raise RuntimeError(
                        'Provider returned no choices: ' + str(data)[:500]
                    )

                message = choices[0].get('message') or {}
                text = message.get('content')
                if not text:
                    raise RuntimeError(
                        'Provider returned empty content: ' + str(data)[:500]
                    )
                return text

            except (requests.RequestException, ValueError, KeyError) as exc:
                last_error = exc
                if attempt < ROUTER_RETRIES:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(str(last_error)) from last_error

        raise RuntimeError(str(last_error))

    def _gemini(self, cfg, prompt, system, model):
        url = (
            'https://generativelanguage.googleapis.com/v1beta/'
            f'models/{model}:generateContent'
        )
        headers = {
            'x-goog-api-key': cfg['key'],
            'Content-Type': 'application/json',
        }
        payload = {
            'contents': [{'role': 'user', 'parts': [{'text': prompt}]}]
        }
        if system:
            payload['systemInstruction'] = {'parts': [{'text': system}]}

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=ROUTER_TIMEOUT_SECONDS,
        )
        self._record_quota(
            next(
                (
                    name for name, cfg_item in PROVIDERS.items()
                    if cfg_item is cfg
                ),
                'gemini',
            ),
            response.headers,
        )
        response.raise_for_status()

        data = response.json()
        candidates = data.get('candidates') or []
        if not candidates:
            raise RuntimeError(
                'Gemini returned no candidates: '
                + str(data.get('promptFeedback', data))
            )

        parts = candidates[0].get('content', {}).get('parts', [])
        text = ''.join(
            part.get('text', '') for part in parts if part.get('text')
        )
        if not text:
            raise RuntimeError('Gemini returned no text: ' + str(data))
        return text
