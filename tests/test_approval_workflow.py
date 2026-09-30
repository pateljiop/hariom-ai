from unittest.mock import Mock
import tempfile
import unittest

from app.approval_workflow import (
    ApprovalNotFoundError,
    ApprovalWorkflow,
    ApprovalWorkflowError,
)
from app.activity import ActivityBus
from app.git_manager import GitManager
from app.task_executor import TaskAction, TaskExecutor
from app.tool_registry import ToolRegistry
from app.workspace import Workspace


class ApprovalWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Workspace(self.temp.name)
        self.registry = ToolRegistry(self.workspace, ActivityBus())
        self.executor = TaskExecutor(self.registry)
        self.git = Mock()
        self.workflow = ApprovalWorkflow(self.executor, self.git)

    def tearDown(self):
        self.temp.cleanup()

    def test_prepare_runs_actions_tests_and_captures_diff_before_approval(self):
        self.registry.test_runner.run = Mock(return_value={"ok": True, "returncode": 0})
        self.git.diff.return_value = "diff -- file"

        result = self.workflow.prepare([
            TaskAction("workspace.write", {"path": "change.txt", "content": "new"})
        ])

        self.assertTrue(result["ok"])
        self.assertEqual(result["stage"], "approval")
        self.assertEqual(result["diff"], "diff -- file")
        self.assertTrue(result["request_id"])
        self.git.commit.assert_not_called()

    def test_failed_tests_block_approval_request(self):
        self.registry.test_runner.run = Mock(return_value={
            "ok": False, "returncode": 1, "output": "failure"
        })

        result = self.workflow.prepare([
            TaskAction("workspace.write", {"path": "change.txt", "content": "new"})
        ])

        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "verification")
        self.git.commit.assert_not_called()

    def test_approval_commits_only_after_diff_remains_unchanged(self):
        self.registry.test_runner.run = Mock(return_value={"ok": True, "returncode": 0})
        self.git.diff.return_value = "same diff"
        self.git.commit.return_value = "committed"

        prepared = self.workflow.prepare([
            TaskAction("workspace.write", {"path": "change.txt", "content": "new"})
        ])
        result = self.workflow.approve(prepared["request_id"], "apply reviewed change")

        self.assertTrue(result["ok"])
        self.git.commit.assert_called_once_with("apply reviewed change", approved=True)

    def test_changed_diff_invalidates_approval(self):
        self.registry.test_runner.run = Mock(return_value={"ok": True, "returncode": 0})
        self.git.diff.side_effect = ["original diff", "changed diff"]

        prepared = self.workflow.prepare([
            TaskAction("workspace.write", {"path": "change.txt", "content": "new"})
        ])

        with self.assertRaises(ApprovalWorkflowError):
            self.workflow.approve(prepared["request_id"], "commit")

        self.git.commit.assert_not_called()

    def test_unknown_request_is_rejected(self):
        with self.assertRaises(ApprovalNotFoundError):
            self.workflow.approve("missing", "commit")


if __name__ == "__main__":
    unittest.main()
