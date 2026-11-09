"""Tests for turning GitHub issues into import rows (app/corpus/github.py)
and for the corpus command line (app/corpus/cli.py). GitHub itself is
never contacted: the one network call is replaced with a fake."""

import json
from urllib.parse import parse_qs, urlparse

import app.corpus.github as github_module
from app.corpus import cli
from app.corpus.github import fetch_issues, issue_to_row, next_page_url
from app.corpus.importer import SkippedRow


def _github_issue(number: int, **overrides: object) -> dict[str, object]:
    issue: dict[str, object] = {
        "number": number,
        "title": f"Issue {number}",
        "body": f"Body of issue {number}",
        "html_url": f"https://github.com/acme/app/issues/{number}",
    }
    issue.update(overrides)
    return issue


class TestIssueToRow:
    def test_an_issue_becomes_an_import_row(self):
        row = issue_to_row("acme/app", _github_issue(12))

        assert row == {
            "id": "acme/app#12",
            "title": "Issue 12",
            "body": "Body of issue 12",
            "url": "https://github.com/acme/app/issues/12",
        }

    def test_a_pull_request_is_left_out(self):
        assert issue_to_row("acme/app", _github_issue(3, pull_request={"url": "x"})) is None

    def test_an_issue_without_a_body_is_left_out(self):
        assert issue_to_row("acme/app", _github_issue(4, body=None)) is None
        assert issue_to_row("acme/app", _github_issue(5, body="   ")) is None


class TestFetchIssues:
    def test_pages_are_followed_by_their_next_link_until_the_limit(self, monkeypatch):
        """More than ten pages, the point where GitHub stops accepting page
        numbers, all reached through the next link, with pull requests (most
        of each page here) skipped."""
        requested: list[str] = []

        def fake_get_page(url: str, token: str | None):
            requested.append(url)
            page = len(requested)
            issues = [_github_issue(page * 100 + n) for n in range(10)]
            issues += [_github_issue(page * 100 + n, pull_request={}) for n in range(10, 100)]
            return issues, f"https://api.github.com/next?after=cursor{page}"

        monkeypatch.setattr(github_module, "_get_page", fake_get_page)

        rows = fetch_issues("acme/app", "bug", 120)

        assert len(rows) == 120
        assert len(requested) == 12
        assert "labels=bug" in requested[0]
        assert "state=all" in requested[0]
        assert "page" not in parse_qs(urlparse(requested[0]).query)
        assert requested[11] == "https://api.github.com/next?after=cursor11"

    def test_fetching_stops_when_there_is_no_next_page(self, monkeypatch):
        monkeypatch.setattr(
            github_module, "_get_page", lambda url, token: ([_github_issue(1)], None)
        )

        assert len(fetch_issues("acme/app", None, 300)) == 1


class TestNextPageUrl:
    def test_the_next_link_is_read_from_the_header(self):
        header = (
            '<https://api.github.com/repositories/1/issues?after=Y3Vy&per_page=100>; rel="next", '
            '<https://api.github.com/repositories/1/issues?before=Y3Vy&per_page=100>; rel="prev"'
        )

        assert next_page_url(header) == (
            "https://api.github.com/repositories/1/issues?after=Y3Vy&per_page=100"
        )

    def test_no_next_link_means_the_last_page(self):
        assert next_page_url('<https://x>; rel="prev"') is None
        assert next_page_url(None) is None


class TestCommandLine:
    def test_fetch_github_writes_the_rows_to_a_json_file(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            cli, "fetch_issues", lambda repository, label, limit, token: [{"id": "acme/app#1"}]
        )
        out = tmp_path / "issues.json"

        exit_code = cli.main(["fetch-github", "acme/app", "--out", str(out)])

        assert exit_code == 0
        assert json.loads(out.read_text(encoding="utf-8")) == [{"id": "acme/app#1"}]

    def test_the_summary_lists_every_skipped_row(self):
        """US-19 criterion 2: invalid rows are reported."""
        text = cli.format_summary(
            3, 1, [SkippedRow(row=2, reason="Missing url"), SkippedRow(row=5, reason="Empty id")]
        )

        assert text == (
            "Imported 3 new, updated 1, skipped 2.\n  Row 2: Missing url\n  Row 5: Empty id"
        )
