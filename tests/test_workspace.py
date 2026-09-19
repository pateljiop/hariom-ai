import tempfile
import unittest
from pathlib import Path

from app.workspace import Workspace


class WorkspaceTests(unittest.TestCase):
    def test_write_and_read_inside_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Workspace(tmp)
            ws.write_file("nested/test.txt", "Hariom AI")
            self.assertEqual(ws.read_file("nested/test.txt"), "Hariom AI")

    def test_path_traversal_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Workspace(tmp)
            with self.assertRaises(ValueError):
                ws.write_file("../outside.txt", "blocked")


if __name__ == "__main__":
    unittest.main()
