# Hariom AI

Hariom AI is a Windows-first **personal AI workstation / Personal AI OS**.

The provider router is internal infrastructure. The product is the personal agent that can understand a request, use local tools, verify the result and keep useful local memory.

## Personal AI architecture

- Brain: multi-provider routing with automatic fallback
- Memory: local SQLite facts, preferences and project notes
- Agent: plan -> execute -> verify
- Tools: workspace files and terminal actions
- Safety: approval gate for writes and terminal commands
- Workspace: active project directory with path containment
- UI: chat mode plus task execution mode
- Health: persistent provider health, cooldown and quota-aware routing

## Current agent flow

A task follows:

1. Understand the request
2. Build a structured execution plan
3. Execute available tools
4. Pause when an approval-gated action is required
5. Resume from the blocked step after approval
6. Verify that every executed step produced a result
7. Report the actual task state

The agent never treats a planned action as completed.

## Local memory

Memory is stored locally in SQLite under the Hariom AI runtime directory.

Memory categories are intended for useful information such as:

- preferences
- project notes
- recurring facts
- task context

Do not store passwords, API keys or other secrets in memory.

## Local tools

The first tool set is intentionally small:

- list files
- read files
- write files
- run terminal commands

Write and terminal actions require explicit approval when invoked by the agent.

## Smart router

Hariom AI has its own routing layer:

- automatic provider/model fallback
- persistent health and latency memory
- quota-aware ranking from provider headers
- exponential cooldowns and circuit-breaker behavior
- capability-aware routing
- profiles: hariom/auto, hariom/fast, hariom/coding, hariom/reasoning, hariom/free
- exact local response cache
- local credentials from .env

Provider availability changes over time, so only configured and compatible providers are attempted.

## Desktop app

Start the personal AI UI with:

```bash
python -m app
```

The UI provides:

- Ask AI for normal conversation
- Run Task for tool-using work
- approval and resume for protected actions
- active workspace selection
- live activity log

## Local gateway

The OpenAI-compatible gateway remains available as an infrastructure component:

```bash
python -m app.gateway
```

Default endpoint:

```
http://127.0.0.1:8080/v1/chat/completions
```

It supports profiles, compatible tool payload pass-through, JSON response-format pass-through and a simple SSE-style response. It is not the main product identity.

## Development

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
python -m compileall -q app tests
python -m unittest discover -s tests -v
```

Never commit API keys or .env.


## Agent intelligence layer

The personal agent now also has:

- **Workspace context**: deterministic project snapshot with important files and ignored build/vendor directories.
- **Skills**: file-backed instructions under `workspace/skills/<name>/SKILL.md`, loaded progressively when relevant.
- **Recovery loop**: failed tool steps can receive one bounded repair attempt instead of immediately ending the task.
- **Evidence verification**: completion checks inspect tool status/output and verify common filesystem outcomes.
- **Resumable execution**: approval pauses preserve the task state and resume from the blocked step.

These ideas are intentionally implemented as small Python modules so the personal-agent core stays understandable and testable.
