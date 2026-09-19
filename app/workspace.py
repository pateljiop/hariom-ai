from pathlib import Path

from . import config


class Workspace:
    def __init__(self, root=None):
        self.root = Path(root or config.WORKSPACE).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def list_files(self):
        if not self.root.exists():
            return []

        return [
            path
            for path in self.root.rglob("*")
            if path.is_file()
        ]

    def read_file(self, path):
        target = self._safe_path(path)
        return target.read_text(encoding="utf-8")

    def write_file(self, path, content):
        target = self._safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def _safe_path(self, path):
        target = (self.root / path).resolve()

        if target != self.root and self.root not in target.parents:
            raise ValueError("Path is outside the workspace.")

        return target
