import unittest
from unittest.mock import Mock

from app.approval_workflow import ApprovalWorkflow, ApprovalWorkflowError
from app.git_manager import GitManager
from app.task_executor import TaskAction


class FakeGit(GitManager):
    def __init__(self):
        super().__init__(".")
        self.reviewed_diff = "staged + unstaged reviewed diff"
        self.branch = "feature/approval"
        self.commit_result = "committed"

    def review_diff(self):
        return self.reviewed_diff

    def current_branch(self):
        return self.branch

    def commit(self, message, approved=False):
        self.commit_message = message
        self.commit_approved = approved
        return self.commit_result


class ApprovalIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.executor = Mock()
        self.executor.execute.return_value = {"ok": True}
        self.executor.verify_expectations.return_value = {"ok": True}
        self.executor.registry.test_runner.run.return_value = {"ok": True, "returncode": 0}
        self.git = FakeGit()
        self.workflow = ApprovalWorkflow(executor=self.executor, git=self.git)

    def test_pending_approval_captures_complete_review_diff(self):
        result = self.workflow.prepare([TaskAction("workspace.write", {"path": "x", "content": "y"})])
        self.assertTrue(result["ok"])
        self.assertEqual(result["diff"], "staged + unstaged reviewed diff")
        request = self.workflow._load(result["request_id"])
        self.assertEqual(request.branch, "feature/approval")

    def test_branch_change_invalidates_approval(self):
        result = self.workflow.prepare([TaskAction("workspace.write", {"path": "x", "content": "y"})])
        self.git.branch = "main"
        with self.assertRaises(ApprovalWorkflowError):
            self.workflow.approve(result["request_id"], "commit")
        self.assertFalse(hasattr(self.git, "commit_message"))

    def test_staged_or_unstaged_change_invalidates_approval(self):
        result = self.workflow.prepare([TaskAction("workspace.write", {"path": "x", "content": "y"})])
        self.git.reviewed_diff = "different diff"
        with self.assertRaises(ApprovalWorkflowError):
            self.workflow.approve(result["request_id"], "commit")
        self.assertFalse(hasattr(self.git, "commit_message"))


if __name__ == "__main__":
    unittest.main()
