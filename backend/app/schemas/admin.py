"""Request and response shapes for the administrator endpoints
(`docs/design.md` section 7.8, US-03, US-28, US-31)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AdminUserRead(BaseModel):
    """One account as an administrator sees it. Never the password hash."""

    id: UUID
    email: str
    is_admin: bool
    is_active: bool
    report_count: int
    created_at: datetime


class UserActiveUpdate(BaseModel):
    """Deactivate (`false`) or reactivate (`true`) an account (US-03)."""

    is_active: bool


class ThresholdsUpdate(BaseModel):
    """US-31 criterion 1: two numbers, validated together."""

    likely: float
    possible: float


class ThresholdsRead(BaseModel):
    """The thresholds in force, the environment's defaults, and whether an
    administrator has changed them."""

    likely: float
    possible: float
    default_likely: float
    default_possible: float
    customised: bool


class CorpusSyncStateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    repository: str
    status: str
    pages_done: int
    imported: int
    updated: int
    skipped: int
    message: str | None
    resume_after: datetime | None
    started_at: datetime | None
    finished_at: datetime | None


class CorpusSyncRead(BaseModel):
    """The automatic import's settings and how its latest run went (US-28).
    `repository` is None when no repository is set, which switches the
    automatic import off."""

    repository: str | None
    interval_minutes: int
    running: bool
    state: CorpusSyncStateRead | None


class CorpusSyncUpdate(BaseModel):
    """owner/name, or null or empty to switch the automatic import off."""

    repository: str | None
