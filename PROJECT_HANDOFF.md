# Hariom AI — Project Handoff / Master Context

> Source of truth for continuing development in another ChatGPT/AI coding agent. Read this before changing the project.

## 1. Project identity
Project: Hariom AI
Repository: https://github.com/pateljiop/hariom-ai
Owner: pateljiop
Target platform: Windows desktop first
Purpose: Personal-use local AI agent / AI workstation for the user's own laptop. NOT a public SaaS.

The user wants the project built incrementally and tested properly. The core MVP and Agent V2 have now been verified; continue with the next phase rather than restarting the foundation.

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

APK generation/reading and mobile app support are removed from current scope.

## 3. Current product decision
The core Windows desktop project was built and tested before moving to the floating/corner-agent vision.

Do not prioritize corner UI, continuous screen awareness, Instagram automation, video tools, etc. ahead of the current developer-integration work.

## 4. Current verified scope
The current project contains:
- Multi-provider AI router with fallback
- Desktop UI
- Live activity/status messages
- Workspace/file read/write/patch tools
- Terminal runner with risky-command protection
- Local .env configuration
- Agent planning/execution loop
- Structured tool/action results
- Test runner integration
- Git read-only context tools
- Permission/approval infrastructure
- Automated regression tests

## 5. Verification record
- Automated suite: 12/12 tests passed
- Real Windows Agent workflow passed
- Calculator project created in `A:\project`
- Agent test command exited with code 0
- Independent Windows run passed 5/5 calculator tests
- Real provider fallback observed: Gemini → Mistral → Groq
- The tested Agent workflow was: natural-language request → planning → workspace inspection → file creation → test execution → completion

Distinguish IMPLEMENTED, TESTED, and PLANNED in all future progress reports.

## 6. Architecture
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
  ├── Terminal/tests
  └── Git read-only context
  ↓
Activity/Event Bus
  ↓
UI status/logs

## 7. Security and API keys
Only legitimate API keys supplied by the user may be used.

Never:
- collect leaked/shared API keys
- hard-code API keys
- commit .env
- expose secrets in logs
- put secrets into GitHub README/issues

Potentially destructive actions require explicit approval.

## 8. Activity transparency
Show useful operational activity, not hidden chain-of-thought:
- task received
- file being read
- command being run
- provider being called
- test started/completed
- files changed
- git diff summary
- next action
- success/error

## 9. Development roadmap

### Phase 1 — Core stabilization
COMPLETED AND VERIFIED.

### Phase 2 — Agent execution
COMPLETED AND VERIFIED.

### Phase 3 — Developer integrations (NEXT)
- VS Code/project awareness
- GitHub issues/branches/commits/PRs/reviews
- browser automation/research
- website analysis

### Phase 4 — Desktop agent
After the core developer integrations are sufficiently stable:
- floating corner UI
- always-on-top mini window
- minimize to AI orb
- pause/stop
- active-window detection
- optional screen context
- controlled desktop awareness

### Phase 5 — Advanced tools
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

## 10. Permission model
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

## 11. Product principles
- Build working software, not just architecture diagrams.
- Do not claim a feature works until implemented and tested.
- Prefer small, testable increments.
- Preserve existing working functionality.
- Keep secrets out of Git.
- Keep the user in control of risky actions.
- Explain failures honestly.
- If requirements are ambiguous, state the ambiguity and make the smallest safe assumption.
- User prefers direct/objective answers, pros/cons/tradeoffs, and no unnecessary flattery.

## 12. Collaboration rule
When continuing:
1. Read this file first.
2. Inspect the actual repository before changing anything.
3. Check README and source files.
4. Make a concrete implementation plan.
5. Implement in small batches.
6. Test after each meaningful change.
7. Update this file when architecture/scope decisions materially change.
8. Distinguish IMPLEMENTED, TESTED, and PLANNED.
9. Do not assume a feature exists just because it is listed in the roadmap.
