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

    def exists(self, path):
        return self._safe_path(path).is_file()

    def read_file(self, path):
        target = self._safe_path(path)
        return target.read_text(encoding="utf-8")

    def write_file(self, path, content):
        target = self._safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def patch_file(self, path, old_text, new_text, expected_replacements=1):
        """Replace an exact text fragment, refusing ambiguous or stale patches."""
        if not isinstance(old_text, str) or not old_text:
            raise ValueError("old_text must be a non-empty string.")
        if not isinstance(new_text, str):
            raise TypeError("new_text must be a string.")
        if not isinstance(expected_replacements, int) or isinstance(expected_replacements, bool) or expected_replacements < 1:
            raise ValueError("expected_replacements must be a positive integer.")

        target = self._safe_path(path)
        if not target.is_file():
            raise FileNotFoundError("Cannot patch a file that does not exist: " + str(path))

        original = target.read_text(encoding="utf-8")
        matches = original.count(old_text)
        if matches != expected_replacements:
            raise ValueError(
                "Patch expected %d exact match(es), found %d."
                % (expected_replacements, matches)
            )

        updated = original.replace(old_text, new_text)
        target.write_text(updated, encoding="utf-8")
        return target

    def _safe_path(self, path):
        target = (self.root / path).resolve()

        if target != self.root and self.root not in target.parents:
            raise ValueError("Path is outside the workspace.")

        return target
