import tempfile
import unittest
from pathlib import Path

from app.context import WorkspaceContext
from app.workspace import Workspace


class WorkspaceContextTests(unittest.TestCase):
    def test_detects_project_type_and_important_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "requirements.txt").write_text("pytest\n", encoding="utf-8")
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            context = WorkspaceContext(Workspace(root)).snapshot()

            self.assertIn("Python", context["project_type"])
            self.assertEqual(context["important_files"]["README.md"], "# Demo\n")
            self.assertEqual(context["important_files"]["requirements.txt"], "pytest\n")

    def test_reports_non_git_workspace_without_failing(self):
        with tempfile.TemporaryDirectory() as tmp:
            context = WorkspaceContext(Workspace(Path(tmp))).snapshot()
            self.assertEqual(context["git"], {"repository": False})

    def test_reports_git_branch_and_dirty_state_when_git_is_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            import subprocess
            subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
            (root / "app.py").write_text("print('x')\n", encoding="utf-8")
            context = WorkspaceContext(Workspace(root)).snapshot()
            self.assertTrue(context["git"]["repository"])
            self.assertIn("app.py", "\n".join(context["git"]["changed_files"]))
            self.assertIn("dirty", context["git"])


if __name__ == "__main__":
    unittest.main()
