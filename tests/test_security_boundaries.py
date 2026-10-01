import tempfile
import unittest
from pathlib import Path

from app.workspace import Workspace
from app.permissions import PermissionManager, Permission


class SecurityBoundaryTests(unittest.TestCase):
    def test_workspace_rejects_oversized_write(self):
        with tempfile.TemporaryDirectory() as root:
            ws = Workspace(root)
            with self.assertRaises(ValueError):
                ws.write_file("large.txt", "x" * (Workspace.MAX_WRITE_SIZE + 1))

    def test_workspace_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as root:
            ws = Workspace(root)
            target = Path(root) / "real.txt"
            target.write_text("safe", encoding="utf-8")
            link = Path(root) / "link.txt"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            with self.assertRaises(ValueError):
                ws.read_file("link.txt")

    def test_approval_binding_rejects_wrong_task_or_tool(self):
        manager = PermissionManager()
        approval = {"task_id": "task-1", "tool": "terminal.run"}
        self.assertFalse(manager.decide(Permission.TERMINAL_EXECUTE, approved=True,
                                         task_id="task-2", tool="terminal.run", approval=approval).allowed)
        self.assertFalse(manager.decide(Permission.TERMINAL_EXECUTE, approved=True,
                                         task_id="task-1", tool="browser.click", approval=approval).allowed)


if __name__ == "__main__":
    unittest.main()
