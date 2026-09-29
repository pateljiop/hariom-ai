from pathlib import Path

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
            "file_count": len(files),
            "files": files,
            "important_files": important,
        }
