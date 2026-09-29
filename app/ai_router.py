import time
import requests
from .config import PROVIDERS


class AIRouter:
    """Try configured providers/models and fall back automatically."""

    def __init__(self, activity):
        self.activity = activity

    def available(self):
        return [
            name for name, cfg in PROVIDERS.items()
            if cfg.get('key') and (not cfg.get('cloudflare') or cfg.get('account_id'))
        ]

    def chat(self, prompt, system='', preferred=None):
        order = []
        if preferred in PROVIDERS:
            order.append(preferred)
        order += [name for name in PROVIDERS if name not in order]

        errors = []
        for name in order:
            cfg = PROVIDERS[name]
            if not cfg.get('key'):
                continue
            if cfg.get('cloudflare') and not cfg.get('account_id'):
                continue

            models = cfg.get('models') or [cfg.get('model')]
            for model in models:
                if not model:
                    continue
                try:
                    self.activity.emit(f'AI -> trying {name} ({model})')
                    text = (
                        self._gemini(cfg, prompt, system, model)
                        if name == 'gemini'
                        else self._compatible(cfg, prompt, system, model)
                    )
                    self.activity.emit(f'AI OK -> {name} ({model})')
                    return text, name
                except Exception as exc:
                    errors.append(f'{name}/{model}: {exc}')
                    self.activity.emit(f'AI FAILED -> {name} ({model})')

        raise RuntimeError(
            'No working provider. Configure a key and check quota/network. '
            + ' | '.join(errors)
        )

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

        last_error = None
        for attempt in range(3):
            try:
                response = requests.post(
                    base,
                    headers=headers,
                    json=payload,
                    timeout=90,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    retry_after = response.headers.get('Retry-After')
                    if attempt < 2:
                        delay = float(retry_after) if retry_after else 2 ** attempt
                        time.sleep(min(delay, 10))
                        continue
                response.raise_for_status()

                data = response.json()
                choices = data.get('choices') or []
                if not choices:
                    raise RuntimeError('Provider returned no choices: ' + str(data)[:500])

                message = choices[0].get('message') or {}
                text = message.get('content')
                if not text:
                    raise RuntimeError('Provider returned empty content: ' + str(data)[:500])
                return text
            except (requests.RequestException, ValueError, KeyError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(str(last_error)) from last_error

        raise RuntimeError(str(last_error))

    def _gemini(self, cfg, prompt, system, model):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {
            'x-goog-api-key': cfg['key'],
            'Content-Type': 'application/json',
        }
        payload = {
            'contents': [{'role': 'user', 'parts': [{'text': prompt}]}]
        }
        if system:
            payload['systemInstruction'] = {'parts': [{'text': system}]}

        response = requests.post(url, headers=headers, json=payload, timeout=90)
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
