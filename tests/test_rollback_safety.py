import subprocess
import tempfile
import unittest
from pathlib import Path

from app.git_manager import GitError, GitManager


def git(root, *args):
    return subprocess.run(
        ["git", *args], cwd=root, check=True,
        capture_output=True, text=True
    ).stdout.strip()


class RollbackSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        git(self.root, "init", "-b", "feature")
        git(self.root, "config", "user.email", "test@example.com")
        git(self.root, "config", "user.name", "Test User")
        (self.root / "state.txt").write_text("before\n", encoding="utf-8")
        git(self.root, "add", "state.txt")
        git(self.root, "commit", "-m", "initial")
        self.before = git(self.root, "rev-parse", "HEAD")
        (self.root / "state.txt").write_text("after\n", encoding="utf-8")
        git(self.root, "add", "state.txt")
        git(self.root, "commit", "-m", "change")
        self.after = git(self.root, "rev-parse", "HEAD")
        self.manager = GitManager(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_requires_explicit_approval(self):
        with self.assertRaises(PermissionError):
            self.manager.rollback_to_commit(self.before, self.after)

    def test_rejects_head_drift(self):
        with self.assertRaises(GitError):
            self.manager.rollback_to_commit(self.before, "0" * 40, approved=True)

    def test_rejects_dirty_worktree(self):
        (self.root / "unrelated.txt").write_text("local\n", encoding="utf-8")
        with self.assertRaises(GitError):
            self.manager.rollback_to_commit(self.before, self.after, approved=True)

    def test_reverts_exact_verified_commit(self):
        result = self.manager.rollback_to_commit(
            self.before, self.after, approved=True
        )
        self.assertEqual(result["target_sha"], self.before)
        self.assertEqual(result["reverted_sha"], self.after)
        self.assertNotEqual(result["rollback_sha"], self.after)
        self.assertEqual(self.manager.head_sha(), result["rollback_sha"])
        self.assertEqual(
            (self.root / "state.txt").read_text(encoding="utf-8"), "before\n"
        )
        self.assertEqual(self.manager.status(), "")

    def test_protected_branch_is_blocked(self):
        git(self.root, "switch", "-c", "main")
        with self.assertRaises(GitError):
            self.manager.rollback_to_commit(
                self.before, self.after, approved=True
            )


if __name__ == "__main__":
    unittest.main()
