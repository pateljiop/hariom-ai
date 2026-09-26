import os
import re
import shutil
import subprocess
from pathlib import Path


_SUFFIX = " - Visual Studio Code"


def _window_titles():
    if os.name != "nt":
        return []
    commands = [
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-Process Code -ErrorAction SilentlyContinue | "
            "Where-Object {$_.MainWindowTitle} | "
            "Select-Object -ExpandProperty MainWindowTitle",
        ],
        [
            "tasklist",
            "/FI",
            "IMAGENAME eq Code.exe",
            "/FO",
            "CSV",
            "/NH",
        ],
    ]
    for command in commands:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,
            )
            if result.returncode != 0:
                continue
            if command[0].lower() == "powershell":
                titles = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            else:
                titles = []
            if titles:
                return titles
        except (OSError, subprocess.SubprocessError):
            continue
    return []


def context(root):
    root = Path(root).resolve()
    titles = _window_titles()
    result = {
        "windows": os.name == "nt",
        "running": bool(titles),
        "window_count": len(titles),
        "window_titles": titles[:10],
        "active_file": "",
        "active_project": "",
        "active_file_exists": False,
        "workspace_file": "",
    }

    workspace_files = sorted(root.glob("*.code-workspace"))
    if workspace_files:
        result["workspace_file"] = str(workspace_files[0].relative_to(root))

    for title in titles:
        parsed = _parse_title(title)
        if not parsed:
            continue
        active_file, project = parsed
        result["active_file"] = active_file
        result["active_project"] = project
        candidate = root / active_file if active_file else None
        if candidate and candidate.is_file():
            result["active_file_exists"] = True
        elif active_file:
            basename = Path(active_file).name
            matches = [p for p in root.rglob(basename) if p.is_file()]
            if len(matches) == 1:
                result["active_file"] = str(matches[0].relative_to(root))
                result["active_file_exists"] = True
        break

    return result


def _parse_title(title):
    title = title.strip()
    if title.endswith(_SUFFIX):
        title = title[: -len(_SUFFIX)].strip()
    if not title:
        return None

    parts = [part.strip() for part in re.split(r"\s+-\s+", title) if part.strip()]
    if len(parts) < 2:
        return None

    active = parts[0]
    project = parts[-1]
    if active in {"Welcome", "Extensions", "Output", "Search"}:
        active = ""
    return active, project


def executable():
    return shutil.which("code.cmd") or shutil.which("code")


def open_path(root, relative_path=""):
    code = executable()
    if not code:
        raise FileNotFoundError("VS Code command 'code' was not found in PATH.")

    root = Path(root).resolve()
    target = root if not relative_path else (root / relative_path).resolve()
    if target != root and root not in target.parents:
        raise ValueError("VS Code path is outside the workspace.")

    subprocess.Popen(
        [code, "-r", str(target)],
        cwd=str(root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
    )
    return str(target)
