"""create triage and duplicate tables

Written by hand against app/models/triage.py and app/models/corpus.py,
following the same shape as the first two migrations. Creates the Sprint 3
tables: triage_values, triage_overrides, corpus_issues, report_embeddings
and duplicate_candidates, per docs/design.md section 6.4.

On PostgreSQL the embedding columns are pgvector vector(384) and the
extension is enabled first; on any other database (the SQLite test
database) they are JSON, matching app.models.types.Embedding.

Revision ID: 4c8e2a91d7b3
Revises: 197e526330ff
Create Date: 2026-10-22 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "4c8e2a91d7b3"
down_revision: str | None = "197e526330ff"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Must match app.models.types.EMBEDDING_DIMENSIONS (all-MiniLM-L6-v2).
_EMBEDDING_DIMENSIONS = 384
_FIELD_CHECK = "field_name IN ('severity','priority','category','reproducibility')"


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _embedding_type() -> sa.types.TypeEngine:
    if _is_postgresql():
        return Vector(_EMBEDDING_DIMENSIONS)
    return sa.JSON()


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
    if _is_postgresql():
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "triage_values",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("field_name", sa.String(length=32), nullable=False),
        sa.Column("suggested_value", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("value", sa.String(length=32), nullable=False),
        sa.Column("overridden", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(_FIELD_CHECK, name="ck_triage_values_field_name_valid"),
        sa.UniqueConstraint("report_id", "field_name", name="uq_triage_values_report_field"),
        sa.ForeignKeyConstraint(["report_id"], ["bug_reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_triage_values_report_id"), "triage_values", ["report_id"], unique=False
    )

    op.create_table(
        "triage_overrides",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("field_name", sa.String(length=32), nullable=False),
        sa.Column("old_value", sa.String(length=32), nullable=False),
        sa.Column("new_value", sa.String(length=32), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(_FIELD_CHECK, name="ck_triage_overrides_field_name_valid"),
        sa.ForeignKeyConstraint(["report_id"], ["bug_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_triage_overrides_report_id"), "triage_overrides", ["report_id"], unique=False
    )
    op.create_index(
        op.f("ix_triage_overrides_user_id"), "triage_overrides", ["user_id"], unique=False
    )

    op.create_table(
        "corpus_issues",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("embedding", _embedding_type(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )

    op.create_table(
        "report_embeddings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("embedding", _embedding_type(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["report_id"], ["bug_reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_id"),
    )

    op.create_table(
        "duplicate_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("corpus_issue_id", sa.Uuid(), nullable=True),
        sa.Column("candidate_report_id", sa.Uuid(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("label", sa.String(length=32), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "(corpus_issue_id IS NULL) <> (candidate_report_id IS NULL)",
            name="ck_duplicate_candidates_one_source",
        ),
        sa.CheckConstraint(
            "label IN ('Likely duplicate','Possible duplicate')",
            name="ck_duplicate_candidates_label_valid",
        ),
        sa.ForeignKeyConstraint(["report_id"], ["bug_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["corpus_issue_id"], ["corpus_issues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["candidate_report_id"], ["bug_reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_duplicate_candidates_report_id"),
        "duplicate_candidates",
        ["report_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_duplicate_candidates_candidate_report_id"),
        "duplicate_candidates",
        ["candidate_report_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_duplicate_candidates_candidate_report_id"), table_name="duplicate_candidates"
    )
    op.drop_index(op.f("ix_duplicate_candidates_report_id"), table_name="duplicate_candidates")
    op.drop_table("duplicate_candidates")

    op.drop_table("report_embeddings")
    op.drop_table("corpus_issues")

    op.drop_index(op.f("ix_triage_overrides_user_id"), table_name="triage_overrides")
    op.drop_index(op.f("ix_triage_overrides_report_id"), table_name="triage_overrides")
    op.drop_table("triage_overrides")

    op.drop_index(op.f("ix_triage_values_report_id"), table_name="triage_values")
    op.drop_table("triage_values")

    # The vector extension is left installed on purpose. It holds no data of
    # its own once the tables above are gone, the pgvector image ships it
    # anyway (ADR-003), and dropping it would fail if anything else on the
    # server had started using it.
