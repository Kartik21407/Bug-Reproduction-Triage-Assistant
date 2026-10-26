"""SQLAlchemy models for the Sprint 2 analysis tables: one row per
extracted field, one row per environment detail, one row per follow-up
question, all scoped to a report (`docs/design.md` section 6.4).

These tables store what `app.analysis` already computes; they do not
decide a label or filter a question themselves. `field_name` values match
the field names `app.analysis.schema.ExtractionResult` and
`app.analysis.questions.ESSENTIAL_FIELDS` use, so the two stay in sync by
construction rather than by convention alone.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
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

if TYPE_CHECKING:
    from app.models.core import BugReport

# Matches app.analysis.schema.Label exactly (FR-09, FR-27). Repeated here as
# a literal, not imported, since a database CHECK constraint cannot import a
# Python enum; both are ADR-014's four labels, and both must change together.
_LABEL_CONSTRAINT = "label IN ('Explicit','Inferred','Unverified','Missing')"


class ExtractedField(Base):
    """One extracted field for one report. A scalar field (title, summary,
    expected_behaviour, actual_behaviour, frequency) has exactly one row;
    a list field (steps, error_messages) has one row per entry, ordered by
    `position` (FR-27, FR-33)."""

    __tablename__ = "extracted_fields"
    __table_args__ = (CheckConstraint(_LABEL_CONSTRAINT, name="ck_extracted_fields_label_valid"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bug_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_name: Mapped[str] = mapped_column(String(32), nullable=False)
    # Null for a scalar field. 0-based, in extraction order, for a list
    # field (steps, error_messages), so the original order is preserved
    # (US-09 criterion 1).
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    label: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    report: Mapped["BugReport"] = relationship(back_populates="extracted_fields")


class EnvironmentDetail(Base):
    """One environment name and value pair for one report, open-ended
    rather than a fixed set of columns (FR-07, ADR-015)."""

    __tablename__ = "environment_details"
    __table_args__ = (
        CheckConstraint(_LABEL_CONSTRAINT, name="ck_environment_details_label_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bug_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    source_quote: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    report: Mapped["BugReport"] = relationship(back_populates="environment_details")


class FollowUpQuestion(Base):
    """One follow-up question shown to the user for one report: the
    model's stated reason, whether code kept or generated it, and the
    answer once given (FR-32, ADR-016)."""

    __tablename__ = "follow_up_questions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bug_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_name: Mapped[str] = mapped_column(String(32), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    # False for a question code generated itself because an essential field
    # was missing and the model did not propose one (US-14 criterion 3).
    model_proposed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # Null until the user answers. Answering writes the value straight into
    # the matching extracted_fields row too; this column is the record of
    # having been asked and answered, not the field's own value.
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    report: Mapped["BugReport"] = relationship(back_populates="follow_up_questions")


# BugReport itself declares the other side of these three relationships
# (models/core.py), by forward-referenced class name rather than an import
# here, since core.py must not depend on this Sprint 2 module.
