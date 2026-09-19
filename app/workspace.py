from pathlib import Path
import os
import subprocess

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

    def patch_file(self, path, old_text, new_text, expected_replacements=1):
        if not isinstance(old_text, str) or not old_text:
            raise ValueError("patch_file requires non-empty old_text.")
        if not isinstance(new_text, str):
            raise ValueError("patch_file requires string new_text.")
        if not isinstance(expected_replacements, int) or expected_replacements < 1:
            raise ValueError("expected_replacements must be a positive integer.")

        target = self._safe_path(path)
        if not target.is_file():
            raise FileNotFoundError(f"File does not exist: {path}")

        content = target.read_text(encoding="utf-8")
        count = content.count(old_text)
        if count != expected_replacements:
            raise ValueError(
                f"Patch expected {expected_replacements} replacement(s), found {count}."
            )

        target.write_text(content.replace(old_text, new_text), encoding="utf-8")
        return target, count

    def project_context(self):
        """Return bounded, read-only context about the selected project/workspace."""
        files = self.list_files()
        relative_files = [
            str(path.relative_to(self.root))
            for path in files[:300]
        ]

        manifest_names = {
            "requirements.txt",
            "pyproject.toml",
            "package.json",
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
            "Cargo.toml",
            "go.mod",
            "pom.xml",
            "build.gradle",
            "build.gradle.kts",
            "composer.json",
        }
        manifest_lookup = {item.lower() for item in manifest_names}
        manifests = [
            name for name in relative_files
            if Path(name).name.lower() in manifest_lookup
        ]

        extensions = {}
        for path in files[:500]:
            suffix = path.suffix.lower()
            if suffix:
                extensions[suffix] = extensions.get(suffix, 0) + 1

        git_branch = ""
        git_status = ""
        try:
            branch = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,
            )
            if branch.returncode == 0:
                git_branch = branch.stdout.strip()

            status = subprocess.run(
                ["git", "status", "--short"],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,
            )
            if status.returncode == 0:
                git_status = status.stdout.strip()[:2000]
        except (OSError, subprocess.SubprocessError):
            pass

        vscode_running = self._is_vscode_running()

        return {
            "workspace": str(self.root),
            "file_count": len(files),
            "files": relative_files,
            "manifests": manifests,
            "extensions": dict(sorted(extensions.items())),
            "git_branch": git_branch,
            "git_status": git_status,
            "windows": os.name == "nt",
            "vscode_running": vscode_running,
        }

    @staticmethod
    def _is_vscode_running():
        if os.name != "nt":
            return False
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Code.exe", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,
            )
            return result.returncode == 0 and "Code.exe" in result.stdout
        except (OSError, subprocess.SubprocessError):
            return False

    def _safe_path(self, path):
        target = (self.root / path).resolve()

        if target != self.root and self.root not in target.parents:
            raise ValueError("Path is outside the workspace.")

        return target
