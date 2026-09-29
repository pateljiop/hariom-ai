# Hariom AI

Windows-first personal AI workstation with a native OpenAI-compatible AI gateway.

## Smart router

Hariom AI does not require Manifest. It contains its own routing layer:

- Automatic provider/model fallback
- Persistent health and latency memory
- Quota-aware ranking from provider rate-limit headers
- Exponential cooldowns and circuit-breaker behavior
- Long disable window for authentication failures
- Capability-aware routing for tools and JSON responses
- Routing profiles: `hariom/auto`, `hariom/fast`, `hariom/coding`, `hariom/reasoning`, `hariom/free`
- Exact local response cache with configurable TTL
- Provider credentials stay in local `.env`

### Example profiles

Use `hariom/auto` for normal requests.

Use `hariom/fast` when latency matters.

Use `hariom/coding` for programming work.

Use `hariom/reasoning` for harder reasoning tasks.

Use `hariom/free` to bias routing toward providers commonly used without paid OpenAI/Anthropic billing.

## Local gateway

Start:

```bash
python -m app.gateway
```

Default endpoint:

```
http://127.0.0.1:8080/v1/chat/completions
```

The gateway supports:

- `/health`
- `/v1/models`
- OpenAI-style chat completions
- routing profiles as model aliases
- tool payload pass-through on compatible providers
- JSON response-format pass-through
- OpenAI-compatible SSE-style `stream=true` responses
- optional Bearer authentication
- automatic refusal to bind publicly without an API key

Example request:

```json
{
  "model": "hariom/coding",
  "messages": [
    {"role": "user", "content": "Explain this Python function"}
  ]
}
```

## Cache

Pure text requests can use the local SQLite response cache. Requests containing tools/tool messages or explicit `no_cache=true` bypass it.

Settings:

- `HARIOM_CACHE_ENABLED=1`
- `HARIOM_CACHE_TTL=300`

## Provider pool

Current defaults include Gemini, Groq, Cerebras, OpenRouter, Mistral, Cloudflare Workers AI and OpenAI. Only providers with valid local credentials are attempted.

Provider/model availability can change, so the router treats the configured pool as dynamic and falls back when a route fails.

## Development

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m compileall -q app tests
```

Never commit API keys or `.env`.
