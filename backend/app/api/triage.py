"""Reads a report's triage suggestions and applies a person's override
(US-15, US-16, US-17; FR-13 to FR-15)."""

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy.orm import Session

from app.api.analysis import _read_extraction as read_extraction
from app.api.reports import get_owned_report_or_404
from app.deps import CurrentUser, DbSession
from app.models.core import BugReport
from app.schemas.triage import TriageOverrideRequest, TriageRead, TriageValueRead
from app.triage.rules import OPTIONS, TRIAGE_FIELDS
from app.triage.service import apply_override, refresh_triage

router = APIRouter(prefix="/reports", tags=["triage"])


@router.get("/{report_id}/triage", response_model=TriageRead)
def read_triage(report_id: UUID, current_user: CurrentUser, db: DbSession) -> TriageRead:
    """The four triage values with their suggestions and reasons. Analysis
    already computes them; a report that has no triage yet (never
    analysed, or analysed before triage existed) gets them computed from
    what is known now, the same deterministic way. 404 rules match every
    other report endpoint (NFR-15)."""
    report = get_owned_report_or_404(db, current_user, report_id)
    ensure_triage(db, report)
    return _to_read(report)


@router.patch("/{report_id}/triage", response_model=TriageRead)
def override_triage(
    report_id: UUID, body: TriageOverrideRequest, current_user: CurrentUser, db: DbSession
) -> TriageRead:
    """Sets one triage value to what the person chose. The change is saved,
    flagged as overridden, and recorded with who made it (US-15 criterion
    4, US-16 criterion 3, FR-15). A value outside the field's own options
    is a 422."""
    report = get_owned_report_or_404(db, current_user, report_id)
    ensure_triage(db, report)
    apply_override(report, current_user, body.field, body.value)
    db.commit()
    return _to_read(report)


def ensure_triage(db: Session, report: BugReport) -> None:
    """Computes and stores triage for a report that has none yet. Shared
    with the generated report router."""
    if not report.triage_values:
        refresh_triage(report, read_extraction(report))
        db.commit()


def _to_read(report: BugReport) -> TriageRead:
    rows = {row.field_name: row for row in report.triage_values}
    values = {
        field_name: TriageValueRead(
            value=rows[field_name].value,
            suggested_value=rows[field_name].suggested_value,
            reason=rows[field_name].reason,
            overridden=rows[field_name].overridden,
            options=list(OPTIONS[field_name]),
        )
        for field_name in TRIAGE_FIELDS
    }
    return TriageRead(**values)
