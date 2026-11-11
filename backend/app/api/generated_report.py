"""Returns the fixed-template report for one report (US-23, FR-19)."""

from uuid import UUID

from fastapi import APIRouter

from app.api.analysis import _read_extraction as read_extraction
from app.api.duplicates import read_candidates
from app.api.reports import get_owned_report_or_404
from app.api.triage import ensure_triage
from app.deps import CurrentUser, DbSession
from app.report.template import CandidateEntry, GeneratedReport, TriageEntry, assemble_report

router = APIRouter(prefix="/reports", tags=["report"])


@router.get("/{report_id}/report", response_model=GeneratedReport)
def read_generated_report(
    report_id: UUID, current_user: CurrentUser, db: DbSession
) -> GeneratedReport:
    """Assembles the template from what is stored now: the verified
    extraction, the triage values in force, and the candidates of the most
    recent duplicate search. Runs no search and calls no model, so it
    always returns quickly (NFR-19). 404 rules match every other report
    endpoint (NFR-15)."""
    report = get_owned_report_or_404(db, current_user, report_id)
    ensure_triage(db, report)

    triage = {
        row.field_name: TriageEntry(
            value=row.value,
            suggested_value=row.suggested_value,
            reason=row.reason,
            overridden=row.overridden,
        )
        for row in report.triage_values
    }
    duplicates = read_candidates(db, report)
    candidates = (
        [
            CandidateEntry(title=c.title, url=c.url, score=c.score, label=c.label)
            for c in duplicates.candidates
        ]
        if duplicates.searched
        else None
    )

    return assemble_report(read_extraction(report), triage, candidates, report.logs)
