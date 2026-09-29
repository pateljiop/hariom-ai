# Hariom AI

Windows-first personal AI workstation MVP.

## Current scope
- Multi-provider AI router with automatic fallback
- Optional Manifest self-hosted meta-router
- Desktop UI with live activity
- Local workspace read/write tools
- Terminal runner with risky-command approval gate
- Git-safe secret handling
- Free/low-cost provider pool with retry and quota fallback

## Provider pool

Hariom AI can use any configured provider and automatically skip providers
whose key is missing. Provider/model failures are also tried in sequence.

If Manifest is configured, it is tried first as a local smart-routing layer
using the virtual model `manifest/auto`. If Manifest is unavailable, Hariom AI
continues directly through the provider pool.

Current direct-provider defaults:

- Gemini — gemini-flash-latest
- Groq — GPT-OSS 120B -> GPT-OSS 20B -> Qwen 3.8 27B
- Cerebras — GPT-OSS 120B
- OpenRouter — openrouter/free
- Mistral — devstral-small-latest
- Cloudflare Workers AI — @cf/openai/gpt-oss-120b
- OpenAI — gpt-5-mini

GitHub Models is not included in the active default pool.

### Manifest

Manifest is optional. Self-host it with Docker, then create an agent API key
in its dashboard and put that key in `MNFST_API_KEY`.

Default local endpoint:

`http://localhost:2099/v1/chat/completions`

Default virtual model:

`manifest/auto`

Manifest is an OpenAI-compatible gateway with automatic model routing and
fallback. It can connect multiple provider credentials behind one endpoint.
If the local Manifest service is down, Hariom AI automatically falls back to
its direct providers.

### Other provider setup

The free-provider list is a source for discovery, not a credential source.
Only use your own legitimate API keys/tokens and each provider's published
free tier or terms. Free-tier limits can change.

Cloudflare Workers AI requires both `CLOUDFLARE_API_TOKEN` and
`CLOUDFLARE_ACCOUNT_ID`. The router sends the required gateway header for
the configured Workers AI OpenAI-compatible endpoint.

## Run

1. Python 3.11+
2. `python -m venv .venv`
3. `.venv\\Scripts\\activate`
4. `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and add your own keys
6. `python -m app`

Never commit `.env` or API keys.
