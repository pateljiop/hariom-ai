# Architecture & Product Decisions

## Decision 001 — Windows first
The first target is a Windows desktop application. Mobile is not current scope.

## Decision 002 — Core before corner agent
The user explicitly wants the core project completed and successful before adding the floating desktop corner-agent experience.

## Decision 003 — Personal-use agent
This is a personal laptop AI workstation, not a public SaaS. Design for local workspace access and user-controlled permissions.

## Decision 004 — Multi-provider AI
Support multiple legitimate providers with fallback. Candidate providers include Gemini, Groq, OpenRouter, Cerebras and OpenAI. Provider quotas/availability must be verified when relevant.

## Decision 005 — Secrets stay local
API keys belong in local configuration/secure storage, never in source control, logs, README files or issues.

## Decision 006 — Visible operational activity
The UI should show useful action/status information: current task, files, commands, tests, provider, changes, errors and next action. Private model reasoning must not be exposed.

## Decision 007 — Risky actions require approval
Deleting files, dangerous terminal commands, direct production/main pushes, external publishing/sending and unknown software installation require explicit approval.

## Decision 008 — Incremental development
Do not replace the entire project just to add a feature. Inspect, implement, test, review, then proceed.

## Decision 009 — Future corner agent
After v1, the desktop UI may become a small always-on-top corner assistant with pause/stop controls and optional screen/active-window context.

## Decision 010 — APK removed
APK generation/reading was removed from the current roadmap.
