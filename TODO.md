# Hariom AI TODO

## V1 — Core stabilization (verified on Windows)
- [x] Inspect current modules for runtime/import issues
- [x] Confirm clean Windows startup
- [x] Validate .env loading
- [x] Validate configured provider paths used in testing
- [x] Validate provider fallback behavior
- [x] Validate workspace listing/reading/writing
- [x] Validate terminal runner
- [x] Validate risky-command protection
- [x] Improve core error handling
- [x] Add automated tests for core modules
- [x] Test a complete task end-to-end
- [x] Improve README setup/troubleshooting
- [x] Document tested Windows/Python versions

## V2 — Agent execution (implementation + verification complete)
- [x] Structured tool calling
- [x] Task planning/execution loop
- [x] Reliable file patch/edit operations
- [x] Test runner integration
- [x] Structured action results
- [x] Git read-only integration
- [x] Permission/approval UI
- [x] Automated V2 test suite
- [x] Real Windows end-to-end Agent verification

## NEXT — Developer integrations
- [ ] VS Code/project context
- [ ] GitHub issues/branches/commits/PRs/reviews
- [ ] Browser research/automation
- [ ] Website analysis

## LATER — Desktop agent
- [ ] Floating corner window
- [ ] Always-on-top mode
- [ ] Compact orb/minimized mode
- [ ] Drag/reposition
- [ ] Pause/Stop
- [ ] Active-window context
- [ ] Optional screen context
- [ ] Privacy toggles

## LATER — Advanced tools
- [ ] Background tasks
- [ ] Scheduled tasks
- [ ] Project memory/context
- [ ] Instagram research/content creation
- [ ] Video workflows
- [ ] PPT generation

## FINALIZATION
- [ ] Windows .exe
- [ ] Installer
- [ ] Crash logging/recovery
- [ ] Backup before update
- [ ] Self-update
- [ ] Rollback on failed update

## Verification record
- Automated suite: 12/12 tests passed
- Real Agent task: calculator project created successfully in `A:\project`
- Real Agent test execution: exit code 0
- Independent Windows test run: 5/5 calculator tests passed
- Verified workflow: planning → workspace inspection → file creation → test execution → final completion
- Provider fallback observed during the real test: Gemini → Mistral → Groq

## Rule
Do not mark a checkbox complete merely because code exists. Mark it complete only after the relevant behavior is tested.
