import tempfile
import unittest
from unittest.mock import Mock

from app.task import Task, TaskStatus
from pathlib import Path

from app.activity import ActivityBus
from app.workstation import Workstation
from app.workspace import Workspace


class FakeRouter:
    def chat(self, request, system=None, preferred=None, profile=None):
        # Minimal valid plan: read-only workspace listing.
        return ('{"user_request":"%s","objective":"list workspace","actions":[{"step_id":"s1","tool":"workspace.list","arguments":{}}],"test_target":"tests","max_retries":0}' % request.replace('"', '\\"'), "fake")


class WorkstationTests(unittest.TestCase):

    def test_reject_cancels_commit_pending_task(self):
        ws = Workstation.__new__(Workstation)
        ws.task_service = Mock()
        ws.task_service.store.get_approval.return_value = {"task_id": "task-1"}
        ws.task_service.get_task.return_value = Task(
            "task-1", "request", "request", status=TaskStatus.AWAITING_COMMIT_APPROVAL
        )
        ws.agent = Mock()
        ws.agent.facade.executor.workflow.reject.return_value = {
            "ok": True, "request_id": "approval-1", "rejected": True
        }
        ws.activity = Mock()

        result = ws.reject("approval-1", "no longer needed")

        self.assertTrue(result["rejected"])
        ws.task_service.cancel_task.assert_called_once_with(
            "task-1", reason="no longer needed"
        )

    def test_ui_uses_shared_registry_and_router(self):
        with tempfile.TemporaryDirectory() as tmp:
            activity = ActivityBus()
            ws = Workstation(activity=activity, workspace=Workspace(tmp), max_workers=1)
            try:
                ws.attach_router(FakeRouter())
                self.assertIs(ws.agent.facade.planner.tool_registry, ws.registry)
                self.assertIs(ws.agent.facade.executor.workflow.executor.registry, ws.registry)
                planned = ws.plan("list files")
                self.assertEqual(planned["provider"], "fake")
                self.assertTrue(planned["plan"]["actions"])
            finally:
                ws.shutdown()


if __name__ == "__main__":
    unittest.main()
