"""Routes for creating, listing, reading, editing and deleting a user's own
bug reports (US-02, US-04, US-05, US-06, US-07)."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select

from app.deps import CurrentUser, DbSession
from app.models.core import BugReport
from app.schemas.core import ReportCreate, ReportListResponse, ReportRead, ReportUpdate

router = APIRouter(prefix="/reports", tags=["reports"])

Severity = Literal["Critical", "High", "Medium", "Low"]
ReportState = Literal["Draft", "Analysed", "Reviewed", "Exported", "Submitted"]


@router.post("", response_model=ReportRead, status_code=status.HTTP_201_CREATED)
def create_report(body: ReportCreate, current_user: CurrentUser, db: DbSession) -> BugReport:
    """Creates a report owned by the current user. The original text is
    stored exactly as submitted, with a timestamp (US-04 criterion 3)."""
    report = BugReport(user_id=current_user.id, original_text=body.original_text, logs=body.logs)
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def _escape_like(value: str) -> str:
    """Escapes the characters LIKE treats specially, so a search containing
    a literal % or _ matches only that literal text."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("", response_model=ReportListResponse)
def list_reports(
    current_user: CurrentUser,
    db: DbSession,
    search: str | None = Query(default=None),
    severity: Severity | None = Query(default=None),
    state: ReportState | None = Query(default=None),
) -> ReportListResponse:
    """Returns the current user's own reports, newest first (US-02
    criterion 1, US-06 criterion 1).

    Filters by severity and state (US-06 criterion 2). Both columns are
    unset for every report this sprint, since triage arrives in Sprint 3, so
    a severity filter currently matches nothing and a state filter other
    than Draft returns an empty list; that is correct, not a bug.

    Keyword search is a case insensitive match over title and original_text
    (US-06 criterion 3). Sort order, limit and offset from the full contract
    in docs/design.md section 7.2 are not implemented; nothing in this story
    needs them.
    """
    query = select(BugReport).where(BugReport.user_id == current_user.id)

    if state is not None:
        query = query.where(BugReport.state == state)

    if severity is not None:
        query = query.where(BugReport.severity == severity)

    if search is not None and search.strip():
        pattern = f"%{_escape_like(search.strip().lower())}%"
        query = query.where(
            or_(
                func.lower(func.coalesce(BugReport.title, "")).like(pattern, escape="\\"),
                func.lower(BugReport.original_text).like(pattern, escape="\\"),
            )
        )

    query = query.order_by(BugReport.created_at.desc())

    reports = db.execute(query).scalars().all()
    return ReportListResponse(items=list(reports), total=len(reports))


def _get_owned_report_or_404(db: DbSession, current_user, report_id: UUID) -> BugReport:
    report = db.execute(
        select(BugReport).where(BugReport.id == report_id, BugReport.user_id == current_user.id)
    ).scalar_one_or_none()
    if report is None:
        # Same response whether the id does not exist at all or belongs to
        # another user (NFR-15, US-02 criterion 2). A 403 would confirm the
        # id exists, which is exactly the leak this requirement prevents.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


@router.get("/{report_id}", response_model=ReportRead)
def read_report(report_id: UUID, current_user: CurrentUser, db: DbSession) -> BugReport:
    """Returns one report. 404 for an unknown id or one belonging to another
    user (NFR-15, US-02 criterion 2)."""
    return _get_owned_report_or_404(db, current_user, report_id)


@router.patch("/{report_id}", response_model=ReportRead)
def update_report(
    report_id: UUID, body: ReportUpdate, current_user: CurrentUser, db: DbSession
) -> BugReport:
    """Edits a report's original text and/or logs. Only fields present in
    the request body are changed. Editing the original text returns the
    report to Draft, so analysis can be run again once it exists
    (US-07 criterion 1). 404 rules match every other report endpoint."""
    report = _get_owned_report_or_404(db, current_user, report_id)

    changes = body.model_dump(exclude_unset=True)
    if "original_text" in changes:
        report.original_text = changes["original_text"]
        report.state = "Draft"
    if "logs" in changes:
        report.logs = changes["logs"]

    db.commit()
    db.refresh(report)
    return report


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(report_id: UUID, current_user: CurrentUser, db: DbSession) -> None:
    """Deletes a report. Everything linked to it is removed too, through
    ON DELETE CASCADE on the foreign key (US-07 criterion 2). No linked
    analysis data exists yet this sprint, since the tables that will
    reference a report arrive in a later sprint; the cascade is what
    makes this criterion hold once they do. 404 rules match every other
    report endpoint. Confirmation is a frontend responsibility; this
    endpoint deletes unconditionally once called."""
    report = _get_owned_report_or_404(db, current_user, report_id)
    db.delete(report)
    db.commit()
