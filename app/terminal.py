import re
import subprocess

RISKY_PATTERNS = [
    r"\b(del|erase|rmdir|format|shutdown|diskpart)\b",
    r"\breg\s+delete\b",
    r"\bremove-item\b",
    r"\bgit\s+push\b.*--force(?:-with-lease)?\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-[a-z]*f[a-z]*\b",
]


def run_command(command, activity, approved=False, cwd=None):
    lowered = command.lower()
    if any(re.search(pattern, lowered) for pattern in RISKY_PATTERNS) and not approved:
        raise PermissionError("Risky command blocked. Explicit approval required.")
    activity.emit("TERMINAL -> "+command)
    p=subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120, cwd=str(cwd) if cwd else None)
    out=(p.stdout or "")+("\n"+p.stderr if p.stderr else "")
    activity.emit(f"TERMINAL -> exit code {p.returncode}")
    return p.returncode, out[-12000:]
