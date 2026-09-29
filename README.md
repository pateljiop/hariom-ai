# Hariom AI

Windows-first personal AI workstation MVP.

## Current scope
- Multi-provider AI router with automatic fallback
- Desktop UI with live activity
- Local workspace read/write tools
- Terminal runner with risky-command approval gate
- Git-safe secret handling
- Free/low-cost provider pool with retry and quota fallback

## Provider pool

Hariom AI can use any configured provider and automatically skip providers
whose key is missing. Provider/model failures are also tried in sequence.

Current defaults:

- Gemini — gemini-flash-latest
- Groq — GPT-OSS 120B -> GPT-OSS 20B -> Qwen 3.8 27B
- Cerebras — GPT-OSS 120B
- OpenRouter — openrouter/free
- Mistral — devstral-small-latest
- Cloudflare Workers AI — @cf/openai/gpt-oss-120b
- OpenAI — gpt-5-mini

GitHub Models is not included in the active default pool.

The free-provider list is a source for discovery, not a credential source.
Only use your own legitimate API keys/tokens and each provider's published
free tier or terms. Free-tier limits can change.

### Cloudflare note

Cloudflare Workers AI uses an account-scoped OpenAI-compatible endpoint.
Set both CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID to enable it.
The router automatically sends the required cf-aig-gateway-id: default
header for Workers AI requests.

## Run

1. Python 3.11+
2. python -m venv .venv
3. .venv\\Scripts\\activate
4. pip install -r requirements.txt
5. Copy .env.example to .env and add your own keys
6. python -m app

Never commit .env or API keys.
