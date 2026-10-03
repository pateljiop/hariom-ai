# Development Log

This file records verified repository changes and the next concrete actions. Entries distinguish remote edits from tests actually executed.

## 2026-10-04 — Workspace patch compatibility

- **Branch:** `fix/workspace-patch-compat`
- **Change:** Added `Workspace.patch_file(path, old_text, new_text, expected_replacements=1)`.
- **Safety behavior:** Uses the existing workspace path resolver; refuses empty search text, invalid replacement counts, missing files, and any exact-match count different from the expected count. It does not permit paths outside the workspace.
- **Commit:** `250a36801b130b4deecceecf530af99fc084d4a5`
- **Verification:** Re-fetched both `app/workspace.py` and this log from the branch; the new method is present in the committed file. The unit tests have **not** been executed in this environment, so this change is not yet marked CI-green.

## Known compatibility issue still open

- The current `app/agent.py` defines `PersonalAgent`, while the existing `tests/test_agent.py` imports the older `Agent` API and exercises methods such as `_execute` and `run` with a legacy router interface.
- Do not paper over this by aliasing `Agent = PersonalAgent`: that would satisfy the import but would not preserve the tested interface.
- Next: inspect the history/remaining execution modules and choose a backward-compatible adapter or deliberately migrate the legacy tests to the current agent contract without losing coverage. Run the full suite and CI before calling the branch complete.
- No merge has been performed.
