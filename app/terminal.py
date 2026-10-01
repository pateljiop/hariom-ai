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
SECRET_ENV_RE = re.compile(r"(?:^|_)(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|PASSWD|PRIVATE[_-]?KEY)(?:$|_)", re.I)
SECRET_ASSIGNMENT_RE = re.compile(r"""(\b(?:api[_-]?key|token|secret|password|passwd|private[_-]?key)\b\s*[=:]\s*)(["']?)[^\s,;&|]+""", re.I)

def _redact(value):
    return SECRET_ASSIGNMENT_RE.sub(r"\1\2[REDACTED]", str(value))

def _safe_environment():
    return {k: v for k, v in os.environ.items() if not SECRET_ENV_RE.search(k)}

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

def _terminate_process_tree(process):
    """Best-effort bounded cleanup of a timed-out process and its descendants."""
    pid = getattr(process, "pid", None)
    if not pid:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], shell=False, capture_output=True, text=True, timeout=5)
        else:
            import signal
            os.killpg(pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        try:
            process.kill()
        except OSError:
            pass


def run_command(command, activity, approved=False):
    argv = _parse_command(command, approved=approved)
    normalized = command.strip().lower()
    if not approved and any(x in normalized for x in RISKY):
        raise PermissionError("Risky command blocked. Explicit approval required.")
    activity.emit("TERMINAL -> " + _redact(command))
    env = _safe_environment()
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        if os.name == "nt":
            process = subprocess.Popen(argv, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, creationflags=creationflags)
        else:
            process = subprocess.Popen(argv, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as exc:
            _terminate_process_tree(process)
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate(timeout=5)
            activity.emit("TERMINAL -> timeout")
            partial = (stdout or "") + ("\n" + stderr if stderr else "")
            if not partial:
                partial = (exc.stdout or "") + ("\n" + exc.stderr if exc.stderr else "")
            return 124, _redact(partial[-MAX_OUTPUT:])
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"Command execution failed: {exc}") from exc
    out = (stdout or "") + ("\n" + stderr if stderr else "")
    activity.emit(f"TERMINAL -> exit code {process.returncode}")
    return process.returncode, _redact(out[-MAX_OUTPUT:])
