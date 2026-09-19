# Hariom AI

Windows-first personal AI workstation.

## Current scope
- Multi-provider AI router with automatic fallback
- Desktop UI with live activity
- Local workspace read/write tools
- Terminal runner with risky-command approval gate
- V1 agent execution loop
- Git-safe secret handling

## V1 agent workflow

Use **Run Agent** for tasks that should interact with the selected workspace.

Current agent tools:
- `list_workspace`
- `read_file`
- `write_file`
- `run_command`

The agent first asks the configured AI provider for a structured plan, executes only the supported tools, records operational activity in the UI, and then produces a factual completion report.

Safety boundaries:
- File paths are restricted to the selected workspace.
- Terminal commands run with the workspace as their working directory.
- Existing terminal risky-command checks remain active.
- The agent cannot delete files, perform disk operations, change the registry, shut down Windows, or force-push Git.
- This v1 does not yet have an interactive approval UI for blocked actions.

## Run

1. Python 3.11+
2. `python -m venv .venv`
3. `.venv\\Scripts\\activate`
4. `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and add your own keys
6. `python -m app`

Never commit `.env` or API keys.

## First agent test

After starting the app, select a test workspace and use **Run Agent** with:

> Create a file named `agent_test.txt` containing exactly `Hariom AI agent works`, then run a command to print the file and report the result.

Check the **Live Activity** panel and the created file before considering the agent workflow verified.
