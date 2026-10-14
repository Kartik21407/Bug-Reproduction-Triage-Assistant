"""Pydantic request and response models for the auth and report endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# --- Auth (US-01) ---------------------------------------------------------


class UserCreate(BaseModel):
    """Request body for POST /api/auth/register.
    Password length is US-01 criterion 1."""

    email: EmailStr
    password: str = Field(min_length=8)


class UserLogin(BaseModel):
    """Request body for POST /api/auth/login."""

    email: EmailStr
    password: str


class UserRead(BaseModel):
    """Response body for the current user. Deliberately excludes
    password_hash (US-01 criterion 4)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    created_at: datetime


# --- Reports (US-02, US-04, US-05, US-06, US-07) --------------------------


class ReportCreate(BaseModel):
    """Request body for POST /api/reports.

    Length is checked against the stripped text so whitespace alone cannot
    satisfy the minimum (design.md section 8.4), but the value returned by
    the validator is the original, unstripped string: the original text is
    stored exactly as submitted, whitespace and line breaks included
    (US-04 criterion 3)."""

    original_text: str
    # US-05 criterion 1: optional, up to 50,000 characters, stored unmodified.
    logs: str | None = Field(default=None, max_length=50_000)

    @field_validator("original_text")
    @classmethod
    def _check_length(cls, value: str) -> str:
        length = len(value.strip())
        if length < 20 or length > 10_000:
            raise ValueError("original_text must be between 20 and 10,000 characters")
        return value


class ReportRead(BaseModel):
    """Response body for a report. user_id is deliberately not included: the
    caller can only ever see their own reports, so it carries no information
    (design.md section 7.2)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str | None
    original_text: str
    logs: str | None
    state: str
    severity: str | None
    created_at: datetime
    updated_at: datetime


class ReportListResponse(BaseModel):
    """Response body for GET /api/reports. Sorting other than newest-first
    and paging are not implemented; nothing in Sprint 1 needs them."""

    items: list[ReportRead]
    total: int


class ReportUpdate(BaseModel):
    """Request body for PATCH /api/reports/{id}. Both fields are optional;
    only a field actually present in the request body is changed, so a
    request that omits logs leaves it untouched rather than clearing it.

    Editing original_text returns the report to Draft (US-07 criterion 1,
    design.md section 5), so that analysis can be run again once it exists."""

    original_text: str | None = None
    logs: str | None = Field(default=None, max_length=50_000)

    @field_validator("original_text")
    @classmethod
    def _check_length(cls, value: str | None) -> str | None:
        if value is None:
            return value
        length = len(value.strip())
        if length < 20 or length > 10_000:
            raise ValueError("original_text must be between 20 and 10,000 characters")
        return value
