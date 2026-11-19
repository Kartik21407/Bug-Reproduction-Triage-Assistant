"""Tests for connecting GitHub and choosing a repository (US-26) and for
previewing then filing an issue (US-27), app/api/github.py.

GitHub is never contacted: `app.github.client._send` is replaced by a fake
that answers the four calls this application makes and records every
request, so a test can show exactly what was sent, and when nothing was."""

from urllib.parse import urlparse

import pytest
from sqlalchemy import update

import app.api.analysis as analysis_module
from app.analysis.schema import RawExtractionResult, RawModelField
from app.config import get_settings
from app.corpus import embedding
from app.corpus.importer import import_rows
from app.github import client as github_client
from app.models.core import BugReport
from app.models.github import GitHubConnection
from app.models.types import EMBEDDING_DIMENSIONS
from app.security import decrypt_secret
from tests.conftest import TestingSessionLocal, create_report, register_and_login

TOKEN = "github_pat_test_only_0123456789abcdef"
REPORT_TEXT = "Login crashes when I enter a wrong password and click submit."


def _repo(name: str, *, private: bool = False, has_issues: bool = True, archived: bool = False):
    return {"full_name": name, "private": private, "has_issues": has_issues, "archived": archived}


class FakeGitHub:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.repos = [
            _repo("octocat/app"),
            _repo("octocat/secret", private=True),
            _repo("octocat/no-issues", has_issues=False),
            _repo("octocat/old", archived=True),
        ]
        # None means a fine-grained token: GitHub sends no X-OAuth-Scopes.
        self.scopes: str | None = None
        self.create_response: tuple[int, dict, object] | None = None
        self.issue_number = 41

    def __call__(self, method: str, url: str, token: str, body: dict | None):
        self.calls.append({"method": method, "url": url, "token": token, "body": body})
        path = urlparse(url).path
        if token != TOKEN:
            return 401, {}, {"message": "Bad credentials"}
        headers = {} if self.scopes is None else {"x-oauth-scopes": self.scopes}
        if method == "GET" and path == "/user":
            return 200, headers, {"login": "octocat"}
        if method == "GET" and path == "/user/repos":
            return 200, headers, self.repos
        if method == "POST" and path.endswith("/issues"):
            if self.create_response is not None:
                return self.create_response
            self.issue_number += 1
            return (
                201,
                {},
                {
                    "number": self.issue_number,
                    "html_url": f"https://github.com/octocat/app/issues/{self.issue_number}",
                },
            )
        return 404, {}, {"message": "Not Found"}

    def posts(self) -> list[dict]:
        return [c for c in self.calls if c["method"] == "POST"]


@pytest.fixture
def github(monkeypatch: pytest.MonkeyPatch) -> FakeGitHub:
    fake = FakeGitHub()
    monkeypatch.setattr(github_client, "_send", fake)
    return fake


def _connected(client, repository: str | None = "octocat/app") -> None:
    register_and_login(client)
    client.put("/api/github/connection", json={"token": TOKEN})
    if repository:
        client.put("/api/github/connection/repository", json={"repository": repository})


def _analysed_report(client, monkeypatch) -> str:
    report_id = create_report(client, REPORT_TEXT).json()["id"]
    raw = RawExtractionResult(
        title=RawModelField(
            value="Login crash on a wrong password",
            source_quote="Login crashes",
            confidence=0.9,
            reason="Stated",
        )
    )
    monkeypatch.setattr(analysis_module, "extract", lambda text: raw)
    client.post(f"/api/reports/{report_id}/analyze")
    return report_id


class TestConnect:
    def test_a_fine_grained_token_is_accepted(self, client, github):
        """US-26 criterion 1."""
        register_and_login(client)

        response = client.put("/api/github/connection", json={"token": TOKEN})

        assert response.status_code == 200
        assert response.json() == {"connected": True, "login": "octocat", "repository": None}

    def test_an_invalid_token_shows_a_clear_error_and_stores_nothing(self, client, github):
        """US-26 criterion 2."""
        register_and_login(client)

        response = client.put("/api/github/connection", json={"token": "not-a-real-token"})

        assert response.status_code == 400
        assert response.json()["detail"].startswith("GitHub did not accept this token.")
        assert client.get("/api/github/connection").json()["connected"] is False

    def test_the_token_is_encrypted_at_rest(self, client, github):
        """US-26 criterion 3, first half."""
        register_and_login(client)
        client.put("/api/github/connection", json={"token": TOKEN})

        with TestingSessionLocal() as db:
            stored = db.query(GitHubConnection).one().encrypted_token

        assert TOKEN not in stored
        assert decrypt_secret(stored) == TOKEN

    def test_the_token_is_never_sent_back_to_the_browser(self, client, github, monkeypatch):
        """US-26 criterion 3, second half: no response anywhere carries it."""
        _connected(client)
        report_id = _analysed_report(client, monkeypatch)

        responses = [
            client.get("/api/github/connection"),
            client.put("/api/github/connection", json={"token": TOKEN}),
            client.get("/api/github/repositories"),
            client.put("/api/github/connection/repository", json={"repository": "octocat/app"}),
            client.get(f"/api/reports/{report_id}/github/preview"),
            client.post(f"/api/reports/{report_id}/github/issue", json={}),
        ]

        for response in responses:
            assert TOKEN not in response.text

    def test_disconnecting_deletes_the_token(self, client, github):
        _connected(client)

        assert client.delete("/api/github/connection").status_code == 204
        assert client.get("/api/github/connection").json()["connected"] is False
        with TestingSessionLocal() as db:
            assert db.query(GitHubConnection).count() == 0

    def test_without_an_encryption_key_github_is_switched_off(self, client, github, monkeypatch):
        monkeypatch.setattr(get_settings(), "token_encryption_key", "")
        register_and_login(client)

        response = client.put("/api/github/connection", json={"token": TOKEN})

        assert response.status_code == 503


