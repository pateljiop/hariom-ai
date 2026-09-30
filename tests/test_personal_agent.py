import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from app.agent import PersonalAgent
from app.memory import MemoryStore
from app.task_engine import TaskStatus
from app.workspace import Workspace
from app.context import WorkspaceContext
from app.skills import SkillRegistry

class FakeRouter:
    def chat_messages(self, messages, **kwargs):
        return {"role":"assistant","content":"{\"steps\":[{\"description\":\"List project files\",\"tool\":\"list_files\",\"arguments\":{\"limit\":10}}]}"}, "fake"

class PersonalAgentTests(unittest.TestCase):
    def test_memory_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            store=MemoryStore(Path(d)/"memory.sqlite3")
            mid=store.remember("Use Python for this project",kind="preference",tags="coding")
            self.assertEqual(store.search("Python")[0]["id"],mid)
            self.assertTrue(store.forget(mid))
            self.assertEqual(store.search("Python"),[])

    def test_agent_executes_and_verifies_safe_tool(self):
        with tempfile.TemporaryDirectory() as d:
            ws=Workspace(d); ws.write_file("hello.txt","hello"); activity=Mock()
            agent=PersonalAgent(FakeRouter(),ws,activity,memory=MemoryStore(Path(d)/"memory.sqlite3"))
            state=agent.run("List the project files")
            self.assertEqual(state.status,TaskStatus.COMPLETED)
            self.assertIn("hello.txt",state.steps[0]["output"])

    def test_screen_click_request_uses_verified_click_tool_without_planner(self):
        with tempfile.TemporaryDirectory() as d:
            ws=Workspace(d); activity=Mock()
            router=Mock()
            agent=PersonalAgent(router,ws,activity,memory=MemoryStore(Path(d)/"memory.sqlite3"))
            tool=Mock()
            tool.requires_approval=True
            agent.tools._tools["computer_click_target"] = tool
            state=agent.run("github tab pr click karo")
            self.assertEqual(state.status,TaskStatus.WAITING_APPROVAL)
            self.assertEqual(state.steps[0]["tool"],"computer_click_target")
            self.assertEqual(state.steps[0]["arguments"]["target"],"github tab")
            router.chat_messages.assert_not_called()

    def test_agent_pauses_for_approval(self):
        with tempfile.TemporaryDirectory() as d:
            ws=Workspace(d); activity=Mock()
            class WriteRouter(FakeRouter):
                def chat_messages(self,messages,**kwargs):
                    return {"role":"assistant","content":"{\"steps\":[{\"description\":\"Write a file\",\"tool\":\"write_file\",\"arguments\":{\"path\":\"x.txt\",\"content\":\"x\"}}]}"}, "fake"
            agent=PersonalAgent(WriteRouter(),ws,activity,memory=MemoryStore(Path(d)/"memory.sqlite3"))
            state=agent.run("write x")
            self.assertEqual(state.status,TaskStatus.WAITING_APPROVAL)
            self.assertFalse((Path(d)/"x.txt").exists())
            saved = agent.checkpoints.load(agent.task_id(state))
            self.assertIsNotNone(saved)
            self.assertEqual(saved.status, TaskStatus.WAITING_APPROVAL)
            self.assertEqual(saved.current_step, 0)

if __name__=="__main__":
    unittest.main()
