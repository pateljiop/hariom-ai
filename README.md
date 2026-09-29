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
whose key is missing. The current defaults include:

- Gemini
- Groq — current GPT-OSS 120B model
- Cerebras — GPT-OSS 120B
- OpenRouter — `openrouter/free`
- Mistral
- GitHub Models
- OpenAI

The free-provider list is a source for discovery, not a credential source.
Only use your own legitimate API keys/tokens and each provider's published
free tier or terms.

## Run

1. Python 3.11+
2. `python -m venv .venv`
3. `.venv\\Scripts\\activate`
4. `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and add your own keys
6. `python -m app`

Never commit `.env` or API keys.
