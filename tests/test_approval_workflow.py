from unittest.mock import Mock
import tempfile
import unittest

from app.approval_workflow import (
    ApprovalNotFoundError,
    ApprovalDeniedError,
    ApprovalWorkflow,
    ApprovalWorkflowError,
)
from app.activity import ActivityBus
from app.git_manager import GitManager
from app.task_executor import TaskAction, TaskExecutor
from app.task_store import TaskStore
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

    def test_plan_expectations_are_verified_before_approval(self):
        self.registry.test_runner.run = Mock(return_value={"ok": True, "returncode": 0})
        self.registry.test_runner.run_command = Mock(return_value={"ok": True, "returncode": 0, "output": ""})
        self.git.diff.return_value = "diff"
        result = self.workflow.prepare(
            [TaskAction("workspace.write", {"path": "expected.txt", "content": "ok"})],
            expected_files=("expected.txt",),
            test_commands=("python -m unittest discover -s tests",),
        )
        self.assertTrue(result["ok"])
        self.registry.test_runner.run_command.assert_called_once_with(
            "python -m unittest discover -s tests"
        )

    def test_missing_plan_expectation_blocks_approval(self):
        self.registry.test_runner.run = Mock(return_value={"ok": True, "returncode": 0})
        self.git.diff.return_value = "diff"
        result = self.workflow.prepare(
            [TaskAction("workspace.write", {"path": "other.txt", "content": "ok"})],
            expected_files=("missing.txt",),
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "verification")
        self.assertEqual(result["expectation_result"]["ok"], False)
        self.git.commit.assert_not_called()

    def test_approval_persists_and_can_be_reloaded(self):
        self.registry.test_runner.run = Mock(return_value={"ok": True, "returncode": 0})
        self.git.diff.return_value = "same diff"
        self.git.commit.return_value = "committed"
        with tempfile.TemporaryDirectory() as root:
            store = TaskStore(f"{root}/tasks.sqlite3")
            from app.task_service import TaskService
            TaskService(store).create_task("persist approval", task_id="task-1")
            workflow = ApprovalWorkflow(self.executor, self.git, store=store)
            prepared = workflow.prepare([TaskAction("workspace.write", {"path": "x", "content": "y"})], task_id="task-1")
            reloaded = ApprovalWorkflow(self.executor, self.git, store=store)
            result = reloaded.approve(prepared["request_id"], "persisted commit")
            self.assertTrue(result["ok"])

    def test_approval_reload_preserves_step_metadata(self):
        self.registry.test_runner.run = Mock(return_value={"ok": True, "returncode": 0})
        self.git.diff.return_value = "same diff"
        with tempfile.TemporaryDirectory() as root:
            store = TaskStore(f"{root}/tasks.sqlite3")
            from app.task_service import TaskService
            TaskService(store).create_task("persist metadata", task_id="task-metadata")
            action = TaskAction("workspace.write", {"path": "x", "content": "y"}, False, ("step-1",), "step-2")
            workflow = ApprovalWorkflow(self.executor, self.git, store=store)
            prepared = workflow.prepare([TaskAction("workspace.write", {"path": "a", "content": "b"}, False, (), "step-1"), action], task_id="task-metadata")
            reloaded = ApprovalWorkflow(self.executor, self.git, store=store)
            request = reloaded._load(prepared["request_id"])
            self.assertEqual(request.actions[1].step_id, "step-2")
            self.assertEqual(request.actions[1].dependencies, ("step-1",))

    def test_reject_consumes_request(self):
        self.registry.test_runner.run = Mock(return_value={"ok": True, "returncode": 0})
        self.git.diff.return_value = "diff"
        prepared = self.workflow.prepare([TaskAction("workspace.write", {"path": "x", "content": "y"})])
        result = self.workflow.reject(prepared["request_id"])
        self.assertTrue(result["rejected"])
        with self.assertRaises(ApprovalDeniedError):
            self.workflow.approve(prepared["request_id"], "should fail")

    def test_expired_request_cannot_be_approved(self):
        self.registry.test_runner.run = Mock(return_value={"ok": True, "returncode": 0})
        self.git.diff.return_value = "diff"
        workflow = ApprovalWorkflow(self.executor, self.git, approval_ttl_seconds=-1)
        prepared = workflow.prepare([TaskAction("workspace.write", {"path": "x", "content": "y"})])
        with self.assertRaises(ApprovalDeniedError):
            workflow.approve(prepared["request_id"], "expired")

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

    def test_approved_request_is_idempotent_after_restart(self):
        self.registry.test_runner.run = Mock(return_value={"ok": True, "returncode": 0})
        self.git.diff.return_value = "same diff"
        self.git.commit.return_value = "committed"
        with tempfile.TemporaryDirectory() as root:
            store = TaskStore(f"{root}/tasks.sqlite3")
            from app.task_service import TaskService
            TaskService(store).create_task("idempotent approval", task_id="task-idempotent")
            first = ApprovalWorkflow(self.executor, self.git, store=store)
            prepared = first.prepare([TaskAction("workspace.write", {"path": "x", "content": "y"})], task_id="task-idempotent")
            first_result = first.approve(prepared["request_id"], "commit once")
            self.assertTrue(first_result["ok"])
            second = ApprovalWorkflow(self.executor, self.git, store=store)
            second_result = second.approve(prepared["request_id"], "commit again")
            self.assertTrue(second_result["ok"])
            self.assertTrue(second_result["idempotent"])
            self.git.commit.assert_called_once_with("commit once", approved=True)

    def test_unknown_request_is_rejected(self):
        with self.assertRaises(ApprovalNotFoundError):
            self.workflow.approve("missing", "commit")


if __name__ == "__main__":
    unittest.main()
