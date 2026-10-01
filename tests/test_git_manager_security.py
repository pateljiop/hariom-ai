import unittest
from unittest.mock import Mock

from app.git_manager import GitManager


class GitManagerSecurityTests(unittest.TestCase):
    def test_secret_scan_includes_staged_changes(self):
        git = GitManager(".")
        git.diff = Mock(return_value="")
        git._run = Mock(return_value='+api_key = "supersecretvalue"')
        self.assertTrue(git.scan_diff_for_secrets())
        git._run.assert_called_once_with("diff", "--cached", "--")

    def test_merge_scans_incoming_branch_changes(self):
        git = GitManager(".")
        git.diff = Mock(return_value="")
        git._run = Mock(side_effect=["main", "", '+token = "incomingsecret"'])
        with self.assertRaises(PermissionError):
            git.merge_branch("feature", approved=True)
        self.assertEqual(git._run.call_args_list[0].args, ("branch", "--show-current"))
        self.assertEqual(git._run.call_args_list[1].args, ("diff", "HEAD", "feature", "--"))


if __name__ == "__main__":
    unittest.main()
