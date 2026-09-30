from pathlib import Path
import subprocess

from .workspace import Workspace


IGNORED_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build"}


class WorkspaceContext:
    """Build a compact, deterministic snapshot of the active project."""

    def __init__(self, workspace: Workspace):
        self.workspace = workspace

    def snapshot(self, max_files=120):
        files = []
        for path in self.workspace.root.rglob("*"):
            if not path.is_file() or any(part in IGNORED_DIRS for part in path.parts):
                continue
            rel = path.relative_to(self.workspace.root)
            files.append(str(rel))
            if len(files) >= max_files:
                break

        important = {}
        for name in ("README.md", "pyproject.toml", "requirements.txt", "package.json", ".gitignore"):
            path = self.workspace.root / name
            if path.is_file():
                try:
                    important[name] = path.read_text(encoding="utf-8")[:5000]
                except (OSError, UnicodeError):
                    pass

        return {
            "root": str(self.workspace.root),
            "project_type": self._project_type(),
            "git": self._git_context(),
            "file_count": len(files),
            "files": files,
            "important_files": important,
        }

    def _project_type(self):
        root = self.workspace.root
        markers = {
            "Python": ("pyproject.toml", "requirements.txt", "setup.py"),
            "Node": ("package.json",),
            "Rust": ("Cargo.toml",),
            "Go": ("go.mod",),
            "Java": ("pom.xml", "build.gradle"),
        }
        detected = [
            name for name, files in markers.items()
            if any((root / filename).is_file() for filename in files)
        ]
        return detected or ["Unknown"]

    def _git_context(self):
        root = self.workspace.root
        if not (root / ".git").exists():
            return {"repository": False}

        def git(*args):
            try:
                result = subprocess.run(
                    ["git", *args],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    timeout=3,
                    check=False,
                )
                if result.returncode != 0:
                    return ""
                return result.stdout.strip()
            except (OSError, subprocess.SubprocessError):
                return ""

        branch = git("branch", "--show-current")
        status = git("status", "--short")
        return {
            "repository": True,
            "branch": branch or "detached",
            "dirty": bool(status),
            "changed_files": status.splitlines()[:40] if status else [],
        }