class TestRepositories:
    def test_only_repositories_where_the_token_can_create_issues_are_listed(self, client, github):
        """US-26 criterion 4: issues switched on and not archived."""
        _connected(client, repository=None)

        names = [r["full_name"] for r in client.get("/api/github/repositories").json()]

        assert names == ["octocat/app", "octocat/secret"]

    def test_a_classic_token_with_public_repo_scope_lists_no_private_repository(
        self, client, github
    ):
        """US-26 criterion 4, for a classic token's scopes."""
        github.scopes = "public_repo, read:user"
        _connected(client, repository=None)

        names = [r["full_name"] for r in client.get("/api/github/repositories").json()]

        assert names == ["octocat/app"]

    def test_a_classic_token_without_a_repo_scope_lists_nothing(self, client, github):
        github.scopes = "read:user"
        _connected(client, repository=None)

        assert client.get("/api/github/repositories").json() == []

    def test_only_a_listed_repository_can_be_chosen(self, client, github):
        _connected(client, repository=None)

        chosen = client.put("/api/github/connection/repository", json={"repository": "octocat/app"})
        refused = client.put(
            "/api/github/connection/repository", json={"repository": "octocat/no-issues"}
        )

        assert chosen.json()["repository"] == "octocat/app"
        assert refused.status_code == 422

    def test_listing_without_a_connection_is_refused(self, client, github):
        register_and_login(client)

        assert client.get("/api/github/repositories").status_code == 409


class TestPreview:
    def test_the_preview_shows_the_exact_title_body_and_labels(self, client, github, monkeypatch):
        """US-27 criterion 1."""
        _connected(client)
        report_id = _analysed_report(client, monkeypatch)

        preview = client.get(f"/api/reports/{report_id}/github/preview").json()

        assert preview["repository"] == "octocat/app"
        assert preview["title"] == "Login crash on a wrong password"
        assert preview["labels"] == ["bug"]
        markdown = client.get(f"/api/reports/{report_id}/markdown").json()["markdown"]
        assert preview["body"] == markdown[markdown.index("## Summary") :]

    def test_nothing_is_sent_until_confirm(self, client, github, monkeypatch):
        """US-27 criterion 2: previewing makes no GitHub call at all."""
        _connected(client)
        report_id = _analysed_report(client, monkeypatch)
        github.calls.clear()

        client.get(f"/api/reports/{report_id}/github/preview")
        client.get(f"/api/reports/{report_id}/github/preview")

        assert github.calls == []


