"""create users and bug_reports

Generated with autogenerate against an empty database, then reviewed and
cleaned up by hand: the auto-generated file used a literal server default
tied to the dialect it was generated against, which is replaced here with
sa.func.now() so it renders correctly on both PostgreSQL and SQLite.

This is the first migration. It creates the two tables Sprint 1 defines, per
docs/design.md section 6.

Revision ID: 961be5534e8f
Revises:
Create Date: 2026-09-18 17:00:51.900336
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "961be5534e8f"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "bug_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("logs", sa.Text(), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("severity", sa.String(length=8), nullable=True),
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
        sa.CheckConstraint(
            "severity IS NULL OR severity IN ('Critical','High','Medium','Low')",
            name="ck_bug_reports_severity_valid",
        ),
        sa.CheckConstraint(
            "state IN ('Draft','Analysed','Reviewed','Exported','Submitted')",
            name="ck_bug_reports_state_valid",
        ),
        sa.CheckConstraint(
            "length(original_text) >= 20 AND length(original_text) <= 10000",
            name="ck_bug_reports_original_text_length",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bug_reports_user_id"), "bug_reports", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_bug_reports_user_id"), table_name="bug_reports")
    op.drop_table("bug_reports")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
