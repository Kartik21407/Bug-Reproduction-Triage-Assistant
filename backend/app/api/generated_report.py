"""The fixed-template report (US-23, FR-19): reading it, editing any field
and resetting it to the suggested version (US-24, FR-20), Markdown export
(US-25, FR-21), and marking it reviewed (DR-10)."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from app.analysis.completeness import compute_completeness
from app.analysis.verification import normalise_environment_name
from app.api.duplicates import read_candidates
from app.api.reports import get_owned_report_or_404
from app.api.triage import ensure_triage
from app.deps import CurrentUser, DbSession
from app.models.core import BugReport
from app.report import store
from app.report.markdown import render_markdown
from app.report.template import CandidateEntry, GeneratedReport, TriageEntry, assemble_report
from app.schemas.core import ReportRead
from app.schemas.report import EditableField, MarkdownRead, ReportEditRequest
from app.triage.service import refresh_triage

router = APIRouter(prefix="/reports", tags=["report"])

_FIELD_NAMES = {
    "expected_behaviour": "expected behaviour",
    "actual_behaviour": "actual behaviour",
    "steps": "steps to reproduce",
    "environment": "environment",
    "frequency": "frequency",
}


@router.get("/{report_id}/report", response_model=GeneratedReport)
def read_generated_report(
    report_id: UUID, current_user: CurrentUser, db: DbSession
) -> GeneratedReport:
    """Assembles the template from what is stored now: the fields with every
    correction a person made, the triage values in force, and the
    candidates of the most recent duplicate search. Runs no search and
    calls no model, so it always returns quickly (NFR-19). 404 rules match
    every other report endpoint (NFR-15)."""
    report = get_owned_report_or_404(db, current_user, report_id)
    return assemble(db, report)


@router.patch("/{report_id}/report", response_model=GeneratedReport)
def edit_generated_report(
    report_id: UUID, body: ReportEditRequest, current_user: CurrentUser, db: DbSession
) -> GeneratedReport:
    """Saves a person's own version of one field (US-24 criteria 1 and 2).
    It is kept beside the suggested version, never over it, so it survives
    re-analysis (ADR-011) and "Reset to suggested" can bring the suggestion
    back. Severity, priority, category and reproducibility are edited
    through `PATCH /triage` instead."""
    report = get_owned_report_or_404(db, current_user, report_id)
    if body.field in store.LIST_FIELDS:
        store.set_list(report, body.field, body.items or [])
    elif body.field == "environment":
        store.set_environment(
            report,
            [(normalise_environment_name(e.name), e.value) for e in body.environment or []],
        )
    else:
        store.set_scalar(report, body.field, body.text)
    refresh_triage(report, store.read_extraction(report))
    db.commit()
    return assemble(db, report)


@router.delete("/{report_id}/report/fields/{field}", response_model=GeneratedReport)
def reset_generated_report_field(
    report_id: UUID, field: EditableField, current_user: CurrentUser, db: DbSession
) -> GeneratedReport:
    """ "Reset to suggested" (US-24 criterion 3): removes the person's own
    version of the field, so the suggested one shows again."""
    report = get_owned_report_or_404(db, current_user, report_id)
    store.reset_field(report, field)
    refresh_triage(report, store.read_extraction(report))
    db.commit()
    return assemble(db, report)


@router.get("/{report_id}/markdown", response_model=MarkdownRead)
def read_markdown(report_id: UUID, current_user: CurrentUser, db: DbSession) -> MarkdownRead:
    """The report as GitHub-flavoured Markdown (US-25), with warnings for
    unanswered questions and missing essential fields (US-14 criterion 6).
    Reading it changes nothing; `POST /export` records that it was copied."""
    report = get_owned_report_or_404(db, current_user, report_id)
    return MarkdownRead(markdown=render_markdown(assemble(db, report)), warnings=warnings(report))


@router.post("/{report_id}/export", response_model=ReportRead)
def mark_exported(report_id: UUID, current_user: CurrentUser, db: DbSession) -> BugReport:
    """Records that the report was copied out as Markdown: Exported (DR-10).
    A report already filed on GitHub stays Submitted."""
    report = get_owned_report_or_404(db, current_user, report_id)
    return _move_state(db, report, "Exported")


@router.post("/{report_id}/review", response_model=ReportRead)
def mark_reviewed(report_id: UUID, current_user: CurrentUser, db: DbSession) -> BugReport:
    """A person has checked the generated report and accepts it: Reviewed
    (DR-10). A report already exported or filed keeps that later state."""
    report = get_owned_report_or_404(db, current_user, report_id)
    return _move_state(db, report, "Reviewed")


_ORDER = ("Draft", "Analysed", "Reviewed", "Exported", "Submitted")


def _move_state(
    db: Session, report: BugReport, target: Literal["Reviewed", "Exported"]
) -> BugReport:
    """Moves a report forward through the lifecycle, never backward: only
    editing the original text returns it to Draft (US-07 criterion 1). A
    Draft report has nothing to review or export yet."""
    if report.state == "Draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Analyse the report first")
    if _ORDER.index(report.state) < _ORDER.index(target):
        report.state = target
        db.commit()
        db.refresh(report)
    return report


def assemble(db: Session, report: BugReport) -> GeneratedReport:
    """Shared with the GitHub router."""
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
            CandidateEntry(
                title=c.title,
                url=c.url,
                score=c.score,
                label=c.label,
                decision=c.decision,
                own_report=c.source == "report",
            )
            for c in duplicates.candidates
        ]
        if duplicates.searched
        else None
    )
    return assemble_report(
        store.read_extraction(report),
        triage,
        candidates,
        report.logs,
        note=store.read_note(report),
        edited_fields=store.edited_fields(report),
    )


def warnings(report: BugReport) -> list[str]:
    """What a reader of the exported report should know is incomplete. Also
    shown before filing on GitHub."""
    result = []
    unanswered = sum(1 for q in report.follow_up_questions if q.answer is None)
    if unanswered:
        plural = "question was" if unanswered == 1 else "questions were"
        result.append(f"{unanswered} follow-up {plural} not answered")
    missing = compute_completeness(store.read_extraction(report)).missing_fields
    if missing:
        names = ", ".join(_FIELD_NAMES.get(name, name) for name in missing)
        result.append(f"Still missing: {names}")
    return result
