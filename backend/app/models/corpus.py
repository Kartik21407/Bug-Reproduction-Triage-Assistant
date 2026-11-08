"""SQLAlchemy models for duplicate detection (`docs/design.md` section 6.4):
the shared corpus of public issues, one embedding per report, and the
ranked duplicate candidates found for a report.

The corpus is shared and read-only to users (ADR-010): only the import
command writes to it. A report's own embedding is what lets a user's past
reports be compared as well, which ADR-010 also requires.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.types import Embedding

if TYPE_CHECKING:
    from app.models.core import BugReport


class CorpusIssue(Base):
    """One existing issue imported into the shared corpus (US-19). Its
    embedding is computed once, at import time (criterion 3), never per
    search."""

    __tablename__ = "corpus_issues"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # The `id` column of the imported file. Re-importing the same id updates
    # the row rather than adding a second copy of the issue.
    external_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Embedding(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ReportEmbedding(Base):
    """The embedding of one report's text, refreshed each time a duplicate
    search runs for it, so the report can in turn be found as a candidate
    for its owner's later reports."""

    __tablename__ = "report_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bug_reports.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    embedding: Mapped[list[float]] = mapped_column(Embedding(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    report: Mapped["BugReport"] = relationship(back_populates="embedding")


class DuplicateCandidate(Base):
    """One ranked candidate for one report (US-20): either a corpus issue or
    another of the same user's reports, never both. Holds the similarity
    score and its label, nothing that says the two are duplicates; only a
    person decides that (DR-05)."""

    __tablename__ = "duplicate_candidates"
    __table_args__ = (
        CheckConstraint(
            "(corpus_issue_id IS NULL) <> (candidate_report_id IS NULL)",
            name="ck_duplicate_candidates_one_source",
        ),
        CheckConstraint(
            "label IN ('Likely duplicate','Possible duplicate')",
            name="ck_duplicate_candidates_label_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bug_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    corpus_issue_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("corpus_issues.id", ondelete="CASCADE"), nullable=True
    )
    candidate_report_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("bug_reports.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # 1 is the most similar. Kept so the order survives a read-back exactly.
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    label: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    report: Mapped["BugReport"] = relationship(
        back_populates="duplicate_candidates", foreign_keys=[report_id]
    )
    corpus_issue: Mapped["CorpusIssue | None"] = relationship()
    candidate_report: Mapped["BugReport | None"] = relationship(
        back_populates="cited_as_candidate", foreign_keys=[candidate_report_id]
    )
