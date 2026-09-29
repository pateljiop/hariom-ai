import os


class GitHubTools:
    """Optional GitHub integration using the GitHub REST API."""

    def __init__(self, activity):
        self.activity = activity
        self.token = os.getenv("GITHUB_TOKEN", "").strip()

    def _request(self, method, path, **kwargs):
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("GitHub tools need the requests package.") from exc
        if not self.token:
            raise RuntimeError("GITHUB_TOKEN is not configured.")
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + self.token,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        response = requests.request(
            method,
            "https://api.github.com" + path,
            headers=headers,
            timeout=20,
            **kwargs,
        )
        if response.status_code >= 400:
            raise RuntimeError("GitHub API %s: %s" % (response.status_code, response.text[:2000]))
        return response.json()

    def repo(self, repository):
        return self._request("GET", "/repos/" + str(repository))

    def issue(self, repository, number):
        return self._request("GET", "/repos/%s/issues/%s" % (repository, int(number)))

    def list_issues(self, repository, state="open", limit=20):
        data = self._request(
            "GET",
            "/repos/%s/issues" % repository,
            params={"state": state, "per_page": max(1, min(int(limit), 100))},
        )
        return [
            {"number": x["number"], "title": x["title"], "state": x["state"], "url": x["html_url"]}
            for x in data
            if "pull_request" not in x
        ]

    def create_issue(self, repository, title, body=""):
        return self._request(
            "POST",
            "/repos/%s/issues" % repository,
            json={"title": str(title), "body": str(body)},
        )

    def create_comment(self, repository, number, body):
        return self._request(
            "POST",
            "/repos/%s/issues/%s/comments" % (repository, int(number)),
            json={"body": str(body)},
        )
