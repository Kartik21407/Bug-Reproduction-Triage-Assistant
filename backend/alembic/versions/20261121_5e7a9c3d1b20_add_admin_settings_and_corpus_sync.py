"""add admin, settings and corpus sync

Written by hand against app/models/core.py and app/models/settings.py.
Sprint 5:

- `is_admin` and `is_active` on users (US-03, US-31). Existing accounts
  become active, non-administrator accounts.
- app_settings, administrator-set values such as the duplicate thresholds
  (US-31).
- corpus_sync_states, the progress of the automatic corpus import (US-28).

Revision ID: 5e7a9c3d1b20
Revises: 8b1d5f3c2a64
Create Date: 2026-11-21 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5e7a9c3d1b20"
down_revision: str | None = "8b1d5f3c2a64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())
        )

    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "updated_by_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        *_timestamps(),
    )

    op.create_table(
        "corpus_sync_states",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("repository", sa.String(length=200), nullable=False, unique=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("next_url", sa.Text(), nullable=True),
        sa.Column("pages_done", sa.Integer(), nullable=False),
        sa.Column("imported", sa.Integer(), nullable=False),
        sa.Column("updated", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("resume_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('idle','running','paused','complete','failed')",
            name="ck_corpus_sync_states_status_valid",
        ),
    )


def downgrade() -> None:
    op.drop_table("corpus_sync_states")
    op.drop_table("app_settings")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("is_active")
        batch.drop_column("is_admin")
