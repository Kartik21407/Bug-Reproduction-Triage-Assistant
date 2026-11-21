"""SQLAlchemy models for the Sprint 1 tables: User and BugReport.

Primary keys are UUIDs generated in Python (uuid.uuid4 as the column default)
rather than by a PostgreSQL server default such as gen_random_uuid(). This
keeps the schema identical on PostgreSQL and on the SQLite database the test
suite runs against, and needs no server-side extension. See ADR-013 in
docs/adr.md.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    false,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.analysis import EnvironmentDetail, ExtractedField, FollowUpQuestion
    from app.models.corpus import DuplicateCandidate, DuplicateDecision, ReportEmbedding
    from app.models.github import GitHubConnection
    from app.models.triage import TriageOverride, TriageValue


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    # Salted argon2 hash. Never a plaintext password (NFR-03).
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Sprint 5 (US-03, US-31). An administrator is made by the operator
    # command `python -m app.admin`, never through the API. A deactivated
    # account keeps every report; it only cannot sign in (US-03).
    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    reports: Mapped[list["BugReport"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    # Sprint 4 (app/models/github.py), forward referenced.
    github_connection: Mapped["GitHubConnection | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )


class BugReport(Base):
    __tablename__ = "bug_reports"
    __table_args__ = (
        # Backs up the 20 to 10,000 character limit enforced in the schema
        # layer (US-04 criterion 1). length() works on both PostgreSQL and
        # SQLite.
        CheckConstraint(
            "length(original_text) >= 20 AND length(original_text) <= 10000",
            name="ck_bug_reports_original_text_length",
        ),
        CheckConstraint(
            "state IN ('Draft','Analysed','Reviewed','Exported','Submitted')",
            name="ck_bug_reports_state_valid",
        ),
        CheckConstraint(
            "severity IS NULL OR severity IN ('Critical','High','Medium','Low')",
            name="ck_bug_reports_severity_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Populated by extraction from Sprint 2. Null until then.
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    logs: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="Draft")
    # Populated by triage from Sprint 3. Null until then.
    severity: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # Sprint 4: the issue this report was filed as (US-27 criterion 5).
    github_issue_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    github_issue_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Set while an issue is being created, so a second Confirm cannot file a
    # second issue (US-27 criterion 4). Claimed with a conditional UPDATE.
    github_submitting: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="reports")
    # Sprint 2 (app/models/analysis.py). Forward-referenced by class name,
    # not imported, so this module does not depend on that one.
    extracted_fields: Mapped[list["ExtractedField"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )
    environment_details: Mapped[list["EnvironmentDetail"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )
    follow_up_questions: Mapped[list["FollowUpQuestion"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )
    # Sprint 3 (app/models/triage.py and app/models/corpus.py), forward
    # referenced the same way.
    triage_values: Mapped[list["TriageValue"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )
    triage_overrides: Mapped[list["TriageOverride"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )
    embedding: Mapped["ReportEmbedding | None"] = relationship(
        back_populates="report", cascade="all, delete-orphan", uselist=False
    )
    duplicate_candidates: Mapped[list["DuplicateCandidate"]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
        foreign_keys="DuplicateCandidate.report_id",
        order_by="DuplicateCandidate.rank",
    )
    # Rows where this report is the candidate found for another report.
    # Deleting this report removes them too, so no candidate ever points at a
    # report that no longer exists (US-07 criterion 2).
    cited_as_candidate: Mapped[list["DuplicateCandidate"]] = relationship(
        back_populates="candidate_report",
        cascade="all, delete-orphan",
        foreign_keys="DuplicateCandidate.candidate_report_id",
    )
    # Sprint 4: a person's duplicate decisions about this report's
    # candidates, and decisions elsewhere that name this report.
    duplicate_decisions: Mapped[list["DuplicateDecision"]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
        foreign_keys="DuplicateDecision.report_id",
    )
    decided_as_candidate: Mapped[list["DuplicateDecision"]] = relationship(
        back_populates="candidate_report",
        cascade="all, delete-orphan",
        foreign_keys="DuplicateDecision.candidate_report_id",
    )
