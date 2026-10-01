# Web Intelligence / Browser Integration Candidates

Status: planning only. This PR intentionally does not replace or rewrite existing Hariom AI browser/web execution code.

## Candidate repositories

- Agent-Reach — internet/source access, multi-platform discovery/read adapters, primary/fallback routing, capability diagnostics.
  - Source: https://github.com/Panniantong/Agent-Reach
- Scrapling — adaptive extraction, dynamic fetching, persistent sessions, XHR/API capture, clean/sanitized content for LLM context.
  - Source: https://github.com/D4Vinci/Scrapling
- Patchright Enhanced — Patchright/Chrome session management and browser execution ideas.
  - Source: https://github.com/whaleyxbt/patchright-enhanced

## Proposed Hariom AI integration

### High priority
1. Agent-Reach capability adapters for supported internet sources.
2. Fallback/health-check pattern for source availability.
3. Scrapling adaptive page extraction.
4. Scrapling clean/sanitized page -> structured LLM context.
5. Scrapling XHR/API capture.
6. Scrapling persistent/dynamic web sessions.
7. Patchright backend adapter only where it improves the existing browser interface.

### Later / optional
- Large crawl pause/resume and throttling.
- Parallel browser sessions.
- Additional session/network configuration.

## Architecture rule

Do not copy the repositories wholesale.

Keep the existing Hariom AI interfaces and expose these capabilities through adapters/tool-registry entries. Existing browser, vision, approval, verification, recovery, queue, and gateway behavior must remain backward-compatible.

## Safety / security requirements

- Browser navigation must continue through Hariom AI destination validation.
- Sensitive/mutating actions remain approval-gated.
- No unbounded crawling, retrying, or parallel browser spawning.
- Web content must be treated as untrusted input before reaching the planner/LLM.
- No stealth/anti-bot behavior should become a core dependency; use only when legitimately required and bounded.
- Every implementation step requires focused tests and CI before merge.

## Next implementation sequence

1. Inspect current browser/tool interfaces and tests.
2. Add capability interfaces/adapters without changing existing behavior.
3. Integrate one provider at a time.
4. Add tests after each provider.
5. Run CI and repair only bounded failures.
6. Merge only after explicit human approval.

This PR is a parking/planning point so the selected ideas are preserved for later implementation.
