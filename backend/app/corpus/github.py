"""Fetches public issues from one GitHub repository into the corpus import
format (`id`, `title`, `body`, `url`), as D5 plans for the initial corpus.

This only produces a file for `importer.py` to read; it never writes to the
database itself, so whatever it fetched can be inspected before it is
imported. Pull requests are left out (the issues API returns them too), as
are issues with no body, since there would be nothing to compare against.
Uses the standard library only.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

_API = "https://api.github.com"
_PAGE_SIZE = 100


class GitHubFetchError(RuntimeError):
    pass


def issue_to_row(repository: str, issue: dict[str, Any]) -> dict[str, str] | None:
    """One GitHub issue as an import row, or None when it should be left
    out: a pull request, or an issue with an empty body."""
    if "pull_request" in issue:
        return None
    body = (issue.get("body") or "").strip()
    if not body:
        return None
    return {
        "id": f"{repository}#{issue['number']}",
        "title": issue["title"],
        "body": body,
        "url": issue["html_url"],
    }


def fetch_issues(
    repository: str, label: str | None, limit: int, token: str | None = None
) -> list[dict[str, str]]:
    """Up to `limit` issues from `owner/name`, newest first, optionally only
    those carrying `label`. Without a token GitHub allows 60 requests an
    hour, enough for a few thousand issues at 100 per page.

    Pages are followed through the `Link: rel="next"` header GitHub sends,
    not by counting page numbers: GitHub refuses numbered pages beyond the
    tenth on a large repository, and a label shared with pull requests can
    need many pages to yield enough issues."""
    params = {"state": "all", "per_page": str(_PAGE_SIZE)}
    if label:
        params["labels"] = label
    url: str | None = f"{_API}/repos/{repository}/issues?{urllib.parse.urlencode(params)}"

    rows: list[dict[str, str]] = []
    while url and len(rows) < limit:
        issues, url = _get_page(url, token)
        for issue in issues:
            row = issue_to_row(repository, issue)
            if row is not None:
                rows.append(row)
    return rows[:limit]


def next_page_url(link_header: str | None) -> str | None:
    """The `rel="next"` address from a GitHub `Link` header, if any."""
    if not link_header:
        return None
    for part in link_header.split(","):
        address, _, relation = part.partition(";")
        if 'rel="next"' in relation:
            return address.strip().strip("<>")
    return None


def _get_page(url: str, token: str | None) -> tuple[list[dict[str, Any]], str | None]:
    """One page of issues and the address of the next page."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "bug-triage-assistant-corpus-import",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response), next_page_url(response.headers.get("Link"))
    except urllib.error.HTTPError as error:
        if error.code in (403, 429):
            raise GitHubFetchError(
                "GitHub refused the request, most likely its rate limit. Wait an hour or pass "
                "--token with a personal access token."
            ) from error
        if error.code == 404:
            raise GitHubFetchError(f"Repository not found: {url}") from error
        raise GitHubFetchError(f"GitHub returned HTTP {error.code}") from error
    except urllib.error.URLError as error:
        raise GitHubFetchError(f"Could not reach GitHub: {error.reason}") from error
