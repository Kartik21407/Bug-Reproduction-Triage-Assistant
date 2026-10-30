"""Tests for the completeness score (FR-11, US-13)."""

from app.analysis.completeness import compute_completeness
from app.analysis.schema import EnvironmentDetail, ExtractedField, ExtractionResult, Label


def _field(label: Label, value: str | None = "x") -> ExtractedField:
    return ExtractedField(value=value, source_quote=value, label=label)


def _result(
    expected_behaviour=Label.MISSING,
    actual_behaviour=Label.MISSING,
    frequency=Label.MISSING,
    steps: list[Label] | None = None,
    environment: list[Label] | None = None,
) -> ExtractionResult:
    return ExtractionResult(
        title=_field(Label.MISSING, None),
        summary=_field(Label.MISSING, None),
        expected_behaviour=_field(
            expected_behaviour, None if expected_behaviour == Label.MISSING else "x"
        ),
        actual_behaviour=_field(
            actual_behaviour, None if actual_behaviour == Label.MISSING else "x"
        ),
        frequency=_field(frequency, None if frequency == Label.MISSING else "x"),
        steps=[_field(label) for label in (steps or [])],
        environment=[
            EnvironmentDetail(name="browser", value="Chrome", source_quote="chrome", label=label)
            for label in (environment or [])
        ],
        error_messages=[],
    )


class TestAllMissing:
    def test_nothing_extracted_gives_a_zero_score_and_flags_every_field(self):
        """US-13 criteria 1 and 2: all five essential fields flagged
        missing, none counted."""
        result = _result()
        score = compute_completeness(result)
        assert score.verified_count == 0
        assert score.total == 5
        assert set(score.missing_fields) == {
            "expected_behaviour",
            "actual_behaviour",
            "frequency",
            "steps",
            "environment",
        }
        assert score.needs_confirmation_fields == []


class TestAllExplicit:
    def test_everything_verified_gives_a_full_score(self):
        """US-13 criterion 3."""
        result = _result(
            expected_behaviour=Label.EXPLICIT,
            actual_behaviour=Label.EXPLICIT,
            frequency=Label.EXPLICIT,
            steps=[Label.EXPLICIT],
            environment=[Label.EXPLICIT],
        )
        score = compute_completeness(result)
        assert score.verified_count == 5
        assert score.total == 5
        assert score.missing_fields == []
        assert score.needs_confirmation_fields == []


class TestInferredAndUnverified:
    def test_an_inferred_field_needs_confirmation_and_is_not_counted(self):
        """US-13 criterion 4."""
        result = _result(expected_behaviour=Label.INFERRED)
        score = compute_completeness(result)
        assert score.verified_count == 0
        assert "expected_behaviour" in score.needs_confirmation_fields
        assert "expected_behaviour" not in score.missing_fields

    def test_an_unverified_field_needs_confirmation_and_is_not_counted(self):
        result = _result(actual_behaviour=Label.UNVERIFIED)
        score = compute_completeness(result)
        assert score.verified_count == 0
        assert "actual_behaviour" in score.needs_confirmation_fields

    def test_a_list_field_with_only_inferred_entries_needs_confirmation(self):
        result = _result(steps=[Label.INFERRED, Label.INFERRED])
        score = compute_completeness(result)
        assert "steps" in score.needs_confirmation_fields
        assert "steps" not in score.missing_fields

    def test_a_list_field_with_one_explicit_entry_among_others_counts_as_verified(self):
        result = _result(environment=[Label.INFERRED, Label.EXPLICIT])
        score = compute_completeness(result)
        assert "environment" not in score.needs_confirmation_fields
        assert "environment" not in score.missing_fields
        assert score.verified_count == 1


class TestMixed:
    def test_a_realistic_partial_report(self):
        result = _result(
            expected_behaviour=Label.EXPLICIT,
            actual_behaviour=Label.EXPLICIT,
            frequency=Label.MISSING,
            steps=[Label.INFERRED],
            environment=[],
        )
        score = compute_completeness(result)
        assert score.verified_count == 2
        assert score.missing_fields == ["frequency", "environment"]
        assert score.needs_confirmation_fields == ["steps"]

    def test_non_essential_fields_never_affect_the_score(self):
        """title and summary are not essential (US-13 criterion 1); a
        fully missing report with them absent scores no differently than
        one with them present."""
        result = _result()
        with_title = result.model_copy(update={"title": _field(Label.EXPLICIT, "A title")})
        assert compute_completeness(result) == compute_completeness(with_title)
