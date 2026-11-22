"""Tests for the automatic import of a repository's open issues
(app/corpus/sync.py, app/corpus/scheduler.py, US-28). GitHub is faked by
replacing `app.corpus.github._get_page`; nothing reaches the network."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.corpus import github, scheduler, sync
from app.models.corpus import CorpusIssue
from tests.conftest import TestingSessionLocal

REPO = "acme/app"
PAGE_2 = "https://api.github.com/repositories/1/issues?state=open&page=2"
PAGE_3 = "https://api.github.com/repositories/1/issues?state=open&page=3"


def _issue(number: int) -> dict[str, object]:
    return {
        "number": number,
        "title": f"Issue {number}",
        "body": f"Body of issue {number}",
        "html_url": f"https://github.com/acme/app/issues/{number}",
    }


PAGES = {
    sync.first_page_url(REPO): ([_issue(1), _issue(2)], PAGE_2),
    PAGE_2: ([_issue(3), {"number": 4, "title": "PR", "body": "x", "pull_request": {}}], PAGE_3),
    PAGE_3: ([_issue(5)], None),
}


class FakeGitHub:
    """Serves PAGES, and refuses the pages listed in `limited` once each
    with a rate limit."""

    def __init__(self, limited: tuple[str, ...] = (), reset_at: datetime | None = None) -> None:
        self.limited = list(limited)
        self.reset_at = reset_at
        self.requested: list[str] = []

    def __call__(self, url: str, token: str | None):
        self.requested.append(url)
        if url in self.limited:
            self.limited.remove(url)
            raise github.GitHubRateLimitError("rate limited", reset_at=self.reset_at)
        return PAGES[url]


def _corpus_size() -> int:
    with TestingSessionLocal() as db:
        return db.execute(select(func.count()).select_from(CorpusIssue)).scalar_one()


def _run(fake: FakeGitHub, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(github, "_get_page", fake)
    with TestingSessionLocal() as db:
        state = sync.run_sync(db, REPO)
        return state.status, state.pages_done, state.imported, state.message


def test_open_issues_are_fetched_page_by_page(monkeypatch):
    """US-28 criterion 1: open issues, through the API, with pagination.
    The pull request on page two is left out."""
    fake = FakeGitHub()

    status, pages, imported, _ = _run(fake, monkeypatch)

    assert "state=open" in fake.requested[0]
    assert fake.requested == [sync.first_page_url(REPO), PAGE_2, PAGE_3]
    assert (status, pages, imported) == ("complete", 3, 4)
    assert _corpus_size() == 4


def test_a_rate_limit_pauses_without_losing_progress(monkeypatch):
    """US-28 criterion 2: the pages already fetched stay imported."""
    fake = FakeGitHub(limited=(PAGE_2,))

    status, pages, imported, message = _run(fake, monkeypatch)

    assert (status, pages, imported) == ("paused", 1, 2)
    assert _corpus_size() == 2
    assert "resumes from page 2" in message


def test_the_next_run_resumes_from_the_refused_page(monkeypatch):
    """US-28 criterion 2: the next run asks for the refused page, not page
    one, and finishes the import."""
    fake = FakeGitHub(limited=(PAGE_2,))
    _run(fake, monkeypatch)
    fake.requested.clear()

    status, pages, imported, _ = _run(fake, monkeypatch)

    assert fake.requested == [PAGE_2, PAGE_3]
    assert (status, pages, imported) == ("complete", 3, 4)
    assert _corpus_size() == 4


def test_a_paused_run_waits_until_github_says_the_limit_lifts(monkeypatch):
    later = datetime.now(UTC) + timedelta(minutes=30)
    fake = FakeGitHub(limited=(PAGE_2,), reset_at=later)
    _run(fake, monkeypatch)
    fake.requested.clear()

    status, _, _, message = _run(fake, monkeypatch)

    assert fake.requested == []
    assert status == "paused"
    assert "Waiting for GitHub's rate limit" in message


def test_a_completed_import_starts_again_from_page_one(monkeypatch):
    """A later run picks up issues opened since, updating the rest."""
    fake = FakeGitHub()
    _run(fake, monkeypatch)
    fake.requested.clear()

    with TestingSessionLocal() as db:
        monkeypatch.setattr(github, "_get_page", fake)
        state = sync.run_sync(db, REPO)
        updated = state.updated

    assert fake.requested[0] == sync.first_page_url(REPO)
    assert updated == 4
    assert _corpus_size() == 4


def test_any_other_failure_is_recorded_and_resumable(monkeypatch):
    def broken(url: str, token: str | None):
        if url == PAGE_2:
            raise github.GitHubFetchError("GitHub returned HTTP 500")
        return PAGES[url]

    monkeypatch.setattr(github, "_get_page", broken)
    with TestingSessionLocal() as db:
        state = sync.run_sync(db, REPO)
        result = (state.status, state.next_url, state.message)

    assert result[0] == "failed"
    assert result[1] == PAGE_2
    assert "HTTP 500" in result[2]


def test_only_one_import_runs_at_a_time(monkeypatch):
    monkeypatch.setattr(github, "_get_page", FakeGitHub())
    sync._running.acquire()
    try:
        with TestingSessionLocal() as db, pytest.raises(sync.SyncBusyError):
            sync.run_sync(db, REPO)
    finally:
        sync._running.release()


def test_a_rate_limit_reply_carries_when_it_lifts():
    headers = {"x-ratelimit-reset": "1893456000"}

    reset = github._reset_time(headers)

    assert reset == datetime(2030, 1, 1, tzinfo=UTC)


class TestSchedule:
    def test_an_interval_of_zero_switches_the_schedule_off(self):
        assert scheduler.start(TestingSessionLocal) is None

    def test_a_scheduled_run_without_a_repository_does_nothing(self, monkeypatch):
        fake = FakeGitHub()
        monkeypatch.setattr(github, "_get_page", fake)

        scheduler.run_once(TestingSessionLocal)

        assert fake.requested == []

    def test_a_scheduled_run_imports_the_configured_repository(self, monkeypatch):
        """US-28: imported automatically, with no one starting it."""
        fake = FakeGitHub()
        monkeypatch.setattr(github, "_get_page", fake)
        with TestingSessionLocal() as db:
            sync.set_repository(db, REPO, None)

        scheduler.run_once(TestingSessionLocal)

        assert _corpus_size() == 4

    def test_a_scheduled_run_never_raises(self, monkeypatch):
        def explode(url: str, token: str | None):
            raise RuntimeError("unexpected")

        monkeypatch.setattr(github, "_get_page", explode)
        with TestingSessionLocal() as db:
            sync.set_repository(db, REPO, None)

        scheduler.run_once(TestingSessionLocal)
