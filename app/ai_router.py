import base64
import json
import time
from collections import defaultdict

import requests

from .cache import get as cache_get, key_for as cache_key, put as cache_put
from .config import (
    APP_DIR, CACHE_ENABLED, PROVIDERS, ROUTING_PROFILES,
    ROUTER_COOLDOWN_SECONDS, ROUTER_RETRIES, ROUTER_TIMEOUT_SECONDS,
)


class AIRouter:
    """Native gateway router: profiles, health, quota, cache and fallback."""

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

    def vision_chat(self, prompt, image_bytes, mime_type='image/png'):
        """Describe/analyze one local screenshot using a configured vision provider."""
        if not image_bytes:
            raise ValueError('image_bytes is required')
        encoded = base64.b64encode(image_bytes).decode('ascii')
        candidates = self._rank_vision()
        if not candidates:
            raise RuntimeError('No configured vision-capable AI provider is available.')

        messages = [{
            'role': 'user',
            'content': [
                {'type': 'text', 'text': str(prompt)},
                {'type': 'image_url', 'image_url': {
                    'url': 'data:' + mime_type + ';base64,' + encoded
                }},
            ],
        }]

        errors = []
        for name, model in candidates:
            try:
                self.activity.emit('VISION -> trying ' + name + ' (' + model + ')')
                started = time.monotonic()
                if name == 'gemini':
                    message, usage = self._gemini_request(
                        PROVIDERS[name], messages, model
                    )
                else:
                    message, usage = self._compatible_request(
                        name, PROVIDERS[name], messages, model
                    )
                latency = time.monotonic() - started
                self.health[name]['last_usage'] = usage or {}
                self._success(name, latency)
                self.activity.emit('VISION OK -> ' + name + ' in %.1fs' % latency)
                return message.get('content', ''), name
            except Exception as exc:
                self._failure(name, exc)
                errors.append(name + '/' + model + ': ' + str(exc))
                self.activity.emit('VISION FAILED -> ' + name)
        raise RuntimeError('All vision providers failed. ' + ' | '.join(errors))

    def verify_click_state(self, target, image_bytes, screen_size):
        """Use fresh vision to verify that a requested UI click produced the expected state."""
        if not target or not image_bytes or not screen_size or len(screen_size) != 2:
            raise ValueError("target, image_bytes and screen_size are required")
        prompt = (
            "Verify the result of a recent computer click. Target: " + str(target) + "\n"
            "Inspect the CURRENT screenshot only. Decide whether that target is now visibly "
            "active/selected/open as expected after a click. For a browser tab, the target tab "
            "must be visibly selected/active in the browser chrome. Do not treat mere visibility "
            "as success. Return ONLY JSON: "
            "{\"verified\":true,\"confidence\":0.0,\"reason\":\"...\"} or "
            "{\"verified\":false,\"confidence\":0.0,\"reason\":\"...\"}. "
            "Never guess."
        )
        text, provider = self.vision_chat(prompt, image_bytes)
        raw = str(text).strip()
        if raw.startswith("```"):
            raw = raw.strip("`").strip()
            if raw.lower().startswith("json"):
                raw = raw[4:].strip()
        try:
            data = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Vision click verification returned invalid JSON.") from exc
        if not isinstance(data, dict):
            raise RuntimeError("Vision click verification returned invalid data.")
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
        verified = bool(data.get("verified")) and confidence >= 0.70
        return {
            "verified": verified,
            "confidence": confidence,
            "reason": str(data.get("reason", "Verified." if verified else "State not verified.")),
            "provider": provider,
        }
    def locate_on_screen(self, target, image_bytes, screen_size):
        """Locate a visible UI target and return safe pixel coordinates."""
        if not target or not image_bytes or not screen_size or len(screen_size) != 2:
            raise ValueError("target, image_bytes and screen_size are required")
        width, height = int(screen_size[0]), int(screen_size[1])
        if width <= 0 or height <= 0:
            raise ValueError("screen_size must be positive")
        target_text = str(target).strip()
        is_tab = "tab" in target_text.lower()
        vision_width, vision_height = width, height
        vision_image = image_bytes
        region_hint = ""
        if is_tab:
            # Tabs are constrained to browser chrome. Crop the screenshot before
            # sending it to vision so page content cannot be mistaken for a tab.
            vision_height = max(80, int(height * 0.18))
            try:
                from PIL import Image
                import io
                with Image.open(io.BytesIO(image_bytes)) as source:
                    crop_height = min(source.height, max(1, int(source.height * 0.18)))
                    cropped = source.crop((0, 0, source.width, crop_height))
                    buffer = io.BytesIO()
                    cropped.save(buffer, format="PNG")
                    vision_image = buffer.getvalue()
                    vision_width = source.width
                    vision_height = crop_height
            except Exception:
                # If cropping is unavailable, keep the original image and retain
                # the strict post-location region check below.
                pass
            region_hint = (
                "This screenshot is cropped to the browser's top tab/chrome region. "
                "Coordinates must be relative to this cropped image. "
                "Search ONLY for the requested browser tab; do not use page content.\n"
            )
        prompt = (
            "Locate this exact target on the screenshot: " + target_text + "\n"
            + region_hint
            + "Return ONLY JSON with found, x/y center pixels, confidence, and label. "
            + "If clearly visible you may instead return bbox as [x1,y1,x2,y2] in pixels. "
            + "Never guess. If not clearly visible return found=false with a reason."
        )
        text, provider = self.vision_chat(prompt, vision_image)
        raw = str(text).strip()
        if raw.startswith("```"):
            raw = raw.strip("`").strip()
            if raw.lower().startswith("json"):
                raw = raw[4:].strip()
        data = None
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            pass

        # Vision models sometimes return a bare JSON array instead of the
        # requested object. Treat a four-number array as a pixel bbox.
        if isinstance(data, list) and len(data) == 4:
            try:
                data = {
                    "found": True,
                    "bbox_pixels": [float(v) for v in data],
                    "confidence": 0.85,
                    "label": str(target),
                }
            except (TypeError, ValueError):
                data = None

        if data is None:
            import re
            # Gemini/OpenRouter-style grounding tags may use either
            # [ymin,xmin,ymax,xmax] or [[ymin,xmin,ymax,xmax]].
            tag = re.search(
                r"<box>\s*\[\s*\[?\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*"
                r"([0-9.]+)\s*,\s*([0-9.]+)\s*\]?\s*\]\s*</box>",
                raw,
                re.I,
            )
            bare = re.search(
                r"\[\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*\]",
                raw,
            )
            match = tag or bare
            if match:
                vals = [float(x) for x in match.groups()]
                if tag:
                    data = {"found": True, "bbox_norm": vals, "confidence": 0.85, "label": str(target)}
                else:
                    data = {"found": True, "bbox_pixels": vals, "confidence": 0.85, "label": str(target)}
        if not isinstance(data, dict):
            raise RuntimeError("Vision locator returned an unsupported response format.")
        if not data.get("found"):
            return {"found": False, "reason": str(data.get("reason", "Target not found.")), "provider": provider}
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
        if "bbox_pixels" in data:
            b = data["bbox_pixels"]
            if not isinstance(b, (list, tuple)) or len(b) != 4:
                raise RuntimeError("Vision locator returned an invalid pixel bounding box.")
            x1, y1, x2, y2 = [float(v) for v in b]
            if not (0 <= x1 < x2 <= vision_width and 0 <= y1 < y2 <= vision_height):
                raise RuntimeError("Vision locator returned out-of-screen pixel bounds.")
            x, y = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        elif "bbox_norm" in data:
            b = data["bbox_norm"]
            if not isinstance(b, (list, tuple)) or len(b) != 4:
                raise RuntimeError("Vision locator returned an invalid bounding box.")
            ymin, xmin, ymax, xmax = [float(v) for v in b]
            if not (0 <= ymin <= ymax <= 1000 and 0 <= xmin <= xmax <= 1000):
                raise RuntimeError("Vision locator returned invalid normalized bounds.")
            x = ((xmin + xmax) / 2000.0) * vision_width
            y = ((ymin + ymax) / 2000.0) * vision_height
        else:
            try:
                x, y = float(data["x"]), float(data["y"])
            except (KeyError, TypeError, ValueError) as exc:
                raise RuntimeError("Vision locator returned invalid coordinates.") from exc

        # The crop keeps the original screen origin and pixel scale; only its
        # height is reduced. Therefore vision pixel coordinates map directly to
        # the same top-left screen coordinates. The desktop screenshot is already
        # normalized to screen_size() by ComputerController.
        if confidence < 0.70:
            return {"found": False, "reason": "Target location confidence is too low.", "confidence": confidence, "provider": provider}

        # A browser-tab request must resolve inside the actual tab strip, even
        # when the provider returns a plausible-looking coordinate.
        final_x = max(0, min(width - 1, int(round(x))))
        final_y = max(0, min(height - 1, int(round(y))))
        if is_tab:
            max_y = max(80, int(height * 0.18))
            if final_y > max_y:
                return {
                    "found": False,
                    "reason": "Vision result is outside the browser tab strip.",
                    "confidence": confidence,
                    "provider": provider,
                }
        return {
            "found": True,
            "x": final_x,
            "y": final_y,
            "label": str(data.get("label", target)),
            "confidence": confidence,
            "provider": provider,
        }
    def _rank_vision(self):
        now = time.time()
        candidates = []
        for name, cfg in PROVIDERS.items():
            if not self._configured(name, cfg) or not cfg.get('supports_vision'):
                continue
            s = self.health[name]
            if s['cooldown_until'] > now or s['disabled_until'] > now:
                continue
            models = cfg.get('models') or [cfg.get('model')]
            for index, model in enumerate(models):
                if not model:
                    continue
                score = (
                    s['successes'] * 5
                    - s['failures'] * 25
                    - min(s['latency'], 60)
                    + cfg.get('speed', 5) * 1.5
                    - index * 3
                )
                candidates.append((score, name, model))
        candidates.sort(reverse=True)
        return [(name, model) for _, name, model in candidates]

    def chat_messages(self, messages, preferred=None, profile='hariom/auto',
                      tools=None, tool_choice=None, response_format=None,
                      use_cache=True):
        """Compatibility wrapper for agent calls with optional request controls."""
        return self.chat_request(
            messages,
            preferred=preferred,
            profile=profile,
            tools=tools,
            tool_choice=tool_choice,
            response_format=response_format,
            use_cache=use_cache,
        )

    def chat_request(self, messages, preferred=None, profile='hariom/auto',
                     tools=None, tool_choice=None, response_format=None,
                     use_cache=True):
        if not messages:
            raise ValueError('messages is required')
        if profile not in ROUTING_PROFILES:
            profile = 'hariom/auto'

        cacheable = (
            CACHE_ENABLED and use_cache and not tools and not tool_choice
            and not response_format
            and all(m.get('role') != 'tool' for m in messages)
        )
        key = cache_key(messages, f'{profile}|preferred={preferred}')
        if cacheable:
            cached = cache_get(key)
            if cached:
                self.activity.emit('AI CACHE -> hit')
                return cached['message'], cached['provider']

        candidates = self._rank(preferred=preferred, profile=profile, tools=tools, response_format=response_format)
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

    def _rank(self, preferred=None, profile='hariom/auto', tools=None, response_format=None):
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
            models = cfg.get('models') or [cfg.get('model')]
            for index, model in enumerate(models):
                if not model:
                    continue
                score = (
                    (1000 if name == preferred else 0)
                    + s['successes'] * 5 - s['failures'] * 25
                    - min(s['latency'], 60) - index * 3
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
        candidates.sort(reverse=True)
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
            s['disabled_until'] = time.time() + 86400
        elif '429' in text:
            s['cooldown_until'] = time.time() + min(ROUTER_COOLDOWN_SECONDS * (2 ** min(s['failures'] - 1, 4)), 3600)
        else:
            s['cooldown_until'] = time.time() + min(ROUTER_COOLDOWN_SECONDS * (2 ** min(s['failures'] - 1, 4)), 3600)
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
            self.STATE_FILE.write_text(json.dumps({n: dict(s) for n, s in self.health.items()}, indent=2), encoding='utf-8')
        except OSError:
            pass

    def _compatible_request(self, name, cfg, messages, model, tools=None, tool_choice=None, response_format=None):
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
            if isinstance(content, list):
                parts = []
                for item in content:
                    if item.get('type') == 'text':
                        parts.append({'text': item.get('text', '')})
                    elif item.get('type') == 'image_url':
                        url_value = item.get('image_url', {}).get('url', '')
                        if ';base64,' in url_value:
                            mime, encoded = url_value.split(';base64,', 1)
                            parts.append({
                                'inline_data': {
                                    'mime_type': mime.replace('data:', ''),
                                    'data': encoded,
                                }
                            })
                contents.append({'role': 'user', 'parts': parts})
            elif isinstance(content, str):
                contents.append({'role': 'model' if role == 'assistant' else 'user', 'parts': [{'text': content}]})
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
