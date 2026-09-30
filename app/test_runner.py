"""Controlled test runner for project verification."""
import subprocess
from pathlib import Path


class TestRunnerError(Exception):
    """Base error for invalid test-runner input."""


class TestRunner:
    def __init__(self, root=None, timeout=120):
        self.root = Path(root or ".").resolve()
        self.timeout = timeout

    def run(self, target="tests"):
        if not isinstance(target, str) or not target.strip():
            raise TestRunnerError("Test target must be a non-empty string.")
        command = ["python", "-m", "unittest", "discover", "-s", target]
        try:
            process = subprocess.run(
                command,
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            return {"ok": False, "timed_out": True, "returncode": None, "output": str(exc)}
        output = (process.stdout or "") + ("\\n" + process.stderr if process.stderr else "")
        return {
            "ok": process.returncode == 0,
            "timed_out": False,
            "returncode": process.returncode,
            "output": output[-12000:],
        }
