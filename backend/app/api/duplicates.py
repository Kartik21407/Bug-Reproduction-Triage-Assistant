"""Lists a report's duplicate candidates, runs a fresh search (US-20,
FR-17), and records a person's decision on a candidate (US-21, FR-18)."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from app.api.reports import get_owned_report_or_404
from app.corpus.embedding import EmbeddingUnavailableError
from app.corpus.search import compared_count, find_duplicates
from app.deps import CurrentUser, DbSession
from app.models.core import BugReport
from app.models.corpus import DuplicateCandidate, DuplicateDecision
from app.schemas.duplicates import (
    DuplicateCandidateRead,
    DuplicateDecisionRequest,
    DuplicatesRead,
)

router = APIRouter(prefix="/reports", tags=["duplicates"])


@router.get("/{report_id}/duplicates", response_model=DuplicatesRead)
def read_duplicates(report_id: UUID, current_user: CurrentUser, db: DbSession) -> DuplicatesRead:
    """The candidates found by the most recent search, most similar first,
    each with the person's decision if they made one. A report never
    searched reads back with `searched` false and no candidates, not an
    error. 404 rules match every other report endpoint (NFR-15)."""
    report = get_owned_report_or_404(db, current_user, report_id)
    return read_candidates(db, report)


@router.post("/{report_id}/duplicates", response_model=DuplicatesRead)
def search_duplicates(report_id: UUID, current_user: CurrentUser, db: DbSession) -> DuplicatesRead:
    """Searches the shared corpus and the user's own earlier reports, and
    replaces the stored candidates with the top five at or above the
    possible-duplicate threshold (US-20 criteria 1 and 2). Decisions are
    kept apart from the candidates, so searching again never loses one. If
    the similarity model cannot be loaded, says so with a 503 and leaves
    the previous candidates untouched, rather than failing with a bare
    500."""
    report = get_owned_report_or_404(db, current_user, report_id)
    try:
        find_duplicates(db, report)
    except EmbeddingUnavailableError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Duplicate search is unavailable right now. Try again later.",
        ) from error
    return read_candidates(db, report)


@router.put("/{report_id}/duplicates/{candidate_id}/decision", response_model=DuplicatesRead)
def decide_duplicate(
    report_id: UUID,
    candidate_id: UUID,
    body: DuplicateDecisionRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> DuplicatesRead:
    """Stores a person's "Duplicate" or "Not duplicate" decision on one
    candidate, or takes it back with `null` (US-21 criteria 1 and 2). An
    unknown candidate is a 404, the same as an unknown report (NFR-15)."""
    report = get_owned_report_or_404(db, current_user, report_id)
    candidate = next((c for c in report.duplicate_candidates if c.id == candidate_id), None)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    existing = _decision_for(report, candidate)
    if body.decision is None:
        if existing is not None:
            report.duplicate_decisions.remove(existing)
    elif existing is None:
        report.duplicate_decisions.append(
            DuplicateDecision(
                corpus_issue_id=candidate.corpus_issue_id,
                candidate_report_id=candidate.candidate_report_id,
                decision=body.decision,
            )
        )
    else:
        existing.decision = body.decision
    db.commit()
    return read_candidates(db, report)


def _decision_for(report: BugReport, candidate: DuplicateCandidate) -> DuplicateDecision | None:
    return next(
        (
            d
            for d in report.duplicate_decisions
            if d.corpus_issue_id == candidate.corpus_issue_id
            and d.candidate_report_id == candidate.candidate_report_id
        ),
        None,
    )


def read_candidates(db: Session, report: BugReport) -> DuplicatesRead:
    """Shared with the generated report and GitHub routers."""
    candidates = []
    for row in report.duplicate_candidates:
        decision = _decision_for(report, row)
        common = {
            "candidate_id": str(row.id),
            "score": row.score,
            "label": row.label,
            "rank": row.rank,
            "decision": decision.decision if decision else None,
        }
        if row.corpus_issue is not None:
            candidates.append(
                DuplicateCandidateRead(
                    id=str(row.corpus_issue.id),
                    source="corpus",
                    title=row.corpus_issue.title,
                    url=row.corpus_issue.url,
                    **common,
                )
            )
        elif row.candidate_report is not None:
            other = row.candidate_report
            candidates.append(
                DuplicateCandidateRead(
                    id=str(other.id),
                    source="report",
                    title=other.title or other.original_text[:80],
                    url=f"/reports/{other.id}",
                    **common,
                )
            )
    return DuplicatesRead(
        searched=report.embedding is not None,
        compared_count=compared_count(db, report),
        candidates=candidates,
    )
