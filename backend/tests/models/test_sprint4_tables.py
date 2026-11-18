"""Tests for the Sprint 4 schema (the fourth migration): row sources, duplicate
decisions and GitHub connections keep their constraints, and deleting a
report or a user removes everything linked to it (US-07 criterion 2)."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.analysis import ExtractedField
from app.models.core import BugReport, User
from app.models.corpus import CorpusIssue, DuplicateDecision
from app.models.github import GitHubConnection
from app.models.types import EMBEDDING_DIMENSIONS
from tests.conftest import TestingSessionLocal


def _user_and_report(db) -> BugReport:
    user = User(email=f"{uuid.uuid4()}@example.com", password_hash="not-a-real-hash")
    db.add(user)
    db.flush()
    report = BugReport(user_id=user.id, original_text="x" * 20)
    db.add(report)
    db.flush()
    return report


def _corpus_issue(db) -> CorpusIssue:
    issue = CorpusIssue(
        external_id=str(uuid.uuid4()),
        title="t",
        body="b",
        url="https://example.com/1",
        embedding=[0.1] * EMBEDDING_DIMENSIONS,
    )
    db.add(issue)
    db.flush()
    return issue


def test_a_row_defaults_to_the_model_as_its_source():
    with TestingSessionLocal() as db:
        report = _user_and_report(db)
        db.add(ExtractedField(report_id=report.id, field_name="title", label="Missing"))
        db.commit()

        assert db.query(ExtractedField).one().source == "model"


def test_an_unknown_source_is_rejected_by_the_database():
    with TestingSessionLocal() as db:
        report = _user_and_report(db)
        db.add(
            ExtractedField(report_id=report.id, field_name="title", label="Missing", source="guess")
        )
        with pytest.raises(IntegrityError):
            db.commit()


def test_a_decision_must_be_duplicate_or_not_duplicate():
    with TestingSessionLocal() as db:
        report = _user_and_report(db)
        issue = _corpus_issue(db)
        db.add(DuplicateDecision(report_id=report.id, corpus_issue_id=issue.id, decision="maybe"))
        with pytest.raises(IntegrityError):
            db.commit()


def test_deleting_a_report_removes_its_decisions():
    with TestingSessionLocal() as db:
        report = _user_and_report(db)
        issue = _corpus_issue(db)
        db.add(
            DuplicateDecision(report_id=report.id, corpus_issue_id=issue.id, decision="duplicate")
        )
        db.commit()

        db.delete(report)
        db.commit()

        assert db.query(DuplicateDecision).count() == 0


def test_deleting_a_user_removes_their_github_connection():
    with TestingSessionLocal() as db:
        report = _user_and_report(db)
        user = db.get(User, report.user_id)
        user.github_connection = GitHubConnection(encrypted_token="ciphertext", login="octocat")
        db.commit()

        db.delete(user)
        db.commit()

        assert db.query(GitHubConnection).count() == 0


def test_a_user_has_at_most_one_github_connection():
    with TestingSessionLocal() as db:
        report = _user_and_report(db)
        db.add_all(
            [
                GitHubConnection(user_id=report.user_id, encrypted_token="a", login="x"),
                GitHubConnection(user_id=report.user_id, encrypted_token="b", login="y"),
            ]
        )
        with pytest.raises(IntegrityError):
            db.commit()
