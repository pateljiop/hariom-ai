"""Git operations for controlled agent workflows."""
import re
import subprocess
from pathlib import Path

SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r'''(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*['"][^'"]{8,}['"]'''),
    re.compile(r"\b(?:sk|rk)-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)

def scan_secrets(text):
    findings = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text or ""):
            findings.append(pattern.pattern)
    return findings


class GitError(Exception):
    pass


class GitManager:
    PROTECTED_BRANCHES = frozenset({"main", "master", "production", "prod"})

    def __init__(self, root=None):
        self.root = Path(root or ".").resolve()

    @classmethod
    def _validate_branch_name(cls, name):
        if not isinstance(name, str) or not name.strip() or name.startswith("-") or any(
            x in name for x in ["..", "~", "^", " ", "\\"]
        ):
            raise GitError("Invalid branch name.")
        if name in cls.PROTECTED_BRANCHES:
            raise GitError("Protected branch cannot be created or directly merged.")
        return name

    def _run(self, *args):
        p = subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True, timeout=30)
        output = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
        if p.returncode:
            raise GitError(output.strip() or f"git exited with {p.returncode}")
        return output.strip()

    def status(self):
        return self._run("status", "--short")

    def current_branch(self):
        self._ensure_repo()
        return self._run("branch", "--show-current")

    def diff(self):
        return self._run("diff", "--")

    def _ensure_repo(self):
        if not (self.root / ".git").exists():
            raise GitError("Workspace is not a Git repository.")

    def create_branch(self, name):
        self._ensure_repo()
        return self._run("switch", "-c", self._validate_branch_name(name))

    def scan_diff_for_secrets(self, diff=None):
        diff = self.diff() if diff is None else str(diff)
        # Inspect added lines only; removed historical secrets are not being committed.
        added = "\n".join(line for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
        return scan_secrets(added)

    def merge_branch(self, name, approved=False):
        self._ensure_repo()
        if not approved:
            raise PermissionError("Git merge requires explicit approval.")
        name = self._validate_branch_name(name)
        current = self.current_branch()
        if current in self.PROTECTED_BRANCHES:
            raise GitError("Protected branch cannot be a merge target.")
        if current == name:
            raise GitError("Cannot merge the current branch into itself.")
        findings = self.scan_diff_for_secrets()
        if findings:
            raise PermissionError("Potential secret detected in working diff; merge blocked.")
        return self._run("merge", "--no-ff", name)

    def commit(self, message, approved=False):
        if not approved:
            raise PermissionError("Git commit requires explicit approval.")
        if not isinstance(message, str) or not message.strip():
            raise GitError("Commit message is required.")
        self._ensure_repo()
        current = self._run("branch", "--show-current")
        if current in self.PROTECTED_BRANCHES:
            raise GitError("Protected branch cannot receive direct commits.")
        findings = self.scan_diff_for_secrets()
        if findings:
            raise PermissionError("Potential secret detected in Git diff; explicit security review required.")
        return self._run("add", "-A") + ("\n" + self._run("commit", "-m", message))
