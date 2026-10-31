"""Tests for the Sprint 2 analysis tables (app/models/analysis.py): the
relationships resolve, rows can be written and read back, an invalid label
is rejected, and deleting a report cascades to every row that references it
(docs/design.md section 6.4)."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.analysis import EnvironmentDetail, ExtractedField, FollowUpQuestion
from app.models.core import BugReport, User
from tests.conftest import TestingSessionLocal


def _make_user_and_report(db) -> BugReport:
    user = User(email=f"{uuid.uuid4()}@example.com", password_hash="not-a-real-hash")
    db.add(user)
    db.flush()
    report = BugReport(user_id=user.id, original_text="x" * 20)
    db.add(report)
    db.flush()
    return report


class TestExtractedField:
    def test_a_row_can_be_written_and_read_back(self):
        with TestingSessionLocal() as db:
            report = _make_user_and_report(db)
            field = ExtractedField(
                report_id=report.id,
                field_name="expected_behaviour",
                value="an error message is shown",
                source_quote="expected error message",
                label="Explicit",
                confidence=0.9,
                reason="Stated directly",
            )
            db.add(field)
            db.commit()

            stored = db.query(ExtractedField).filter_by(report_id=report.id).one()
            assert stored.field_name == "expected_behaviour"
            assert stored.label == "Explicit"

    def test_a_list_field_entry_carries_its_position(self):
        with TestingSessionLocal() as db:
            report = _make_user_and_report(db)
            db.add_all(
                [
                    ExtractedField(
                        report_id=report.id,
                        field_name="steps",
                        position=0,
                        value="Click Login",
                        source_quote="click login",
                        label="Explicit",
                    ),
                    ExtractedField(
                        report_id=report.id,
                        field_name="steps",
                        position=1,
                        value="Enter wrong password",
                        source_quote="wrong password",
                        label="Explicit",
                    ),
                ]
            )
            db.commit()

            steps = (
                db.query(ExtractedField)
                .filter_by(report_id=report.id, field_name="steps")
                .order_by(ExtractedField.position)
                .all()
            )
            assert [s.position for s in steps] == [0, 1]

    def test_an_invalid_label_is_rejected(self):
        """FR-09, FR-27: only the four labels are ever valid, enforced at
        the database, not only in Python."""
        with TestingSessionLocal() as db:
            report = _make_user_and_report(db)
            field = ExtractedField(report_id=report.id, field_name="title", label="Maybe")
            db.add(field)
            with pytest.raises(IntegrityError):
                db.commit()


class TestEnvironmentDetail:
    def test_a_row_can_be_written_and_read_back(self):
        with TestingSessionLocal() as db:
            report = _make_user_and_report(db)
            detail = EnvironmentDetail(
                report_id=report.id,
                name="browser",
                value="Chrome",
                source_quote="chrome windows",
                label="Explicit",
            )
            db.add(detail)
            db.commit()

            stored = db.query(EnvironmentDetail).filter_by(report_id=report.id).one()
            assert stored.name == "browser"
            assert stored.value == "Chrome"

    def test_an_invalid_label_is_rejected(self):
        with TestingSessionLocal() as db:
            report = _make_user_and_report(db)
            detail = EnvironmentDetail(
                report_id=report.id, name="os", value="Windows", source_quote="windows", label="???"
            )
            db.add(detail)
            with pytest.raises(IntegrityError):
                db.commit()


class TestFollowUpQuestion:
    def test_a_model_proposed_question_can_be_written_and_read_back(self):
        with TestingSessionLocal() as db:
            report = _make_user_and_report(db)
            question = FollowUpQuestion(
                report_id=report.id,
                field_name="frequency",
                question="How often does this happen?",
                reason="Not stated",
                model_proposed=True,
            )
            db.add(question)
            db.commit()

            stored = db.query(FollowUpQuestion).filter_by(report_id=report.id).one()
            assert stored.model_proposed is True
            assert stored.answer is None

    def test_a_fallback_question_is_recorded_as_not_model_proposed(self):
        """US-14 criterion 3: code's own fallback question is a real row
        too, distinguishable from one the model proposed."""
        with TestingSessionLocal() as db:
            report = _make_user_and_report(db)
            question = FollowUpQuestion(
                report_id=report.id,
                field_name="steps",
                question="What steps led up to this?",
                reason="Essential field, none extracted",
                model_proposed=False,
            )
            db.add(question)
            db.commit()

            stored = db.query(FollowUpQuestion).filter_by(report_id=report.id).one()
            assert stored.model_proposed is False

    def test_answering_sets_the_answer_and_answered_at(self):
        from datetime import UTC, datetime

        with TestingSessionLocal() as db:
            report = _make_user_and_report(db)
            question = FollowUpQuestion(
                report_id=report.id,
                field_name="frequency",
                question="How often?",
                reason="Missing",
                model_proposed=True,
            )
            db.add(question)
            db.commit()

            question.answer = "About once a day"
            question.answered_at = datetime.now(UTC)
            db.commit()

            stored = db.query(FollowUpQuestion).filter_by(report_id=report.id).one()
            assert stored.answer == "About once a day"
            assert stored.answered_at is not None


class TestCascadeDelete:
    def test_deleting_a_report_removes_every_linked_analysis_row(self):
        """US-07 criterion 2, extended to the Sprint 2 tables: deleting a
        report removes everything linked to it."""
        with TestingSessionLocal() as db:
            report = _make_user_and_report(db)
            db.add(
                ExtractedField(
                    report_id=report.id,
                    field_name="title",
                    value="x",
                    source_quote="x",
                    label="Explicit",
                )
            )
            db.add(
                EnvironmentDetail(
                    report_id=report.id,
                    name="os",
                    value="Windows",
                    source_quote="windows",
                    label="Explicit",
                )
            )
            db.add(
                FollowUpQuestion(
                    report_id=report.id,
                    field_name="frequency",
                    question="How often?",
                    reason="Missing",
                    model_proposed=False,
                )
            )
            db.commit()
            report_id = report.id

            db.delete(report)
            db.commit()

            assert db.query(ExtractedField).filter_by(report_id=report_id).count() == 0
            assert db.query(EnvironmentDetail).filter_by(report_id=report_id).count() == 0
            assert db.query(FollowUpQuestion).filter_by(report_id=report_id).count() == 0
