"""Tests for the verification layer (FR-27, US-09 criterion 4). This suite
proves the labelling rules on their own, independent of any story, per
docs/sprints.md's Sprint 2 dependencies: the verification layer is built
and tested before anything else in the pipeline."""

from app.analysis.schema import RawEnvironmentDetail, RawExtractionResult, RawModelField
from app.analysis.verification import (
    quote_is_verbatim,
    shares_content,
    steps_need_review,
    verify_extraction,
    verify_field,
)

# The reference report, quoted verbatim from Section 1.1 of the requirements
# report. US-08 criterion 1 requires this exact example to extract correctly.
REFERENCE_REPORT = (
    "login crashes sometimes when i put wrong password and click login, "
    "happened on chrome windows, expected error message but application closes"
)


class TestQuoteIsVerbatim:
    def test_quote_present_in_report_is_verbatim(self):
        assert quote_is_verbatim("application closes", REFERENCE_REPORT) is True

    def test_quote_absent_from_report_is_not_verbatim(self):
        assert quote_is_verbatim("the server crashed", REFERENCE_REPORT) is False

    def test_verbatim_check_is_case_insensitive(self):
        assert quote_is_verbatim("CHROME WINDOWS", REFERENCE_REPORT) is True

    def test_verbatim_check_normalises_whitespace(self):
        report = "step one\n\n   step two"
        assert quote_is_verbatim("step one step two", report) is True

    def test_empty_quote_is_not_verbatim(self):
        assert quote_is_verbatim("", REFERENCE_REPORT) is False
        assert quote_is_verbatim("   ", REFERENCE_REPORT) is False


class TestSharesContent:
    def test_identical_text_shares_content(self):
        assert shares_content("application closes", "application closes") is True

    def test_overlapping_content_words_share_content(self):
        assert shares_content("an error message is shown", "expected error message") is True

    def test_unrelated_text_does_not_share_content(self):
        assert shares_content("database connection timeout", "login button disabled") is False

    def test_only_stopwords_never_share_content(self):
        assert shares_content("the a is", "an of to") is False


class TestVerifyFieldOrdinary:
    """Fields outside WRITTEN_FIELDS follow the general FR-27 rule: quote
    verbatim first, then quote supports value."""

    def test_missing_field_is_labelled_missing(self):
        """FR-09: a field the model did not fill is Missing."""
        result = verify_field("actual_behaviour", None, REFERENCE_REPORT)
        assert result.label == "Missing"
        assert result.value is None
        assert result.source_quote is None

    def test_quote_not_in_report_is_unverified(self):
        """FR-27: fields that fail the first check (quote verbatim in the
        report) are labelled Unverified."""
        raw = RawModelField(
            value="Firefox",
            source_quote="using firefox on this bug",
            confidence=0.8,
            reason="Stated browser",
        )
        result = verify_field("browser", raw, REFERENCE_REPORT)
        assert result.label == "Unverified"

    def test_quote_verbatim_and_value_contained_in_quote_is_explicit(self):
        """FR-27: quote verbatim and quote supports the value is Explicit."""
        raw = RawModelField(
            value="application closes",
            source_quote="but application closes",
            confidence=0.95,
            reason="Directly stated",
        )
        result = verify_field("actual_behaviour", raw, REFERENCE_REPORT)
        assert result.label == "Explicit"

    def test_quote_verbatim_but_does_not_support_value_is_inferred(self):
        """FR-27: fields that fail the second check (quote supports value)
        are labelled Inferred."""
        raw = RawModelField(
            value="Firefox",
            source_quote="happened on chrome windows",
            confidence=0.4,
            reason="Guessed from context",
        )
        result = verify_field("browser", raw, REFERENCE_REPORT)
        assert result.label == "Inferred"

    def test_the_reference_example_expected_behaviour_is_explicit(self):
        """US-08 criterion 1: for the sample report, expected behaviour is
        'an error message is shown', labelled Explicit."""
        raw = RawModelField(
            value="an error message is shown",
            source_quote="expected error message",
            confidence=0.9,
            reason="Stated directly after 'expected'",
        )
        result = verify_field("expected_behaviour", raw, REFERENCE_REPORT)
        assert result.value == "an error message is shown"
        assert result.label == "Explicit"

    def test_the_reference_example_actual_behaviour_is_explicit(self):
        """US-08 criterion 1: actual behaviour is 'the application closes',
        labelled Explicit."""
        raw = RawModelField(
            value="the application closes",
            source_quote="but application closes",
            confidence=0.92,
            reason="Stated directly after 'but'",
        )
        result = verify_field("actual_behaviour", raw, REFERENCE_REPORT)
        assert result.value == "the application closes"
        assert result.label == "Explicit"

    def test_a_value_never_invented_when_the_quote_cannot_be_found(self):
        """US-08 criterion 3: a field that cannot be found is shown as
        Missing and is never invented. This is proved at the None case
        (test_missing_field_is_labelled_missing) and again here: even a
        confidently stated but unverifiable value does not become
        Explicit or Inferred silently trusted as fact, it is flagged
        Unverified rather than presented as a stated fact."""
        raw = RawModelField(
            value="Safari",
            source_quote="reported using safari browser",
            confidence=0.99,
            reason="Model claims high confidence",
        )
        result = verify_field("browser", raw, REFERENCE_REPORT)
        assert result.label == "Unverified"


