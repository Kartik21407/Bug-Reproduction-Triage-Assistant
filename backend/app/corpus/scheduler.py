"""Runs the corpus import on a schedule, so the corpus follows the
repository's open issues without anyone starting it (US-28).

A single background thread wakes every `CORPUS_SYNC_INTERVAL_MINUTES` and
runs `sync.run_sync` for the configured repository, if there is one. An
interval of 0 switches the schedule off; the test suite does exactly that.
"""

import logging
import threading
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.config import get_settings
from app.corpus import sync

logger = logging.getLogger(__name__)

_FIRST_RUN_DELAY_SECONDS = 60


def start(session_factory: Callable[[], Session]) -> threading.Event | None:
    """Starts the schedule and returns the event that stops it, or None
    when the schedule is switched off."""
    minutes = get_settings().corpus_sync_interval_minutes
    if minutes <= 0:
        return None
    stop = threading.Event()
    thread = threading.Thread(
        target=_loop,
        args=(stop, session_factory, minutes * 60),
        name="corpus-sync",
        daemon=True,
    )
    thread.start()
    return stop


def _loop(stop: threading.Event, session_factory: Callable[[], Session], seconds: int) -> None:
    delay = _FIRST_RUN_DELAY_SECONDS
    while not stop.wait(delay):
        run_once(session_factory)
        delay = seconds


def run_once(session_factory: Callable[[], Session]) -> None:
    """One scheduled run. Never raises: a failure is recorded in the sync
    state where it can be, and logged otherwise, and the next run tries
    again."""
    token = get_settings().corpus_sync_token or None
    try:
        with session_factory() as db:
            repository = sync.configured_repository(db)
            if repository:
                sync.run_sync(db, repository, token)
    except sync.SyncBusyError:
        logger.info("Skipped a scheduled corpus import: one is already running")
    except Exception:
        logger.exception("Scheduled corpus import failed")
