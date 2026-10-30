"""Tests for follow-up question filtering (FR-32, US-14, ADR-016)."""

from app.analysis.questions import MAX_QUESTIONS, filter_questions
from app.analysis.schema import (
    EnvironmentDetail,
    ExtractedField,
    ExtractionResult,
    Label,
    RawFollowUpQuestion,
)


def _explicit(value: str = "x") -> ExtractedField:
    return ExtractedField(value=value, source_quote=value, label=Label.EXPLICIT)


def _missing() -> ExtractedField:
    return ExtractedField(value=None, source_quote=None, label=Label.MISSING)


def _unverified(value: str = "x") -> ExtractedField:
    return ExtractedField(value=value, source_quote=value, label=Label.UNVERIFIED)


def _all_missing_result() -> ExtractionResult:
    return ExtractionResult(
        title=_missing(),
        summary=_missing(),
        expected_behaviour=_missing(),
        actual_behaviour=_missing(),
        frequency=_missing(),
        steps=[],
        environment=[],
        error_messages=[],
    )


def _all_explicit_result() -> ExtractionResult:
    env = EnvironmentDetail(
        name="browser", value="Chrome", source_quote="chrome", label=Label.EXPLICIT
    )
    return ExtractionResult(
        title=_explicit(),
        summary=_explicit(),
        expected_behaviour=_explicit(),
        actual_behaviour=_explicit(),
        frequency=_explicit(),
        steps=[_explicit()],
        environment=[env],
        error_messages=[],
    )


class TestDroppingVerifiedFields:
    def test_question_for_an_already_explicit_field_is_dropped(self):
        """US-14 criterion 2."""
        result = _all_explicit_result()
        raw = [
            RawFollowUpQuestion(
                field="expected_behaviour", question="What did you expect?", reason="Missing"
            )
        ]
        questions = filter_questions(raw, result)
        assert questions == []

    def test_question_for_an_unverified_field_is_kept(self):
        """Unverified is not 'verified'; the model's question about it
        should survive filtering, since the field still needs confirming."""
        result = _all_explicit_result()
        result.expected_behaviour = _unverified()
        raw = [
            RawFollowUpQuestion(
                field="expected_behaviour",
                question="Can you confirm what you expected?",
                reason="Unverified",
            )
        ]
        questions = filter_questions(raw, result)
        assert len(questions) == 1
        assert questions[0].field == "expected_behaviour"

    def test_question_for_a_field_with_at_least_one_explicit_step_is_dropped(self):
        result = _all_explicit_result()
        raw = [RawFollowUpQuestion(field="steps", question="What did you do?", reason="Missing")]
        assert filter_questions(raw, result) == []


class TestEssentialFieldGuarantee:
    def test_missing_essential_field_gets_a_fallback_question_when_model_proposes_none(self):
        """US-14 criterion 3."""
        result = _all_missing_result()
        questions = filter_questions([], result)
        fields = {q.field for q in questions}
        assert fields == {
            "expected_behaviour",
            "actual_behaviour",
            "frequency",
            "steps",
            "environment",
        }
        assert all(not q.model_proposed for q in questions)

    def test_missing_essential_field_uses_the_models_own_question_when_it_proposed_one(self):
        result = _all_missing_result()
        raw = [
            RawFollowUpQuestion(
                field="frequency",
                question="How often have you seen this bug?",
                reason="Not stated anywhere",
            )
        ]
        questions = filter_questions(raw, result)
        frequency_question = next(q for q in questions if q.field == "frequency")
        assert frequency_question.model_proposed is True
        assert frequency_question.question == "How often have you seen this bug?"

    def test_non_essential_missing_field_does_not_force_a_question(self):
        """title and summary are not essential fields (US-13 criterion 1),
        so a missing title alone should not force a question about it."""
        result = _all_missing_result()
        questions = filter_questions([], result)
        assert all(q.field != "title" for q in questions)
        assert all(q.field != "summary" for q in questions)

    def test_empty_steps_list_counts_as_missing(self):
        result = _all_explicit_result()
        result.steps = []
        questions = filter_questions([], result)
        assert any(q.field == "steps" for q in questions)

    def test_empty_environment_list_counts_as_missing(self):
        result = _all_explicit_result()
        result.environment = []
        questions = filter_questions([], result)
        assert any(q.field == "environment" for q in questions)

    def test_a_single_explicit_environment_entry_satisfies_the_essential_requirement(self):
        result = _all_explicit_result()
        questions = filter_questions([], result)
        assert all(q.field != "environment" for q in questions)


class TestCap:
    def test_no_more_than_six_questions_are_ever_returned(self):
        """US-14 criterion 4."""
        result = _all_missing_result()
        raw = [
            RawFollowUpQuestion(field="title", question="What is the title?", reason="Missing"),
            RawFollowUpQuestion(field="summary", question="Summarise the bug?", reason="Missing"),
            RawFollowUpQuestion(
                field="error_messages", question="Any error shown?", reason="Missing"
            ),
        ]
        questions = filter_questions(raw, result)
        assert len(questions) <= MAX_QUESTIONS

    def test_essential_questions_are_never_pushed_out_by_the_cap(self):
        """All five essential fields fit inside the cap of six, so none of
        them should ever be dropped to make room for a non-essential one."""
        result = _all_missing_result()
        raw = [
            RawFollowUpQuestion(field="title", question="What is the title?", reason="Missing"),
            RawFollowUpQuestion(field="summary", question="Summarise the bug?", reason="Missing"),
        ]
        questions = filter_questions(raw, result)
        fields = {q.field for q in questions}
        for essential in (
            "expected_behaviour",
            "actual_behaviour",
            "frequency",
            "steps",
            "environment",
        ):
            assert essential in fields


class TestNoQuestionsNeeded:
    def test_a_fully_explicit_result_with_no_proposals_produces_no_questions(self):
        result = _all_explicit_result()
        assert filter_questions([], result) == []
