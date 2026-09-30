"""Git operations for controlled agent workflows."""
import subprocess
from pathlib import Path


class GitError(Exception):
    pass


class GitManager:
    def __init__(self, root=None):
        self.root = Path(root or ".").resolve()

    def _run(self, *args):
        p = subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True, timeout=30)
        output = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
        if p.returncode:
            raise GitError(output.strip() or f"git exited with {p.returncode}")
        return output.strip()

    def status(self):
        return self._run("status", "--short")

    def diff(self):
        return self._run("diff", "--")

    def create_branch(self, name):
        if not isinstance(name, str) or not name.strip() or name.startswith("-") or any(x in name for x in ["..", "~", "^"]):
            raise GitError("Invalid branch name.")
        return self._run("switch", "-c", name)

    def commit(self, message, approved=False):
        if not approved:
            raise PermissionError("Git commit requires explicit approval.")
        if not isinstance(message, str) or not message.strip():
            raise GitError("Commit message is required.")
        return self._run("add", "-A") + ("\n" + self._run("commit", "-m", message))
