"""SQLAlchemy models for what an administrator can change while the server
runs (Sprint 5): application settings stored as rows, and the progress of
the automatic corpus import.

A setting row overrides the default from `app/config.py`; with no row, the
environment's value applies. This is what lets the duplicate thresholds be
tuned without a code change or a restart (US-31, FR-26).
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

SYNC_STATUSES = ("idle", "running", "paused", "complete", "failed")


class AppSetting(Base):
    """One administrator-set value, keyed by name. `updated_by` records who
    set it last; it is cleared rather than blocking the delete of that
    account."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CorpusSyncState(Base):
    """Where the automatic import of one repository's open issues has got
    to (US-28). `next_url` is the page still to fetch, so a run stopped by
    GitHub's rate limit resumes from that page instead of starting over
    (criterion 2). Counts are for the current or most recent run."""

    __tablename__ = "corpus_sync_states"
    __table_args__ = (
        CheckConstraint(
            "status IN ('idle','running','paused','complete','failed')",
            name="ck_corpus_sync_states_status_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    repository: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="idle")
    next_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    pages_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
