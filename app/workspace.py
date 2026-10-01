from pathlib import Path

from . import config


class Workspace:
    MAX_FILE_SIZE = 2 * 1024 * 1024
    MAX_WRITE_SIZE = 2 * 1024 * 1024

    def __init__(self, root=None):
        self.root = Path(root or config.WORKSPACE).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _check_regular_file(self, target):
        if target.exists() and target.is_symlink():
            raise ValueError("Symlink targets are not allowed.")
        if target.exists() and not target.is_file():
            raise ValueError("Workspace target must be a regular file.")
        if target.exists() and target.stat().st_size > self.MAX_FILE_SIZE:
            raise ValueError("Workspace file exceeds the maximum allowed size.")

    def list_files(self):
        if not self.root.exists():
            return []

        return [
            path
            for path in self.root.rglob("*")
            if path.is_file()
        ]

    def exists(self, path):
        return self._safe_path(path).is_file()

    def read_file(self, path):
        target = self._safe_path(path)
        self._check_regular_file(target)
        return target.read_text(encoding="utf-8")

    def write_file(self, path, content):
        if not isinstance(content, str):
            raise TypeError("Workspace content must be text.")
        if len(content.encode("utf-8")) > self.MAX_WRITE_SIZE:
            raise ValueError("Workspace write exceeds the maximum allowed size.")
        target = self._safe_path(path)
        self._check_regular_file(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def _safe_path(self, path):
        if not isinstance(path, (str, Path)):
            raise TypeError("Workspace path must be text.")
        candidate = self.root / path
        if candidate.is_symlink():
            raise ValueError("Symlink paths are not allowed.")
        target = candidate.resolve()

        if target != self.root and self.root not in target.parents:
            raise ValueError("Path is outside the workspace.")

        return target
