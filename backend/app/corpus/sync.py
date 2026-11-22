"""Keeps the corpus up to date with one repository's open issues (US-28).

The issues are fetched through GitHub's API a page at a time, following
its `Link` headers (criterion 1), and each page is imported and committed
before the next is asked for. Where the run has got to is saved in
`corpus_sync_states` after every page, so when GitHub's rate limit stops a
run, nothing already fetched is lost and the next run starts from the page
that was refused, not from the beginning (criterion 2).

Runs on a schedule (`app/corpus/scheduler.py`), from the admin page, or
from the command line; only one runs at a time.
"""

import re
import threading
from datetime import UTC, datetime
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.corpus import github
from app.corpus.embedding import EmbeddingUnavailableError
from app.corpus.importer import import_rows
from app.models.settings import AppSetting, CorpusSyncState

REPOSITORY_KEY = "corpus_sync_repository"
_REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_RESUMABLE = ("paused", "failed")

_running = threading.Lock()


class SyncBusyError(RuntimeError):
    """Another import is already running."""


class RepositoryError(ValueError):
    """A repository name that is not owner/name."""


def check_repository(repository: str) -> str:
    repository = repository.strip()
    if not _REPOSITORY_PATTERN.match(repository):
        raise RepositoryError("Enter the repository as owner/name, for example nextcloud/server.")
    return repository


def configured_repository(db: Session) -> str | None:
    """The administrator's choice when there is one, else the environment's
    `CORPUS_SYNC_REPOSITORY`, else None (no automatic import)."""
    row = db.get(AppSetting, REPOSITORY_KEY)
    if row is not None:
        return row.value or None
    return get_settings().corpus_sync_repository.strip() or None


def set_repository(db: Session, repository: str | None, user_id: object) -> str | None:
    """Stores the repository to import from, or an empty value to switch the
    automatic import off. Commits."""
    value = check_repository(repository) if repository else ""
    row = db.get(AppSetting, REPOSITORY_KEY)
    if row is None:
        db.add(AppSetting(key=REPOSITORY_KEY, value=value, updated_by_id=user_id))
    else:
        row.value = value
        row.updated_by_id = user_id
    db.commit()
    return value or None


def first_page_url(repository: str) -> str:
    params = urlencode({"state": "open", "per_page": "100"})
    return f"https://api.github.com/repos/{repository}/issues?{params}"


def read_state(db: Session, repository: str) -> CorpusSyncState | None:
    return db.execute(
        select(CorpusSyncState).where(CorpusSyncState.repository == repository)
    ).scalar_one_or_none()


def is_running() -> bool:
    return _running.locked()


def run_sync(db: Session, repository: str, token: str | None = None) -> CorpusSyncState:
    """Imports the repository's open issues, resuming a paused or failed
    run from its saved page. Raises SyncBusyError if a run is already in
    progress. Returns the saved state, whatever the outcome."""
    if not _running.acquire(blocking=False):
        raise SyncBusyError("An import is already running.")
    try:
        return _run(db, check_repository(repository), token)
    finally:
        _running.release()


def _run(db: Session, repository: str, token: str | None) -> CorpusSyncState:
    now = datetime.now(UTC)
    state = read_state(db, repository)
    if state is None:
        state = CorpusSyncState(repository=repository, status="idle")
        db.add(state)

    if state.status == "paused" and state.resume_after and _aware(state.resume_after) > now:
        state.message = (
            f"Waiting for GitHub's rate limit to lift at "
            f"{_aware(state.resume_after):%H:%M} UTC; the import resumes from page "
            f"{state.pages_done + 1} then."
        )
        db.commit()
        return state

    if not (state.status in _RESUMABLE and state.next_url):
        state.next_url = first_page_url(repository)
        state.pages_done = state.imported = state.updated = state.skipped = 0
        state.started_at = now
    state.status = "running"
    state.message = None
    state.resume_after = None
    state.finished_at = None
    db.commit()

    try:
        while state.next_url:
            issues, next_url = github._get_page(state.next_url, token)
            rows = [row for issue in issues if (row := github.issue_to_row(repository, issue))]
            summary = import_rows(db, rows)
            state.imported += summary.imported
            state.updated += summary.updated
            state.skipped += len(summary.skipped)
            state.pages_done += 1
            state.next_url = next_url
            db.commit()
    except github.GitHubRateLimitError as error:
        db.rollback()
        state.status = "paused"
        state.resume_after = error.reset_at
        state.message = (
            f"GitHub's rate limit stopped the import after {state.pages_done} pages. "
            f"Nothing was lost; it resumes from page {state.pages_done + 1}."
        )
        db.commit()
        return state
    except (github.GitHubFetchError, EmbeddingUnavailableError) as error:
        db.rollback()
        state.status = "failed"
        state.message = f"{error} The next run resumes from page {state.pages_done + 1}."
        db.commit()
        return state

    state.status = "complete"
    state.finished_at = datetime.now(UTC)
    state.message = (
        f"Imported {state.imported} new and updated {state.updated} issues "
        f"from {state.pages_done} pages; skipped {state.skipped}."
    )
    db.commit()
    return state


def _aware(moment: datetime) -> datetime:
    """SQLite returns stored times without a zone; they are UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)
