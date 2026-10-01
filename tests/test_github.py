import unittest
from unittest.mock import Mock, patch

from app.github import GitHubClient


class GitHubClientTests(unittest.TestCase):
    def test_parse_remote_supports_ssh_and_https(self):
        self.assertEqual(
            GitHubClient._parse_remote("git@github.com:pateljiop/hariom-ai.git"),
            ("pateljiop", "hariom-ai"),
        )
        self.assertEqual(
            GitHubClient._parse_remote("https://github.com/pateljiop/hariom-ai.git"),
            ("pateljiop", "hariom-ai"),
        )
        self.assertEqual(
            GitHubClient._parse_remote("https://gitlab.com/pateljiop/hariom-ai.git"),
            ("", ""),
        )

    @patch("app.github.subprocess.run")
    def test_repo_context_reads_remote_and_github_metadata(self, run):
        run.return_value = Mock(returncode=0, stdout="git@github.com:pateljiop/hariom-ai.git\n")
        client = GitHubClient(".")
        response = Mock(ok=True)
        response.json.return_value = {
            "default_branch": "main",
            "visibility": "public",
            "private": False,
            "description": "test repo",
            "html_url": "https://github.com/pateljiop/hariom-ai",
            "open_issues_count": 2,
        }
        with patch("app.github.requests.get", return_value=response) as get:
            context = client.repo_context()

        self.assertEqual(context["full_name"], "pateljiop/hariom-ai")
        self.assertEqual(context["default_branch"], "main")
        self.assertFalse(context["private"])
        get.assert_called_once()

    @patch("app.github.subprocess.run")
    @patch("app.github.requests.get")
    def test_issues_excludes_pull_requests(self, get, run):
        run.return_value = Mock(returncode=0, stdout="https://github.com/pateljiop/hariom-ai.git\n")
        response = Mock(ok=True)
        response.json.return_value = [
            {"number": 1, "title": "Bug", "state": "open", "user": {"login": "user"}, "labels": [], "comments": 0},
            {"number": 2, "title": "PR", "state": "open", "user": {"login": "user"}, "pull_request": {"url": "x"}},
        ]
        get.return_value = response
        items = GitHubClient(".").issues()
        self.assertEqual([item["number"] for item in items], [1])

    @patch("app.github.subprocess.run")
    @patch("app.github.requests.get")
    def test_pull_request_reviews_are_read_only(self, get, run):
        run.return_value = Mock(returncode=0, stdout="git@github.com:pateljiop/hariom-ai.git\n")
        response = Mock(ok=True)
        response.json.return_value = [
            {"id": 7, "user": {"login": "reviewer"}, "state": "APPROVED", "body": "Looks good", "submitted_at": "2026-09-20T00:00:00Z", "html_url": "https://github.com/x"}
        ]
        get.return_value = response
        items = GitHubClient(".").pull_request_reviews(7)
        self.assertEqual(items[0]["state"], "APPROVED")
        self.assertEqual(items[0]["user"], "reviewer")

    def test_invalid_pull_request_number_is_rejected(self):
        with self.assertRaises(ValueError):
            GitHubClient(".").pull_request_reviews(0)


if __name__ == "__main__":
    unittest.main()
