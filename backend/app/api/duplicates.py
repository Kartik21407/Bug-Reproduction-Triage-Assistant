"""Lists a report's duplicate candidates and runs a fresh search (US-20,
FR-17). Confirming or rejecting a candidate (FR-18, US-21) is not built
yet."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from app.api.reports import get_owned_report_or_404
from app.corpus.embedding import EmbeddingUnavailableError
from app.corpus.search import compared_count, find_duplicates
from app.deps import CurrentUser, DbSession
from app.models.core import BugReport
from app.schemas.duplicates import DuplicateCandidateRead, DuplicatesRead

router = APIRouter(prefix="/reports", tags=["duplicates"])


@router.get("/{report_id}/duplicates", response_model=DuplicatesRead)
def read_duplicates(report_id: UUID, current_user: CurrentUser, db: DbSession) -> DuplicatesRead:
    """The candidates found by the most recent search, most similar first.
    A report never searched reads back with `searched` false and no
    candidates, not an error. 404 rules match every other report endpoint
    (NFR-15)."""
    report = get_owned_report_or_404(db, current_user, report_id)
    return read_candidates(db, report)


@router.post("/{report_id}/duplicates", response_model=DuplicatesRead)
def search_duplicates(report_id: UUID, current_user: CurrentUser, db: DbSession) -> DuplicatesRead:
    """Searches the shared corpus and the user's own earlier reports, and
    replaces the stored candidates with the top five at or above the
    possible-duplicate threshold (US-20 criteria 1 and 2). If the
    similarity model cannot be loaded, says so with a 503 and leaves the
    previous candidates untouched, rather than failing with a bare 500."""
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


def read_candidates(db: Session, report: BugReport) -> DuplicatesRead:
    """Shared with the generated report router."""
    candidates = []
    for row in report.duplicate_candidates:
        if row.corpus_issue is not None:
            candidates.append(
                DuplicateCandidateRead(
                    id=str(row.corpus_issue.id),
                    source="corpus",
                    title=row.corpus_issue.title,
                    url=row.corpus_issue.url,
                    score=row.score,
                    label=row.label,
                    rank=row.rank,
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
                    score=row.score,
                    label=row.label,
                    rank=row.rank,
                )
            )
    return DuplicatesRead(
        searched=report.embedding is not None,
        compared_count=compared_count(db, report),
        candidates=candidates,
    )
