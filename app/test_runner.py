"""Controlled test runner for project verification."""
import shlex
import subprocess
from pathlib import Path


class TestRunnerError(Exception):
    """Base error for invalid test-runner input."""


class TestRunner:
    def __init__(self, root=None, timeout=120):
        self.root = Path(root or ".").resolve()
        self.timeout = timeout

    def _safe_path(self, value):
        if not isinstance(value, str) or not value.strip():
            raise TestRunnerError("Test path must be a non-empty string.")
        target = (self.root / value).resolve()
        if target != self.root and self.root not in target.parents:
            raise TestRunnerError("Test path is outside the workspace.")
        return target

    def _validate_command(self, command):
        if not isinstance(command, str) or not command.strip():
            raise TestRunnerError("Test command must be a non-empty string.")
        try:
            argv = shlex.split(command, posix=True)
        except ValueError as exc:
            raise TestRunnerError(f"Invalid test command syntax: {exc}") from exc
        if not argv:
            raise TestRunnerError("Test command must not be empty.")
        executable = Path(argv[0]).name.lower()
        if executable not in {"python", "python3", "py"}:
            raise TestRunnerError("Only Python test-runner commands are allowed.")
        if len(argv) < 4 or argv[1:4] != ["-m", "unittest", "discover"]:
            raise TestRunnerError("Only 'python -m unittest discover' commands are allowed.")
        i = 4
        while i < len(argv):
            token = argv[i]
            if token in {"-v", "--verbose"}:
                i += 1
                continue
            if token in {"-s", "--start-directory", "-t", "--top-level-directory", "-p", "--pattern"}:
                if i + 1 >= len(argv):
                    raise TestRunnerError(f"Missing value for {token}.")
                value = argv[i + 1]
                if token in {"-s", "--start-directory", "-t", "--top-level-directory"}:
                    self._safe_path(value)
                i += 2
                continue
            raise TestRunnerError(f"Unsupported unittest option: {token}")
        return argv

    def run_command(self, command):
        argv = self._validate_command(command)
        try:
            process = subprocess.run(
                argv,
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            return {"ok": False, "timed_out": True, "returncode": None, "output": str(exc)}
        output = (process.stdout or "") + ("\n" + process.stderr if process.stderr else "")
        return {
            "ok": process.returncode == 0,
            "timed_out": False,
            "returncode": process.returncode,
            "output": output[-12000:],
        }

    def run(self, target="tests"):
        self._safe_path(target)
        command = f"python -m unittest discover -s {shlex.quote(target)}"
        return self.run_command(command)
