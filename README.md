# Hariom AI

Windows-first personal AI workstation MVP.

## Current scope
- Multi-provider AI router with automatic fallback
- Desktop UI with live activity
- Local workspace read/write tools
- Terminal runner with risky-command approval gate
- Git-safe secret handling

## Run
1. Python 3.11+
2. python -m venv .venv
3. .venv\\Scripts\\activate
4. pip install -r requirements.txt
5. Copy .env.example to .env and add your own keys
6. python -m app

Never commit .env or API keys.