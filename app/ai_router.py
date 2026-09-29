import time
from collections import defaultdict
import requests

from .config import (
    PROVIDERS,
    ROUTER_COOLDOWN_SECONDS,
    ROUTER_RETRIES,
    ROUTER_TIMEOUT_SECONDS,
)


class AIRouter:
    """Native smart router with health, cooldown, latency and model fallback."""

    def __init__(self, activity):
        self.activity = activity
        self.health = defaultdict(
            lambda: {
                'failures': 0,
                'successes': 0,
                'latency': 0.0,
                'cooldown_until': 0.0,
            }
        )

    def available(self):
        return [
            name for name, cfg in PROVIDERS.items()
            if self._configured(name, cfg)
        ]

    def status(self):
        """Return a UI-friendly snapshot of provider health."""
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
            'All configured AI providers failed. '
            + ' | '.join(errors)
        )

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

                # Preferred provider/model gets the first attempt.
                preferred_bonus = 1000 if name == preferred else 0

                # Healthy providers are preferred; lower recent latency wins.
                failure_penalty = state['failures'] * 25
                latency_penalty = min(state['latency'], 60)
                model_penalty = index * 3

                score = (
                    preferred_bonus
                    + state['successes'] * 5
                    - failure_penalty
                    - latency_penalty
                    - model_penalty
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

    def _failure(self, name):
        state = self.health[name]
        state['failures'] += 1
        state['cooldown_until'] = time.time() + ROUTER_COOLDOWN_SECONDS

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

        return self._post_chat(base, headers, payload)

    def _post_chat(self, base, headers, payload):
        last_error = None

        for attempt in range(ROUTER_RETRIES + 1):
            try:
                response = requests.post(
                    base,
                    headers=headers,
                    json=payload,
                    timeout=ROUTER_TIMEOUT_SECONDS,
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
