# Hariom AI

Windows-first personal AI workstation MVP.

## What makes it different

Hariom AI has its own native smart-router instead of requiring Manifest or another gateway.

### Router capabilities
- Automatic provider and model fallback
- Health-aware ranking using success rate and latency
- Persistent provider health across restarts
- Exponential cooldown for repeatedly failing routes
- Rate-limit and server-error retries
- Reads common rate-limit headers and tracks remaining request/token budget
- Local OpenAI-compatible gateway for other apps
- Provider health endpoint
- No provider switch required by the user

Example:

Groq 120B -> 429
       ↓
Groq 20B -> failed
       ↓
Cerebras 120B -> success
       ↓
Next request uses the remembered health/quota state

## Provider pool

Current direct-provider defaults:
- Gemini — gemini-flash-latest
- Groq — GPT-OSS 120B -> GPT-OSS 20B -> Qwen 3.8 27B
- Cerebras — GPT-OSS 120B
- OpenRouter — openrouter/free
- Mistral — devstral-small-latest
- Cloudflare Workers AI — @cf/openai/gpt-oss-120b
- OpenAI — gpt-5-mini

Only configured providers are attempted.

## Local gateway

Hariom AI can expose the router as an OpenAI-compatible local API.

Start it with:

python -m app.gateway

Default endpoint:

http://127.0.0.1:8080/v1/chat/completions

Models:

http://127.0.0.1:8080/v1/models

Health:

http://127.0.0.1:8080/health

Set HARIOM_GATEWAY_API_KEY in .env if another local application should authenticate.
The gateway binds to 127.0.0.1 by default and is therefore not exposed to the LAN.

## Router tuning

Optional .env settings:
- HARIOM_ROUTER_COOLDOWN=60
- HARIOM_ROUTER_RETRIES=2
- HARIOM_ROUTER_TIMEOUT=90

## Inspiration

Recent open-source gateways show useful patterns such as health-aware routing, quota-aware fallback, model aliases, circuit breakers, semantic caching, tool calling, streaming, multimodal routing and encrypted key storage. Hariom AI implements the lightweight pieces first and keeps provider credentials local.

## Run

1. Python 3.11+
2. python -m venv .venv
3. .venv\\Scripts\\activate
4. pip install -r requirements.txt
5. Copy .env.example to .env and add your own keys
6. python -m app

Never commit .env or API keys.
