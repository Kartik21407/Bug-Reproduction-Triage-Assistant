"""The GitHub REST API calls this application makes (DR-08, DR-09).

Every call goes through `_send`, the one function that touches the network,
which is what lets the test suite replace it and never reach GitHub. Every
failure becomes a `GitHubError` carrying a message written for the person
using the application; the token itself never appears in any message.

Which repositories a token can file issues in: for a classic token, GitHub
reports its scopes in the `X-OAuth-Scopes` header, so a repository is
listed only when that scope allows writing issues there. A fine-grained
token's per-repository permissions cannot be read back from GitHub; it only
ever sees the repositories it was granted, and those with issues switched
on are listed. If it lacks "Issues: Read and write", GitHub refuses at
creation, and that refusal is shown with the draft kept (US-27 criterion 6).
"""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from app.corpus.github import next_page_url

API = "https://api.github.com"
_TIMEOUT_SECONDS = 15


class GitHubError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class GitHubAuthError(GitHubError):
    """GitHub did not accept the token at all."""


@dataclass(frozen=True)
class Repository:
    full_name: str
    private: bool


@dataclass(frozen=True)
class CreatedIssue:
    number: int
    url: str


def _send(
    method: str, url: str, token: str, body: dict[str, Any] | None
) -> tuple[int, dict[str, str], Any]:
    """One HTTP request: the status, the response headers (lower-cased
    names) and the decoded JSON body."""
    request = urllib.request.Request(
        url,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "bug-triage-assistant",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            headers = {k.lower(): v for k, v in response.headers.items()}
            return response.status, headers, json.load(response)
    except urllib.error.HTTPError as error:
        headers = {k.lower(): v for k, v in error.headers.items()}
        try:
            data = json.load(error)
        except (json.JSONDecodeError, ValueError):
            data = None
        return error.code, headers, data
    except (urllib.error.URLError, TimeoutError) as error:
        raise GitHubError(
            0, "Could not reach GitHub. Check the connection and try again."
        ) from error


def _error(status: int, headers: dict[str, str], data: Any) -> GitHubError:
    detail = data.get("message") if isinstance(data, dict) else None
    if status == 401:
        return GitHubAuthError(
            401,
            "GitHub did not accept this token. Check it was copied in full and has not "
            "expired or been revoked.",
        )
    if status == 429 or (status == 403 and headers.get("x-ratelimit-remaining") == "0"):
        return GitHubError(status, "GitHub's rate limit was reached. Wait a few minutes and retry.")
    if status == 403:
        return GitHubError(
            403,
            "GitHub refused this. The token may not be allowed to create issues in this "
            'repository; a fine-grained token needs "Issues: Read and write".',
        )
    if status == 404:
        return GitHubError(404, "GitHub could not find this repository with this token.")
    if status == 410:
        return GitHubError(410, "Issues are switched off for this repository.")
    if status == 422:
        return GitHubError(422, f"GitHub rejected the issue: {detail or 'invalid request'}.")
    return GitHubError(status, f"GitHub returned an error ({status}). Try again.")


def _call(
    method: str, url: str, token: str, body: dict[str, Any] | None = None, ok: int = 200
) -> tuple[Any, dict[str, str]]:
    status, headers, data = _send(method, url, token, body)
    if status != ok:
        raise _error(status, headers, data)
    return data, headers


def authenticated_login(token: str) -> str:
    """The GitHub account a token belongs to. Raises `GitHubAuthError` for
    a token GitHub does not accept (US-26 criterion 2)."""
    data, _ = _call("GET", f"{API}/user", token)
    return str(data["login"])


def _can_file_issues(repo: dict[str, Any], scopes: str | None) -> bool:
    """Issues switched on, not archived or disabled, and, for a classic
    token, a scope that allows writing issues there."""
    if not repo.get("has_issues") or repo.get("archived") or repo.get("disabled"):
        return False
    if scopes is None:
        return True
    granted = {scope.strip() for scope in scopes.split(",")}
    return "repo" in granted or ("public_repo" in granted and not repo.get("private"))


def issue_repositories(token: str) -> list[Repository]:
    """Repositories the token can file issues in (US-26 criterion 4): issues
    switched on, not archived, and allowed by the token's scopes."""
    url: str | None = (
        f"{API}/user/repos?per_page=100&sort=full_name"
        "&affiliation=owner,collaborator,organization_member"
    )
    found: list[Repository] = []
    while url:
        data, headers = _call("GET", url, token)
        scopes = headers.get("x-oauth-scopes")
        found += [
            Repository(repo["full_name"], bool(repo.get("private")))
            for repo in data
            if _can_file_issues(repo, scopes)
        ]
        url = next_page_url(headers.get("link"))
    return sorted(found, key=lambda r: r.full_name.lower())


def create_issue(
    token: str, repository: str, title: str, body: str, labels: list[str]
) -> CreatedIssue:
    """Creates one issue (DR-08) and returns its number and address."""
    data, _ = _call(
        "POST",
        f"{API}/repos/{repository}/issues",
        token,
        {"title": title, "body": body, "labels": labels},
        ok=201,
    )
    return CreatedIssue(number=int(data["number"]), url=str(data["html_url"]))