class TestVerifyFieldWritten:
    """title, summary and steps skip the verbatim check and are judged on
    content overlap with the report itself (ADR-014, US-09 criterion 4)."""

    def test_written_field_sharing_content_with_report_is_explicit(self):
        """US-09 criterion 4: a step counts as Explicit when the quote
        shares its main action and object with the report."""
        raw = RawModelField(
            value="Click Login",
            source_quote="click login",
            confidence=0.85,
            reason="Imperative rewrite of the reported action",
        )
        result = verify_field("steps", raw, REFERENCE_REPORT)
        assert result.label == "Explicit"

    def test_written_field_not_sharing_content_with_report_is_inferred(self):
        """US-09 criterion 4: a step is Inferred otherwise."""
        raw = RawModelField(
            value="Restart the browser",
            source_quote="restart browser step",
            confidence=0.3,
            reason="Not stated in the report",
        )
        result = verify_field("steps", raw, REFERENCE_REPORT)
        assert result.label == "Inferred"

    def test_written_field_is_never_unverified(self):
        """Written fields only ever come out Explicit or Inferred, never
        Unverified, since a paraphrase is never a literal substring by
        definition (ADR-014)."""
        raw = RawModelField(
            value="Something entirely unrelated",
            source_quote="not in the report at all",
            confidence=0.1,
            reason="Low confidence",
        )
        result = verify_field("title", raw, REFERENCE_REPORT)
        assert result.label in ("Explicit", "Inferred")

    def test_title_written_from_the_reference_example_is_explicit(self):
        raw = RawModelField(
            value="Application closes on login with a wrong password",
            source_quote="login crashes when i put wrong password",
            confidence=0.8,
            reason="Condensed from the report",
        )
        result = verify_field("title", raw, REFERENCE_REPORT)
        assert result.label == "Explicit"


class TestVerifyEnvironmentDetail:
    def test_environment_detail_verbatim_and_supported_is_explicit(self):
        """US-10 criterion 1: 'chrome windows' gives browser = Chrome."""
        raw = RawEnvironmentDetail(name="browser", value="Chrome", source_quote="chrome windows")
        result = verify_extraction(
            RawExtractionResult(environment=[raw]), REFERENCE_REPORT
        ).environment[0]
        assert result.name == "browser"
        assert result.value == "Chrome"
        assert result.label == "Explicit"

    def test_environment_detail_not_in_report_is_unverified(self):
        raw = RawEnvironmentDetail(
            name="database", value="PostgreSQL 14", source_quote="using postgresql 14"
        )
        result = verify_extraction(
            RawExtractionResult(environment=[raw]), REFERENCE_REPORT
        ).environment[0]
        assert result.label == "Unverified"

    def test_inferred_device_from_the_reference_example(self):
        """US-10 criterion 4: inferred values (for example, Device =
        Desktop because the OS is Windows) are clearly marked as
        Inferred."""
        raw = RawEnvironmentDetail(
            name="device", value="Desktop", source_quote="happened on chrome windows"
        )
        result = verify_extraction(
            RawExtractionResult(environment=[raw]), REFERENCE_REPORT
        ).environment[0]
        assert result.label == "Inferred"

    def test_an_alias_name_is_normalised_to_its_canonical_name(self):
        """US-10 criterion 3: the same concept written differently is
        stored under one name, for example "chrome" and "Chrome browser"
        both become "browser" (ADR-015)."""
        for alias in ("chrome", "Chrome browser", "  BROWSER TYPE  "):
            raw = RawEnvironmentDetail(name=alias, value="Chrome", source_quote="chrome windows")
            result = verify_extraction(
                RawExtractionResult(environment=[raw]), REFERENCE_REPORT
            ).environment[0]
            assert result.name == "browser", f"{alias!r} did not normalise to 'browser'"

    def test_an_unrecognised_name_is_still_lowercased_and_trimmed(self):
        raw = RawEnvironmentDetail(name="  Shell  ", value="bash", source_quote="chrome windows")
        result = verify_extraction(
            RawExtractionResult(environment=[raw]), REFERENCE_REPORT
        ).environment[0]
        assert result.name == "shell"


