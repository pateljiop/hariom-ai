import os
import re
import subprocess
from urllib.parse import urlparse

import requests


API_BASE = "https://api.github.com"
TIMEOUT = 15
DEFAULT_LIMIT = 20
MAX_BODY = 6000


class GitHubClient:
    """Read-only GitHub context for the local agent."""

    def __init__(self, root, activity=None):
        self.root = root
        self.activity = activity
        self.token = os.getenv("GITHUB_TOKEN", "").strip()

    def repo_context(self):
        remote = self._remote_url()
        owner, name = self._parse_remote(remote)
        result = {
            "configured": bool(owner and name),
            "owner": owner,
            "name": name,
            "full_name": f"{owner}/{name}" if owner and name else "",
            "remote": remote,
            "authenticated": bool(self.token),
        }
        if owner and name:
            data = self._request(f"/repos/{owner}/{name}")
            result.update({
                "default_branch": data.get("default_branch", ""),
                "visibility": data.get("visibility", ""),
                "private": bool(data.get("private", False)),
                "description": data.get("description", "") or "",
                "html_url": data.get("html_url", ""),
                "open_issues_count": data.get("open_issues_count", 0),
            })
        return result

    def issues(self, state="open", limit=DEFAULT_LIMIT):
        owner, name = self._repo_parts()
        limit = self._limit(limit)
        items = self._request(
            f"/repos/{owner}/{name}/issues",
            params={"state": state, "per_page": limit},
        )
        return [self._issue_item(item) for item in items if "pull_request" not in item]

    def pull_requests(self, state="open", limit=DEFAULT_LIMIT):
        owner, name = self._repo_parts()
        limit = self._limit(limit)
        items = self._request(
            f"/repos/{owner}/{name}/pulls",
            params={"state": state, "per_page": limit},
        )
        return [self._pr_item(item) for item in items]

    def branches(self, limit=DEFAULT_LIMIT):
        owner, name = self._repo_parts()
        items = self._request(
            f"/repos/{owner}/{name}/branches",
            params={"per_page": self._limit(limit)},
        )
        return [
            {
                "name": item.get("name", ""),
                "protected": bool(item.get("protected", False)),
                "sha": ((item.get("commit") or {}).get("sha", "")),
            }
            for item in items
        ]

    def commits(self, limit=DEFAULT_LIMIT):
        owner, name = self._repo_parts()
        items = self._request(
            f"/repos/{owner}/{name}/commits",
            params={"per_page": self._limit(limit)},
        )
        return [
            {
                "sha": item.get("sha", ""),
                "message": ((item.get("commit") or {}).get("message", "").splitlines() or [""])[0],
                "author": ((item.get("commit") or {}).get("author") or {}).get("name", ""),
                "date": ((item.get("commit") or {}).get("author") or {}).get("date", ""),
                "html_url": item.get("html_url", ""),
            }
            for item in items
        ]

    def pull_request_reviews(self, number):
        if not isinstance(number, int) or number < 1:
            raise ValueError("Pull request number must be a positive integer.")
        owner, name = self._repo_parts()
        items = self._request(f"/repos/{owner}/{name}/pulls/{number}/reviews")
        return [
            {
                "id": item.get("id"),
                "user": ((item.get("user") or {}).get("login", "")),
                "state": item.get("state", ""),
                "body": (item.get("body", "") or "")[:MAX_BODY],
                "submitted_at": item.get("submitted_at", ""),
                "html_url": item.get("html_url", ""),
            }
            for item in items
        ]

    def _repo_parts(self):
        remote = self._remote_url()
        owner, name = self._parse_remote(remote)
        if not owner or not name:
            raise ValueError("Selected workspace is not linked to a GitHub repository.")
        return owner, name

    def _remote_url(self):
        try:
            result = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(f"Could not inspect GitHub remote: {exc}") from exc
        if result.returncode != 0:
            raise ValueError("No git remote.origin.url found in the selected workspace.")
        return result.stdout.strip()

    @staticmethod
    def _parse_remote(remote):
        remote = (remote or "").strip()
        if remote.startswith("git@github.com:"):
            path = remote.split(":", 1)[1]
        else:
            parsed = urlparse(remote)
            if parsed.hostname and parsed.hostname.lower() == "github.com":
                path = parsed.path.lstrip("/")
            else:
                return "", ""
        path = re.sub(r"\.git$", "", path.strip("/"))
        parts = path.split("/")
        if len(parts) != 2:
            return "", ""
        owner, name = parts
        if not owner or not name:
            return "", ""
        return owner, name

    def _request(self, path, params=None):
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        if self.activity:
            self.activity.emit(f"GITHUB -> GET {path}")

        response = requests.get(
            API_BASE + path,
            headers=headers,
            params=params,
            timeout=TIMEOUT,
        )
        if not response.ok:
            body = (response.text or "").replace("\n", " ")[:500]
            raise RuntimeError(f"GitHub HTTP {response.status_code}: {body}")
        return response.json()

    @staticmethod
    def _limit(value):
        if not isinstance(value, int):
            return DEFAULT_LIMIT
        return max(1, min(value, DEFAULT_LIMIT))

    @staticmethod
    def _issue_item(item):
        return {
            "number": item.get("number"),
            "title": item.get("title", ""),
            "state": item.get("state", ""),
            "author": ((item.get("user") or {}).get("login", "")),
            "labels": [label.get("name", "") for label in item.get("labels", [])],
            "comments": item.get("comments", 0),
            "created_at": item.get("created_at", ""),
            "updated_at": item.get("updated_at", ""),
            "html_url": item.get("html_url", ""),
        }

    @staticmethod
    def _pr_item(item):
        return {
            "number": item.get("number"),
            "title": item.get("title", ""),
            "state": item.get("state", ""),
            "draft": bool(item.get("draft", False)),
            "author": ((item.get("user") or {}).get("login", "")),
            "head": ((item.get("head") or {}).get("ref", "")),
            "base": ((item.get("base") or {}).get("ref", "")),
            "created_at": item.get("created_at", ""),
            "updated_at": item.get("updated_at", ""),
            "html_url": item.get("html_url", ""),
        }
