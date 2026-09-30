import re
import subprocess

RISKY = (
    "del ", "erase ", "rmdir ", "format ", "shutdown", "reg delete",
    "diskpart", "remove-item", "git push --force", "git reset --hard",
    "git clean -fd", "git clean -xdf",
)
import shlex
import subprocess

SHELL_META = re.compile(r"[;&|<>`$()]")
MAX_OUTPUT = 12000
TIMEOUT_SECONDS = 120

def _parse_command(command):
    if not isinstance(command, str) or not command.strip():
        raise ValueError("Command must be a non-empty string.")
    if SHELL_META.search(command):
        raise PermissionError("Shell metacharacters are not allowed.")
    try:
        return shlex.split(command, posix=False)
    except ValueError as exc:
        raise ValueError(f"Invalid command syntax: {exc}") from exc

def run_command(command, activity, approved=False):
    argv = _parse_command(command)
    normalized = command.strip().lower()
    if not approved and any(x in normalized for x in RISKY):
        raise PermissionError("Risky command blocked. Explicit approval required.")
    activity.emit("TERMINAL -> " + command)
    try:
        p = subprocess.run(argv, shell=False, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        activity.emit("TERMINAL -> timeout")
        partial = (exc.stdout or "") + ("\n" + exc.stderr if exc.stderr else "")
        return 124, partial[-MAX_OUTPUT:]
    out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
    activity.emit(f"TERMINAL -> exit code {p.returncode}")
    return p.returncode, out[-MAX_OUTPUT:]
