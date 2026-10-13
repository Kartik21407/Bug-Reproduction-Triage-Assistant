"""SQLAlchemy models for the Sprint 1 tables: User and BugReport.

Primary keys are UUIDs generated in Python (uuid.uuid4 as the column default)
rather than by a PostgreSQL server default such as gen_random_uuid(). This
keeps the schema identical on PostgreSQL and on the SQLite database the test
suite runs against, and needs no server-side extension. See ADR-013 in
docs/adr.md.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    # Salted argon2 hash. Never a plaintext password (NFR-03).
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    reports: Mapped[list["BugReport"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="reports")
