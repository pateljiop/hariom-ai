import tempfile
import unittest
from pathlib import Path

from app.activity import ActivityBus
from app.workstation import Workstation


class FakeRouter:
    def chat(self, request, system=None, preferred=None, profile=None):
        # Minimal valid plan: read-only workspace listing.
        return ('{"user_request":"%s","objective":"list workspace","actions":[{"step_id":"s1","tool":"workspace.list","arguments":{}}],"test_target":"tests","max_retries":0}' % request.replace('"', '\\"'), "fake")


class WorkstationTests(unittest.TestCase):
    def test_ui_uses_shared_registry_and_router(self):
        with tempfile.TemporaryDirectory() as tmp:
            activity = ActivityBus()
            ws = Workstation(activity=activity, workspace=Path(tmp), max_workers=1)
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
