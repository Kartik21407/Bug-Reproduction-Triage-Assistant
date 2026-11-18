"""add corrections, duplicate decisions and github

Written by hand against app/models/analysis.py, app/models/corpus.py,
app/models/github.py and app/models/core.py. Sprint 4:

- `source` on extracted_fields and environment_details, and `removed` on
  environment_details, so a person's corrections survive re-analysis
  (ADR-011, ADR-027). Existing rows become "model", which is what they are.
- duplicate_decisions (US-21).
- github_connections (US-26), and the issue columns on bug_reports (US-27).

Columns with CHECK constraints are added in batch mode, so the same
migration works on SQLite, which cannot add a constraint to an existing
table in place.

Revision ID: 8b1d5f3c2a64
Revises: 4c8e2a91d7b3
Create Date: 2026-11-07 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8b1d5f3c2a64"
down_revision: str | None = "4c8e2a91d7b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOURCE_CHECK = "source IN ('model','user')"


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    with op.batch_alter_table("extracted_fields") as batch:
        batch.add_column(
            sa.Column("source", sa.String(length=8), nullable=False, server_default="model")
        )
        batch.create_check_constraint("ck_extracted_fields_source_valid", _SOURCE_CHECK)

    with op.batch_alter_table("environment_details") as batch:
        batch.add_column(
            sa.Column("source", sa.String(length=8), nullable=False, server_default="model")
        )
        batch.add_column(
            sa.Column("removed", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.create_check_constraint("ck_environment_details_source_valid", _SOURCE_CHECK)

    with op.batch_alter_table("bug_reports") as batch:
        batch.add_column(sa.Column("github_issue_url", sa.Text(), nullable=True))
        batch.add_column(sa.Column("github_issue_number", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column(
                "github_submitting", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )

    op.create_table(
        "duplicate_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("corpus_issue_id", sa.Uuid(), nullable=True),
        sa.Column("candidate_report_id", sa.Uuid(), nullable=True),
        sa.Column("decision", sa.String(length=16), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "(corpus_issue_id IS NULL) <> (candidate_report_id IS NULL)",
            name="ck_duplicate_decisions_one_source",
        ),
        sa.CheckConstraint(
            "decision IN ('duplicate','not_duplicate')",
            name="ck_duplicate_decisions_decision_valid",
        ),
        sa.ForeignKeyConstraint(["report_id"], ["bug_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["corpus_issue_id"], ["corpus_issues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["candidate_report_id"], ["bug_reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_duplicate_decisions_report_id"),
        "duplicate_decisions",
        ["report_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_duplicate_decisions_candidate_report_id"),
        "duplicate_decisions",
        ["candidate_report_id"],
        unique=False,
    )

    op.create_table(
        "github_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("encrypted_token", sa.Text(), nullable=False),
        sa.Column("login", sa.String(length=100), nullable=False),
        sa.Column("repository", sa.String(length=200), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("github_connections")

    op.drop_index(
        op.f("ix_duplicate_decisions_candidate_report_id"), table_name="duplicate_decisions"
    )
    op.drop_index(op.f("ix_duplicate_decisions_report_id"), table_name="duplicate_decisions")
    op.drop_table("duplicate_decisions")

    with op.batch_alter_table("bug_reports") as batch:
        batch.drop_column("github_submitting")
        batch.drop_column("github_issue_number")
        batch.drop_column("github_issue_url")

    # A person's corrections ("user" rows) have no place in the older schema,
    # so they are deleted before the column that marks them is dropped.
    # Downgrading therefore loses corrections; the model rows survive.
    op.execute("DELETE FROM environment_details WHERE source = 'user'")
    with op.batch_alter_table("environment_details") as batch:
        batch.drop_constraint("ck_environment_details_source_valid", type_="check")
        batch.drop_column("removed")
        batch.drop_column("source")

    op.execute("DELETE FROM extracted_fields WHERE source = 'user'")
    with op.batch_alter_table("extracted_fields") as batch:
        batch.drop_constraint("ck_extracted_fields_source_valid", type_="check")
        batch.drop_column("source")