class TestCreateIssue:
    def test_confirm_sends_exactly_the_preview_and_stores_the_url(
        self, client, github, monkeypatch
    ):
        """US-27 criteria 1 and 5."""
        _connected(client)
        report_id = _analysed_report(client, monkeypatch)
        preview = client.get(f"/api/reports/{report_id}/github/preview").json()

        response = client.post(f"/api/reports/{report_id}/github/issue", json={})

        assert response.status_code == 200
        assert response.json() == {
            "issue_url": "https://github.com/octocat/app/issues/42",
            "issue_number": 42,
            "created": True,
        }
        sent = github.posts()[0]
        assert urlparse(sent["url"]).path == "/repos/octocat/app/issues"
        assert sent["body"] == {
            "title": preview["title"],
            "body": preview["body"],
            "labels": preview["labels"],
        }
        report = client.get(f"/api/reports/{report_id}").json()
        assert report["state"] == "Submitted"
        preview_after = client.get(f"/api/reports/{report_id}/github/preview").json()
        assert preview_after["issue_url"] == "https://github.com/octocat/app/issues/42"

    def test_clicking_confirm_twice_does_not_create_two_issues(self, client, github, monkeypatch):
        """US-27 criterion 4."""
        _connected(client)
        report_id = _analysed_report(client, monkeypatch)

        first = client.post(f"/api/reports/{report_id}/github/issue", json={}).json()
        second = client.post(f"/api/reports/{report_id}/github/issue", json={}).json()

        assert len(github.posts()) == 1
        assert second == {**first, "created": False}

    def test_a_confirm_while_another_is_filing_creates_nothing(self, client, github, monkeypatch):
        """US-27 criterion 4, for two clicks at the same moment: the second
        finds the report already claimed."""
        _connected(client)
        report_id = _analysed_report(client, monkeypatch)
        with TestingSessionLocal() as db:
            db.execute(update(BugReport).values(github_submitting=True))
            db.commit()

        response = client.post(f"/api/reports/{report_id}/github/issue", json={})

        assert response.status_code == 409
        assert github.posts() == []

    def test_on_failure_the_draft_is_kept_and_the_error_shown(self, client, github, monkeypatch):
        """US-27 criterion 6."""
        _connected(client)
        report_id = _analysed_report(client, monkeypatch)
        github.create_response = (403, {}, {"message": "Resource not accessible"})

        failed = client.post(f"/api/reports/{report_id}/github/issue", json={})

        assert failed.status_code == 502
        assert "Issues: Read and write" in failed.json()["detail"]
        report = client.get(f"/api/reports/{report_id}").json()
        assert report["state"] == "Analysed"
        assert client.get(f"/api/reports/{report_id}/github/preview").json()["issue_url"] is None

        github.create_response = None
        retried = client.post(f"/api/reports/{report_id}/github/issue", json={})

        assert retried.json()["created"] is True

    def test_a_rate_limit_says_to_wait(self, client, github, monkeypatch):
        """DR-09: 403 and 429 from GitHub are handled."""
        _connected(client)
        report_id = _analysed_report(client, monkeypatch)
        github.create_response = (403, {"x-ratelimit-remaining": "0"}, {"message": "limit"})

        response = client.post(f"/api/reports/{report_id}/github/issue", json={})

        assert response.status_code == 503
        assert "rate limit" in response.json()["detail"]

    def test_a_draft_report_or_no_repository_cannot_be_filed(self, client, github):
        _connected(client, repository=None)
        report_id = create_report(client, REPORT_TEXT).json()["id"]

        assert client.post(f"/api/reports/{report_id}/github/issue", json={}).status_code == 409
        assert github.posts() == []

    def test_another_users_report_returns_404(self, client, github, monkeypatch):
        """NFR-15."""
        _connected(client)
        report_id = _analysed_report(client, monkeypatch)
        client.post("/api/auth/logout")
        register_and_login(client, "other@example.com")

        assert client.get(f"/api/reports/{report_id}/github/preview").status_code == 404
        assert client.post(f"/api/reports/{report_id}/github/issue", json={}).status_code == 404


class TestLikelyDuplicates:
    """US-27 criterion 3: if a Likely duplicate exists, the user must
    acknowledge it first."""

    def _with_likely_duplicate(self, client, monkeypatch) -> tuple[str, str]:
        query = [1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1)
        close = [0.9, (1 - 0.81) ** 0.5] + [0.0] * (EMBEDDING_DIMENSIONS - 2)
        monkeypatch.setattr(
            embedding,
            "embed",
            lambda texts: [close if t.startswith("Close match") else query for t in texts],
        )
        with TestingSessionLocal() as db:
            import_rows(
                db,
                [
                    {
                        "id": "acme/app#1",
                        "title": "Close match",
                        "body": "b",
                        "url": "https://github.com/acme/app/issues/1",
                    }
                ],
            )
        _connected(client)
        report_id = _analysed_report(client, monkeypatch)
        candidates = client.post(f"/api/reports/{report_id}/duplicates").json()["candidates"]
        return report_id, candidates[0]["candidate_id"]

    def test_filing_is_refused_until_the_likely_duplicate_is_acknowledged(
        self, client, github, monkeypatch
    ):
        report_id, _ = self._with_likely_duplicate(client, monkeypatch)

        preview = client.get(f"/api/reports/{report_id}/github/preview").json()
        refused = client.post(f"/api/reports/{report_id}/github/issue", json={})
        accepted = client.post(
            f"/api/reports/{report_id}/github/issue",
            json={"acknowledge_likely_duplicates": True},
        )

        assert [d["title"] for d in preview["likely_duplicates"]] == ["Close match"]
        assert refused.status_code == 409
        assert accepted.json()["created"] is True
        assert len(github.posts()) == 1

    def test_a_candidate_marked_not_a_duplicate_needs_no_acknowledgement(
        self, client, github, monkeypatch
    ):
        report_id, candidate_id = self._with_likely_duplicate(client, monkeypatch)
        client.put(
            f"/api/reports/{report_id}/duplicates/{candidate_id}/decision",
            json={"decision": "not_duplicate"},
        )

        response = client.post(f"/api/reports/{report_id}/github/issue", json={})

        assert response.json()["created"] is True
