import re
import shlex
import subprocess
import os

RISKY = (
    "del ", "erase ", "rmdir ", "format ", "shutdown", "reg delete",
    "diskpart", "remove-item", "git push --force", "git reset --hard",
    "git clean -fd", "git clean -xdf",
)

SHELL_META = re.compile(r"[;&|<>`$()]")
MAX_OUTPUT = 12000
TIMEOUT_SECONDS = 120
MAX_COMMAND_LENGTH = 4000

def _parse_command(command, approved=False):
    if not isinstance(command, str) or not command.strip():
        raise ValueError("Command must be a non-empty string.")
    if len(command) > MAX_COMMAND_LENGTH:
        raise ValueError("Command exceeds the maximum allowed length.")
    if SHELL_META.search(command) and not approved:
        raise PermissionError("Shell metacharacters are not allowed.")
    try:
        return shlex.split(command, posix=approved)
    except ValueError as exc:
        raise ValueError(f"Invalid command syntax: {exc}") from exc

def run_command(command, activity, approved=False):
    argv = _parse_command(command, approved=approved)
    normalized = command.strip().lower()
    if not approved and any(x in normalized for x in RISKY):
        raise PermissionError("Risky command blocked. Explicit approval required.")
    activity.emit("TERMINAL -> " + command)
    try:
        env = {k: v for k, v in os.environ.items() if k not in {"OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "GITHUB_TOKEN"}}
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        p = subprocess.run(argv, shell=False, capture_output=True, text=True, timeout=TIMEOUT_SECONDS, env=env, creationflags=creationflags)
    except subprocess.TimeoutExpired as exc:
        activity.emit("TERMINAL -> timeout")
        partial = (exc.stdout or "") + ("\n" + exc.stderr if exc.stderr else "")
        return 124, partial[-MAX_OUTPUT:]
    out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
    activity.emit(f"TERMINAL -> exit code {p.returncode}")
    return p.returncode, out[-MAX_OUTPUT:]
