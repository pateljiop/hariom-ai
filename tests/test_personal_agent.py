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

    def test_agent_pauses_for_approval(self):
        with tempfile.TemporaryDirectory() as d:
            ws=Workspace(d); activity=Mock()
            class WriteRouter(FakeRouter):
                def chat_messages(self,messages,**kwargs):
                    return {"role":"assistant","content":"{\"steps\":[{\"description\":\"Write a file\",\"tool\":\"write_file\",\"arguments\":{\"path\":\"x.txt\",\"content\":\"x\"}}]}"}, "fake"
            state=PersonalAgent(WriteRouter(),ws,activity,memory=MemoryStore(Path(d)/"memory.sqlite3")).run("write x")
            self.assertEqual(state.status,TaskStatus.WAITING_APPROVAL)
            self.assertFalse((Path(d)/"x.txt").exists())

if __name__=="__main__":
    unittest.main()
