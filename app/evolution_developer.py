import subprocess
from pathlib import Path


class EvolutionDeveloper:
    """Isolated self-improvement workflow. Never merges or deploys automatically."""

    def __init__(self, repo_root, activity=None):
        self.root = Path(repo_root).resolve()
        self.activity = activity

    def _run(self, *args):
        result = subprocess.run(
            ["git", *args], cwd=self.root, text=True,
            capture_output=True, timeout=120
        )
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout).strip()[-4000:])
        return result.stdout.strip()

    def status(self):
        return self._run("status", "--short")

    def create_isolated_branch(self, branch_name):
        if not branch_name or "/" not in branch_name:
            raise ValueError("branch_name must identify an isolated evolution branch")
        if self.status():
            raise RuntimeError("Working tree must be clean before an evolution branch is created.")
        self._run("switch", "-c", branch_name)
        self._emit("EVOLUTION -> isolated branch created: " + branch_name)
        return branch_name

    def apply_patch(self, patch):
        patch = str(patch)
        if not patch.strip():
            raise ValueError("patch is empty")
        if len(patch) > 100000:
            raise ValueError("patch is too large")
        result = subprocess.run(
            ["git", "apply", "--check", "--whitespace=error"],
            cwd=self.root, input=patch, text=True,
            capture_output=True, timeout=60
        )
        if result.returncode:
            raise RuntimeError("patch validation failed: " + (result.stderr or result.stdout).strip()[-4000:])
        result = subprocess.run(
            ["git", "apply", "--whitespace=error"],
            cwd=self.root, input=patch, text=True,
            capture_output=True, timeout=60
        )
        if result.returncode:
            raise RuntimeError("patch application failed: " + (result.stderr or result.stdout).strip()[-4000:])
        self._emit("EVOLUTION -> patch applied")
        return self.status()

    def run_tests(self):
        result = subprocess.run(
            ["python", "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=self.root, text=True, capture_output=True, timeout=300
        )
        output = (result.stdout + "\n" + result.stderr).strip()
        self._emit("EVOLUTION -> tests " + ("passed" if result.returncode == 0 else "failed"))
        return {"passed": result.returncode == 0, "exit_code": result.returncode, "output": output[-12000:]}

    def diff(self):
        return self._run("diff", "--check") + "\n" + self._run("diff", "--stat")

    def commit_candidate(self, message):
        if self.status():
            self._run("add", "-A")
            self._run("commit", "-m", str(message))
            sha = self._run("rev-parse", "HEAD")
            self._emit("EVOLUTION -> candidate commit " + sha)
            return sha
        raise RuntimeError("No changes to commit.")

    def _emit(self, message):
        if self.activity:
            self.activity.emit(message)
