"""Finds the existing issues most similar to a report (FR-17, US-20).

Compares the report against the shared corpus and against the same user's
other reports (ADR-010), never another user's. A candidate is shown only
when its similarity reaches the possible-duplicate threshold, at most five
of them, most similar first (criteria 1 and 2). A label only ever says
"Likely duplicate" or "Possible duplicate"; nothing here states that two
reports are duplicates, since only a person decides that (criterion 3,
DR-05).

On PostgreSQL the cosine distance is computed in the database by pgvector
(ADR-003). Any other database, which in practice means the SQLite test
database, gets the same score computed in Python, so the ranking rules are
exercised by the test suite either way.
"""

import uuid
from dataclasses import dataclass
from typing import Literal

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, literal, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.corpus import embedding
from app.models.core import BugReport
from app.models.corpus import CorpusIssue, DuplicateCandidate, ReportEmbedding
from app.models.types import EMBEDDING_DIMENSIONS

MAX_CANDIDATES = 5
LIKELY_DUPLICATE = "Likely duplicate"
POSSIBLE_DUPLICATE = "Possible duplicate"


@dataclass(frozen=True)
class _Scored:
    source: Literal["corpus", "report"]
    id: uuid.UUID
    score: float


def label_for(score: float) -> str | None:
    """US-20 criterion 2: 0.80 or above is Likely, 0.60 up to 0.80 is
    Possible, anything lower is hidden (None). The two numbers come from
    settings and are starting estimates (ADR-018)."""
    settings = get_settings()
    if score >= settings.duplicate_likely_threshold:
        return LIKELY_DUPLICATE
    if score >= settings.duplicate_possible_threshold:
        return POSSIBLE_DUPLICATE
    return None


def report_embedding_text(report: BugReport) -> str:
    """What gets embedded for a report: its extracted title, when there is
    one, then the text as submitted."""
    return f"{report.title}\n{report.original_text}" if report.title else report.original_text


def find_duplicates(db: Session, report: BugReport) -> None:
    """Embeds the report, stores that embedding so later reports can find
    this one, ranks the candidates and replaces whatever candidates were
    stored for the report before. Commits."""
    vector = embedding.embed([report_embedding_text(report)])[0]
    if report.embedding is None:
        report.embedding = ReportEmbedding(embedding=vector)
    else:
        report.embedding.embedding = vector
    db.flush()

    scored = _score_candidates(db, report, vector)
    threshold = get_settings().duplicate_possible_threshold
    shown = sorted((s for s in scored if s.score >= threshold), key=lambda s: -s.score)
    shown = shown[:MAX_CANDIDATES]

    report.duplicate_candidates.clear()
    db.flush()
    for rank, candidate in enumerate(shown, start=1):
        report.duplicate_candidates.append(
            DuplicateCandidate(
                corpus_issue_id=candidate.id if candidate.source == "corpus" else None,
                candidate_report_id=candidate.id if candidate.source == "report" else None,
                rank=rank,
                score=candidate.score,
                label=label_for(candidate.score),
            )
        )
    db.commit()


def compared_count(db: Session, report: BugReport) -> int:
    """How many issues and past reports a search for this report compares
    against, so the interface can say what an empty result means."""
    corpus = db.query(CorpusIssue).count()
    own = (
        db.query(ReportEmbedding)
        .join(BugReport, ReportEmbedding.report_id == BugReport.id)
        .filter(BugReport.user_id == report.user_id, BugReport.id != report.id)
        .count()
    )
    return corpus + own


def _score_candidates(db: Session, report: BugReport, vector: list[float]) -> list[_Scored]:
    if db.get_bind().dialect.name == "postgresql":
        return _score_in_postgresql(db, report, vector)
    return _score_in_python(db, report, vector)


def _own_other_reports(report: BugReport):
    """Embeddings of the same user's other reports. Filtered by owner in the
    query itself, so another user's report can never be a candidate
    (NFR-15)."""
    return (
        select(ReportEmbedding.report_id, ReportEmbedding.embedding)
        .join(BugReport, ReportEmbedding.report_id == BugReport.id)
        .where(BugReport.user_id == report.user_id, BugReport.id != report.id)
    )


def _score_in_postgresql(db: Session, report: BugReport, vector: list[float]) -> list[_Scored]:
    query_vector = literal(vector, type_=Vector(EMBEDDING_DIMENSIONS))

    corpus_distance = CorpusIssue.embedding.op("<=>", return_type=Float)(query_vector)
    corpus_rows = db.execute(
        select(CorpusIssue.id, corpus_distance.label("distance"))
        .order_by(corpus_distance)
        .limit(MAX_CANDIDATES)
    ).all()

    own_distance = ReportEmbedding.embedding.op("<=>", return_type=Float)(query_vector)
    own_rows = db.execute(
        select(ReportEmbedding.report_id, own_distance.label("distance"))
        .join(BugReport, ReportEmbedding.report_id == BugReport.id)
        .where(BugReport.user_id == report.user_id, BugReport.id != report.id)
        .order_by(own_distance)
        .limit(MAX_CANDIDATES)
    ).all()

    return [_Scored("corpus", row.id, 1 - row.distance) for row in corpus_rows] + [
        _Scored("report", row.report_id, 1 - row.distance) for row in own_rows
    ]


def _score_in_python(db: Session, report: BugReport, vector: list[float]) -> list[_Scored]:
    corpus_rows = db.execute(select(CorpusIssue.id, CorpusIssue.embedding)).all()
    own_rows = db.execute(_own_other_reports(report)).all()
    return [_Scored("corpus", row.id, _cosine(vector, row.embedding)) for row in corpus_rows] + [
        _Scored("report", row.report_id, _cosine(vector, row.embedding)) for row in own_rows
    ]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
