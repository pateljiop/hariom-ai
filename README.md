# Hariom AI

Windows-first personal AI workstation MVP.

## Current scope
- Native smart AI router with automatic provider/model fallback
- Provider health tracking and cooldowns
- Latency-aware routing
- Automatic retry for rate limits and server failures
- Desktop UI with live activity
- Local workspace read/write tools
- Terminal runner with risky-command approval gate
- Git-safe secret handling
- Free/low-cost provider pool

## Native Smart Router

Hariom AI now contains its own routing layer. Manifest is not required.

The router:

1. Detects configured providers.
2. Ranks healthy providers/models using recent success, failure and latency.
3. Temporarily cools down failed providers instead of repeatedly hitting them.
4. Retries rate-limit and server errors.
5. Falls through provider -> model -> next provider automatically.
6. Exposes live health information through status() for the UI.

Example:

Groq 120B -> 429
       ↓
Groq 20B -> failed
       ↓
Cerebras 120B -> success
       ↓
Next request remembers Cerebras as healthy

No provider switch is required from the user.

## Provider pool

Current direct-provider defaults:

- Gemini — gemini-flash-latest
- Groq — GPT-OSS 120B -> GPT-OSS 20B -> Qwen 3.8 27B
- Cerebras — GPT-OSS 120B
- OpenRouter — openrouter/free
- Mistral — devstral-small-latest
- Cloudflare Workers AI — @cf/openai/gpt-oss-120b
- OpenAI — gpt-5-mini

Only providers with configured credentials are attempted.

The free-provider list is a source for discovery, not a credential source.
Use your own legitimate API keys/tokens and each provider's published terms.
Free-tier limits can change.

### Router tuning

Optional .env settings:

- HARIOM_ROUTER_COOLDOWN=60
- HARIOM_ROUTER_RETRIES=2
- HARIOM_ROUTER_TIMEOUT=90

### Cloudflare

Cloudflare Workers AI requires both CLOUDFLARE_API_TOKEN and
CLOUDFLARE_ACCOUNT_ID. The router sends the gateway header required by the
configured Workers AI OpenAI-compatible endpoint.

## Run

1. Python 3.11+
2. python -m venv .venv
3. .venv\\Scripts\\activate
4. pip install -r requirements.txt
5. Copy .env.example to .env and add your own keys
6. python -m app

Never commit .env or API keys.
