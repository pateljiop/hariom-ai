# Hariom AI — Project Handoff / Master Context

> Source of truth for continuing development in another ChatGPT/AI coding agent. Read this before changing the project.

## 1. Project identity

Project: Hariom AI
Repository: https://github.com/pateljiop/hariom-ai
Owner: pateljiop
Target platform: Windows desktop first
Purpose: Personal-use local AI agent / AI workstation for the user's own laptop. NOT a public SaaS.

The user wants the project built incrementally and tested properly. Do not jump to the final Jarvis/corner-agent vision before the core v1 is stable.

## 2. Long-term vision

A personal AI assistant similar in spirit to Jarvis/desktop agents that can:
- understand natural-language tasks
- work with local projects/files
- write, debug, refactor and create code
- use terminal commands
- work with VS Code/local development projects
- research/use the browser
- manage Git/GitHub workflows
- analyze websites
- eventually help with Instagram/viral-content research and content creation
- eventually create/edit videos
- eventually create PPTs
- maintain project context/memory
- run background/scheduled tasks
- show useful operational activity
- have permission/approval controls
- eventually package as a Windows .exe
- eventually support self-update/rollback

APK generation/reading is removed from current scope. Mobile app is also removed from current scope. Focus on Windows desktop.

## 3. Current product decision

The user explicitly decided:

FIRST make Hariom AI v1 a properly working, stable core project.

Only after v1 is genuinely successful should the floating/corner desktop-agent update be added.

Do NOT prioritize corner UI, continuous screen awareness, Instagram automation, video tools, etc. yet.

## 4. Current v1 scope

Current MVP/foundation contains:
- Multi-provider AI router with fallback
- Desktop UI
- Live activity/status messages
- Workspace/file read/write tools
- Terminal runner
- Risky-command blocking/approval concept
- Local .env configuration
- Windows-first execution

Current files:
- README.md
- requirements.txt
- .env.example
- .gitignore
- app/__init__.py
- app/__main__.py
- app/main.py
- app/config.py
- app/activity.py
- app/ai_router.py
- app/workspace.py
- app/terminal.py
- app/ui.py

Before claiming the project is fully working, verify actual current contents and test where possible. This is a foundation/MVP, not yet the full autonomous agent.

## 5. Architecture

Conceptually:

User
  ↓
Desktop UI
  ↓
AI Router
  ↓
Provider fallback
  ├── OpenAI-compatible providers
  └── Gemini
  ↓
Agent/tool layer
  ├── Workspace/files
  └── Terminal
  ↓
Activity/Event Bus
  ↓
UI status/logs

Intended providers include:
- Google Gemini
- Groq
- OpenRouter
- Cerebras
- OpenAI
- other legitimate providers later if useful

Free tiers/quotas change. Verify current provider documentation before relying on a specific free quota.

## 6. Security and API keys

Only legitimate API keys supplied by the user may be used.

Never:
- collect leaked/shared API keys
- hard-code API keys
- commit .env
- expose secrets in logs
- put secrets into GitHub README/issues

Keys should remain local and ideally become encrypted/securely stored as the project matures.

Potentially destructive actions require explicit approval:
- deleting files
- dangerous terminal commands
- pushing directly to main
- external publishing/sending
- unknown software installation

Prefer:
branch → edit → test → diff → approval → merge

## 7. Activity transparency

The user wants useful operational activity, not hidden chain-of-thought.

Show:
- task received
- file being read
- command being run
- provider being called
- test started/completed
- files changed
- git diff summary
- next action
- success/error

Do not expose or fabricate private chain-of-thought. Show concise, inspectable action/status information.

## 8. Basic run instructions

Expected setup:

git clone https://github.com/pateljiop/hariom-ai.git
cd hariom-ai
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m app

Python 3.11+ is the intended baseline.

If setup fails, diagnose the actual error and update the repository rather than guessing.

## 9. Development roadmap

### Phase 1 — Stabilize v1 (CURRENT)
1. Verify every current module.
2. Make the app launch reliably on Windows.
3. Validate provider configuration and fallback.
4. Validate workspace/file operations.
5. Validate terminal execution and safety.
6. Improve error handling.
7. Add useful tests.
8. Improve README/setup instructions.
9. Test the basic workflow end-to-end.

### Phase 2 — Agent execution
After v1 is stable:
- better tool calling
- task planning
- file editing
- test execution
- structured action results
- git integration
- approval workflow

### Phase 3 — Development integrations
- VS Code/project awareness
- Git
- GitHub issues/branches/commits/PRs/reviews
- browser automation/research

### Phase 4 — Desktop agent
ONLY after v1 success:
- floating corner UI
- always-on-top mini window
- minimize to AI orb
- pause/stop
- active-window detection
- screen context
- controlled desktop awareness

### Phase 5 — Advanced tools
- website analysis
- Instagram/content research and creation
- video editing
- PPT generation
- background/scheduled tasks
- memory/project context

### Phase 6 — Packaging/reliability
- Windows .exe
- installer
- logs
- crash recovery
- backup before updates
- self-update
- rollback if update fails

## 10. Future corner-agent design

Future UI:

Windows desktop
┌─────────────────────────────────────┐
│ VS Code / Chrome / Terminal         │
│                                     │
│                         ┌─────────┐ │
│                         │ 🤖      │ │
│                         │ Hariom  │ │
│                         │ AI      │ │
│                         │ [Pause] │ │
│                         │ [Stop]  │ │
│                         └─────────┘ │
└─────────────────────────────────────┘

It may eventually explain useful current context:
- active app
- current project/file
- terminal activity
- browser page
- detected errors
- current task

Continuous screen monitoring should be opt-in and privacy-controlled.

## 11. Permission model

Final agent should have granular controls:
- Screen analysis ON/OFF
- Active-window monitoring ON/OFF
- File monitoring ON/OFF
- Browser context ON/OFF
- AI suggestions ON/OFF

Risky actions:
- Allow once
- Always allow where appropriate
- Deny

Do not give unrestricted destructive control by default.

## 12. Product principles

- Build working software, not just architecture diagrams.
- Do not claim a feature works until implemented and tested.
- Prefer small, testable increments.
- Preserve existing working functionality.
- Do not overwrite user work without checking current repository state.
- Keep secrets out of Git.
- Keep the user in control of risky actions.
- Explain failures honestly.
- If requirements are ambiguous, state the ambiguity and make the smallest safe assumption.
- User prefers direct/objective answers, pros/cons/tradeoffs, and no unnecessary flattery.

## 13. Do NOT do right now

Do not start with:
- floating corner UI
- full screen surveillance
- mobile app
- APK tools
- autonomous Instagram posting
- video editor
- giant all-in-one rewrite

These belong to later phases after v1 is stable.

## 14. Collaboration rule for another AI agent

When continuing:
1. Read this file first.
2. Inspect the actual repository before changing anything.
3. Check README and source files.
4. Make a concrete implementation plan.
5. Implement in small batches.
6. Test after each meaningful change.
7. Update this file when architecture/scope decisions materially change.
8. Keep a clear TODO/status section if useful.
9. Do not assume a feature exists just because it is listed in the roadmap.
10. In progress reports distinguish IMPLEMENTED, TESTED, and PLANNED.

## 15. Current status

STATUS: MVP foundation created; full v1 still needs stabilization and end-to-end verification.

CURRENT GOAL: Make the core Windows desktop AI workstation reliable first.

DEFERRED GOAL: Floating/corner desktop agent after v1 success.
