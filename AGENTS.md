# AGENTS.md — Hariom AI Coding Agent Instructions

Read this file and PROJECT_HANDOFF.md before making changes.

## Mission
Build Hariom AI as a Windows-first personal AI workstation. The immediate mission is to make v1 reliable. The floating corner-agent is explicitly deferred until v1 succeeds.

## Non-negotiable workflow
1. Inspect the current repository before editing.
2. Distinguish IMPLEMENTED, TESTED, and PLANNED.
3. Make small, reversible changes.
4. Test after meaningful changes.
5. Never claim a feature works without evidence.
6. Preserve existing working behavior.
7. Never commit secrets.
8. Ask for approval for destructive/high-risk actions.
9. Prefer branch -> edit -> test -> diff -> approval -> merge for substantial changes.
10. Update project documentation when architecture or scope decisions change.

## Current priority
Stabilize the existing Python desktop MVP:
- app launch
- provider configuration/fallback
- workspace/file operations
- terminal execution and safety
- activity logging
- error handling
- tests
- Windows setup documentation
- end-to-end basic workflow

## Deferred until v1 is successful
- floating corner UI
- always-on-top agent/orb
- continuous screen awareness
- full desktop surveillance
- mobile app/APK
- autonomous Instagram posting
- video editor
- giant all-in-one rewrite

## Safety
Never hard-code or expose API keys. Never commit .env. Do not execute destructive commands without approval. Avoid direct pushes to main when a safer branch/PR workflow is practical.

## Transparency
Show operational status such as files read, commands run, tests, provider calls, files changed, and errors. Never expose or fabricate private chain-of-thought.

## Communication
Be direct and technical. Report what changed, what was tested, what remains, and any uncertainty.
