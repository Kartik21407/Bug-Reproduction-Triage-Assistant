"""SQLAlchemy models for triage (`docs/design.md` section 6.4): one row per
triage field per report, and one row per override a user makes.

These tables store what `app.triage.rules` suggests and what the user
decides; they never compute a suggestion themselves.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.core import BugReport, User

# Matches app.triage.rules.TRIAGE_FIELDS. Repeated as a literal for the same
# reason analysis.py repeats its label constraint: a CHECK cannot import.
_FIELD_CONSTRAINT = "field_name IN ('severity','priority','category','reproducibility')"


class TriageValue(Base):
    """One triage field for one report: the rule-based suggestion and the
    reason for it, the value currently in force, and whether a person
    changed it (US-15 criterion 4)."""

    __tablename__ = "triage_values"
    __table_args__ = (
        CheckConstraint(_FIELD_CONSTRAINT, name="ck_triage_values_field_name_valid"),
        UniqueConstraint("report_id", "field_name", name="uq_triage_values_report_field"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bug_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_name: Mapped[str] = mapped_column(String(32), nullable=False)
    suggested_value: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str] = mapped_column(String(32), nullable=False)
    # True when the value in force differs from the suggestion because a
    # person chose it. A refreshed suggestion never overwrites such a value.
    overridden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    report: Mapped["BugReport"] = relationship(back_populates="triage_values")


class TriageOverride(Base):
    """A record of one change a person made to a triage value: who, which
    field, from what, to what, and when (FR-15). Rows are only ever added."""

    __tablename__ = "triage_overrides"
    __table_args__ = (
        CheckConstraint(_FIELD_CONSTRAINT, name="ck_triage_overrides_field_name_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bug_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_name: Mapped[str] = mapped_column(String(32), nullable=False)
    old_value: Mapped[str] = mapped_column(String(32), nullable=False)
    new_value: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    report: Mapped["BugReport"] = relationship(back_populates="triage_overrides")
    user: Mapped["User"] = relationship()
