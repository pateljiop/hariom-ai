import re
import subprocess

RISKY = (
    "del ", "erase ", "rmdir ", "format ", "shutdown", "reg delete",
    "diskpart", "remove-item", "git push --force", "git reset --hard",
    "git clean -fd", "git clean -xdf",
)
SHELL_META = re.compile(r"[;&|<>`$()]")

def run_command(command, activity, approved=False):
    if not isinstance(command, str) or not command.strip():
        raise ValueError("Command must be a non-empty string.")
    normalized = command.strip().lower()
    if not approved and (any(x in normalized for x in RISKY) or SHELL_META.search(command)):
        raise PermissionError("Risky shell command blocked. Explicit approval required.")
    activity.emit("TERMINAL -> " + command)
    p = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120)
    out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
    activity.emit(f"TERMINAL -> exit code {p.returncode}")
    return p.returncode, out[-12000:]