class TestVerifyExtraction:
    def test_missing_fields_default_to_missing_label(self):
        """A raw result with nothing filled in produces an all-Missing
        extraction, not an error (FR-28's safe fallback shape)."""
        result = verify_extraction(RawExtractionResult(), REFERENCE_REPORT)
        assert result.title.label == "Missing"
        assert result.summary.label == "Missing"
        assert result.expected_behaviour.label == "Missing"
        assert result.actual_behaviour.label == "Missing"
        assert result.frequency.label == "Missing"
        assert result.steps == []
        assert result.environment == []
        assert result.error_messages == []

    def test_frequency_is_an_ordinary_field_verified_like_any_other(self):
        """frequency is one of the five essential fields (US-13 criterion
        1) and follows the general FR-27 rule, not the written-field rule:
        it is not in WRITTEN_FIELDS."""
        raw = RawExtractionResult(
            frequency=RawModelField(
                value="sometimes",
                source_quote="crashes sometimes",
                confidence=0.7,
                reason="Stated directly",
            )
        )
        result = verify_extraction(raw, REFERENCE_REPORT)
        assert result.frequency.label == "Explicit"

    def test_full_reference_example_end_to_end(self):
        """US-08 criterion 1 and 2, assembled as a full extraction: each
        field is labelled, and expected/actual behaviour come out
        Explicit for the canonical example."""
        raw = RawExtractionResult(
            expected_behaviour=RawModelField(
                value="an error message is shown",
                source_quote="expected error message",
                confidence=0.9,
                reason="Stated directly",
            ),
            actual_behaviour=RawModelField(
                value="the application closes",
                source_quote="but application closes",
                confidence=0.92,
                reason="Stated directly",
            ),
            environment=[
                RawEnvironmentDetail(name="browser", value="Chrome", source_quote="chrome windows"),
                RawEnvironmentDetail(name="os", value="Windows", source_quote="chrome windows"),
            ],
        )
        result = verify_extraction(raw, REFERENCE_REPORT)
        assert result.expected_behaviour.label == "Explicit"
        assert result.actual_behaviour.label == "Explicit"
        assert result.title.label == "Missing"
        browser = next(e for e in result.environment if e.name == "browser")
        os_detail = next(e for e in result.environment if e.name == "os")
        assert browser.label == "Explicit"
        assert os_detail.label == "Explicit"


class TestStepsNeedReview:
    """US-09 criterion 5: a report producing more than seven steps is
    flagged for human review rather than shortened automatically."""

    def test_seven_or_fewer_steps_do_not_need_review(self):
        raw = RawExtractionResult(
            steps=[
                RawModelField(value=f"Step {i}", source_quote="x", confidence=0.9, reason="x")
                for i in range(7)
            ]
        )
        result = verify_extraction(raw, REFERENCE_REPORT)
        assert len(result.steps) == 7
        assert steps_need_review(result.steps) is False

    def test_exactly_eight_steps_needs_review(self):
        raw = RawExtractionResult(
            steps=[
                RawModelField(value=f"Step {i}", source_quote="x", confidence=0.9, reason="x")
                for i in range(8)
            ]
        )
        result = verify_extraction(raw, REFERENCE_REPORT)
        assert len(result.steps) == 8
        assert steps_need_review(result.steps) is True

    def test_more_than_seven_steps_need_review_and_none_are_dropped(self):
        raw = RawExtractionResult(
            steps=[
                RawModelField(value=f"Step {i}", source_quote="x", confidence=0.9, reason="x")
                for i in range(10)
            ]
        )
        result = verify_extraction(raw, REFERENCE_REPORT)
        assert len(result.steps) == 10
        assert steps_need_review(result.steps) is True
