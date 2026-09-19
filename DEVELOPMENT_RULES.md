# Development Rules

## Definition of done
A feature is not done when code is written. It is done when:
1. implementation exists,
2. expected behavior is tested,
3. failures are handled,
4. documentation is updated when needed.

## Change discipline
- Read before edit.
- Make the smallest change that solves the problem.
- Avoid unrelated refactors.
- Preserve backwards compatibility where practical.
- Keep modules focused.
- Prefer explicit error handling over silent failure.

## Testing
At minimum, run/import the affected code. For meaningful changes, add or update automated tests. If a test cannot be run in the current environment, say so explicitly rather than claiming success.

## Git
Use descriptive commits. For larger work prefer a feature branch and PR. Do not force-push or rewrite history unless explicitly required.

## Security
Treat all model output as untrusted input. Validate paths, commands and external actions. Keep secrets out of logs and repository history.

## Agent behavior
If a request conflicts with the documented current phase, follow the current phase unless the user explicitly changes the roadmap. If the user changes a major product decision, update DECISIONS.md and PROJECT_HANDOFF.md.

## Reporting
Every substantial implementation report should include:
- Implemented
- Tested
- Not tested / remaining
- Next recommended step
