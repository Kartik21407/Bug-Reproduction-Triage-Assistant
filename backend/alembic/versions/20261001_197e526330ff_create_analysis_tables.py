"""create analysis tables

Written by hand against app/models/analysis.py, following the same shape
as the first migration (no live database was available to autogenerate
against). Creates the three Sprint 2 tables: extracted_fields,
environment_details, follow_up_questions, per docs/design.md section 6.4.

Revision ID: 197e526330ff
Revises: 961be5534e8f
Create Date: 2026-10-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "197e526330ff"
down_revision: str | None = "961be5534e8f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LABEL_CHECK = "label IN ('Explicit','Inferred','Unverified','Missing')"


def upgrade() -> None:
    op.create_table(
        "extracted_fields",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("field_name", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("source_quote", sa.Text(), nullable=True),
        sa.Column("label", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(_LABEL_CHECK, name="ck_extracted_fields_label_valid"),
        sa.ForeignKeyConstraint(["report_id"], ["bug_reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_extracted_fields_report_id"), "extracted_fields", ["report_id"], unique=False
    )

    op.create_table(
        "environment_details",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("source_quote", sa.Text(), nullable=False),
        sa.Column("label", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(_LABEL_CHECK, name="ck_environment_details_label_valid"),
        sa.ForeignKeyConstraint(["report_id"], ["bug_reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_environment_details_report_id"),
        "environment_details",
        ["report_id"],
        unique=False,
    )

    op.create_table(
        "follow_up_questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("field_name", sa.String(length=32), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("model_proposed", sa.Boolean(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["report_id"], ["bug_reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_follow_up_questions_report_id"),
        "follow_up_questions",
        ["report_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_follow_up_questions_report_id"), table_name="follow_up_questions")
    op.drop_table("follow_up_questions")

    op.drop_index(op.f("ix_environment_details_report_id"), table_name="environment_details")
    op.drop_table("environment_details")

    op.drop_index(op.f("ix_extracted_fields_report_id"), table_name="extracted_fields")
    op.drop_table("extracted_fields")
