"""Tests for the Sprint 3 tables (app/models/triage.py, app/models/corpus.py):
rows round-trip, the CHECK and UNIQUE constraints hold, and deleting a
report removes every row that references it (docs/design.md section 6.4,
US-07 criterion 2)."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.core import BugReport, User
from app.models.corpus import CorpusIssue, DuplicateCandidate, ReportEmbedding
from app.models.triage import TriageOverride, TriageValue
from app.models.types import EMBEDDING_DIMENSIONS
from tests.conftest import TestingSessionLocal

_VECTOR = [0.5] * EMBEDDING_DIMENSIONS


def _make_user_and_report(db) -> BugReport:
    user = User(email=f"{uuid.uuid4()}@example.com", password_hash="not-a-real-hash")
    db.add(user)
    db.flush()
    report = BugReport(user_id=user.id, original_text="x" * 20)
    db.add(report)
    db.flush()
    return report


def _triage_value(report: BugReport, field_name: str = "severity") -> TriageValue:
    return TriageValue(
        report_id=report.id,
        field_name=field_name,
        suggested_value="High",
        reason="r",
        value="High",
        overridden=False,
    )


def _corpus_issue(external_id: str = "acme/app#1") -> CorpusIssue:
    return CorpusIssue(
        external_id=external_id,
        title="t",
        body="b",
        url="https://example.com/1",
        embedding=_VECTOR,
    )


class TestTriageTables:
    def test_an_unknown_field_name_is_rejected_by_the_database(self):
        with TestingSessionLocal() as db:
            report = _make_user_and_report(db)
            db.add(_triage_value(report, field_name="owner"))
            with pytest.raises(IntegrityError):
                db.commit()

    def test_a_report_has_at_most_one_row_per_field(self):
        with TestingSessionLocal() as db:
            report = _make_user_and_report(db)
            db.add_all([_triage_value(report), _triage_value(report)])
            with pytest.raises(IntegrityError):
                db.commit()

    def test_deleting_a_report_removes_its_triage_and_overrides(self):
        with TestingSessionLocal() as db:
            report = _make_user_and_report(db)
            db.add(_triage_value(report))
            db.add(
                TriageOverride(
                    report_id=report.id,
                    user_id=report.user_id,
                    field_name="severity",
                    old_value="High",
                    new_value="Low",
                )
            )
            db.commit()

            db.delete(report)
            db.commit()

            assert db.query(TriageValue).count() == 0
            assert db.query(TriageOverride).count() == 0


class TestCorpusTables:
    def test_an_embedding_round_trips_as_a_list_of_floats(self):
        with TestingSessionLocal() as db:
            db.add(_corpus_issue())
            db.commit()

            stored = db.query(CorpusIssue).one()
            assert stored.embedding == _VECTOR

    def test_an_external_id_is_unique(self):
        with TestingSessionLocal() as db:
            db.add_all([_corpus_issue("same"), _corpus_issue("same")])
            with pytest.raises(IntegrityError):
                db.commit()

    def test_a_candidate_names_exactly_one_source(self):
        with TestingSessionLocal() as db:
            report = _make_user_and_report(db)
            db.add(
                DuplicateCandidate(report_id=report.id, rank=1, score=0.9, label="Likely duplicate")
            )
            with pytest.raises(IntegrityError):
                db.commit()

    def test_a_candidate_label_never_states_a_duplicate(self):
        """US-20 criterion 3, enforced by the database too."""
        with TestingSessionLocal() as db:
            report = _make_user_and_report(db)
            issue = _corpus_issue()
            db.add(issue)
            db.flush()
            db.add(
                DuplicateCandidate(
                    report_id=report.id,
                    corpus_issue_id=issue.id,
                    rank=1,
                    score=0.99,
                    label="Duplicate",
                )
            )
            with pytest.raises(IntegrityError):
                db.commit()

    def test_deleting_a_report_removes_its_embedding_and_candidates(self):
        with TestingSessionLocal() as db:
            report = _make_user_and_report(db)
            issue = _corpus_issue()
            db.add(issue)
            db.flush()
            db.add(ReportEmbedding(report_id=report.id, embedding=_VECTOR))
            db.add(
                DuplicateCandidate(
                    report_id=report.id,
                    corpus_issue_id=issue.id,
                    rank=1,
                    score=0.9,
                    label="Likely duplicate",
                )
            )
            db.commit()

            db.delete(report)
            db.commit()

            assert db.query(ReportEmbedding).count() == 0
            assert db.query(DuplicateCandidate).count() == 0
            assert db.query(CorpusIssue).count() == 1
