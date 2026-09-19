# Hariom AI

Windows-first personal AI workstation.

## Current scope
- Multi-provider AI router with automatic fallback
- Desktop UI with live activity
- Local workspace read/write tools
- Terminal runner with risky-command approval gate
- V1 agent execution loop
- Git-safe secret handling

## Agent workflow

Use **Run Agent** for tasks that should interact with the selected workspace.

Current agent tools:
- `project_context`
- `vscode_context`
- `list_workspace`
- `read_file`
- `write_file`
- `patch_file`
- `run_command`
- `run_tests`
- `git_status`
- `git_diff`
- `git_log`
- `git_branch`

`project_context` is a read-only project inspection tool. It reports the selected workspace, bounded file inventory, common project manifests, file-extension counts, Git branch/status when available, and Windows/VS Code availability. `vscode_context` adds read-only VS Code window titles plus best-effort active file/project detection from the Windows VS Code window title.

The agent asks the configured AI provider for a structured plan, executes only the supported tools, records operational activity in the UI, and then produces a factual completion report.

Safety boundaries:
- File paths are restricted to the selected workspace.
- Terminal commands run with the workspace as their working directory.
- Existing terminal risky-command checks remain active.
- Project context and Git context tools are read-only.
- Destructive Git operations are not planner tools.
- Protected actions use the approval mechanism where applicable.

## Run

1. Python 3.11+
2. `python -m venv .venv`
3. `.venv\\Scripts\\activate`
4. `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and add your own keys
6. `python -m app`

## Run automated tests

From the repository root with the virtual environment activated:

`python -m unittest discover -s tests -v`

The v1 test suite covers provider retry behavior, workspace path safety, file read/write, and terminal safety.

Never commit `.env` or API keys.

## First agent test

After starting the app, select a test workspace and use **Run Agent** with:

> Create a file named `agent_test.txt` containing exactly `Hariom AI agent works`, then run a command to print the file and report the result.

Check the **Live Activity** panel and the created file before considering the agent workflow verified.
