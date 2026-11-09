"""Tests for the deterministic triage rules (app/triage/rules.py): US-15,
US-16 and US-17, plus DR-02, DR-03 and DR-04. Plain functions of text, so
no database and no model call."""

import pytest

from app.analysis.schema import EnvironmentDetail, ExtractedField, ExtractionResult, Label
from app.triage.rules import (
    CATEGORIES,
    PRIORITIES,
    REPRODUCIBILITY,
    SEVERITIES,
    suggest_category,
    suggest_priority,
    suggest_reproducibility,
    suggest_severity,
    suggest_triage,
    triage_text,
)

# The reference report from Section 1.1 of the requirements report.
REFERENCE_REPORT = (
    "login crashes sometimes when i put wrong password and click login, happened on chrome "
    "windows, expected error message but application closes"
)


def _missing() -> ExtractedField:
    return ExtractedField(value=None, source_quote=None, label=Label.MISSING)


def _empty_extraction(**overrides: object) -> ExtractionResult:
    fields = {
        "title": _missing(),
        "summary": _missing(),
        "expected_behaviour": _missing(),
        "actual_behaviour": _missing(),
        "frequency": _missing(),
        "steps": [],
        "environment": [],
        "error_messages": [],
    }
    fields.update(overrides)
    return ExtractionResult(**fields)


class TestSeverity:
    @pytest.mark.parametrize(
        "text",
        [
            REFERENCE_REPORT,
            "Typo in the footer",
            "All my drafts were lost, data loss",
            "The dashboard numbers look odd",
            "",
        ],
    )
    def test_the_suggestion_is_always_one_of_the_four_severities(self, text):
        """US-15 criterion 1: the suggestion is one of Critical, High,
        Medium or Low."""
        suggestion = suggest_severity(text)

        assert suggestion.value in SEVERITIES

    def test_a_crash_is_high_and_the_reason_names_it(self):
        """US-15 criterion 2: the reason names what triggered it, for
        example "mentions a crash, so High"."""
        suggestion = suggest_severity("The app crashes when I open settings")

        assert suggestion.value == "High"
        assert suggestion.reason == 'Mentions "crashes", so High'

    def test_data_loss_is_critical(self):
        """DR-03: Critical covers data loss."""
        suggestion = suggest_severity("After the update we had data loss on every account")

        assert suggestion.value == "Critical"
        assert "data loss" in suggestion.reason

    def test_a_security_breach_is_critical(self):
        """DR-03: Critical covers a security breach."""
        suggestion = suggest_severity("The profile page exposes user passwords in the HTML")

        assert suggestion.value == "Critical"

    def test_a_crash_with_a_workaround_is_medium(self):
        """DR-03: Medium is a function impaired but with a workaround."""
        suggestion = suggest_severity("Export crashes, but there is a workaround: use the CSV link")

        assert suggestion.value == "Medium"
        assert "crashes" in suggestion.reason
        assert "workaround" in suggestion.reason

    def test_cosmetic_wording_is_low(self):
        """DR-03: Low is cosmetic or minor."""
        suggestion = suggest_severity("There is a typo in the settings page header")

        assert suggestion.value == "Low"
        assert suggestion.reason == 'Mentions "typo", so Low'

    def test_no_signal_is_medium_and_says_so(self):
        """With nothing to go on the reason says so, rather than inventing a
        trigger (US-15 criterion 2, NFR-10)."""
        suggestion = suggest_severity("The dashboard numbers look different from yesterday")

        assert suggestion.value == "Medium"
        assert suggestion.reason.startswith("No crash")

    def test_the_same_text_always_gives_the_same_suggestion(self):
        """Rule based, not a model: deterministic."""
        assert suggest_severity(REFERENCE_REPORT) == suggest_severity(REFERENCE_REPORT)


class TestPriority:
    def test_priority_is_a_separate_value_on_its_own_scale(self):
        """US-16 criterion 1 and DR-02: priority is a separate field, never
        one of the severity values."""
        suggestions = suggest_triage(REFERENCE_REPORT, None, _empty_extraction())

        assert suggestions.priority.value in PRIORITIES
        assert suggestions.priority.value not in SEVERITIES

    @pytest.mark.parametrize(
        ("severity", "priority"),
        [("Critical", "P1"), ("High", "P2"), ("Medium", "P3"), ("Low", "P4")],
    )
    def test_priority_follows_severity_without_urgency(self, severity, priority):
        suggestion = suggest_priority("An ordinary report about the settings page", severity)

        assert suggestion.value == priority
        assert suggestion.reason == f"Follows severity {severity}, so {priority}"

    def test_urgency_raises_priority_one_step(self):
        suggestion = suggest_priority("This is happening in production for every user", "High")

        assert suggestion.value == "P1"
        assert '"production"' in suggestion.reason

    def test_urgency_never_raises_beyond_p1(self):
        suggestion = suggest_priority("urgent", "Critical")

        assert suggestion.value == "P1"


class TestCategory:
    def test_the_suggestion_is_always_from_the_fixed_list(self):
        """US-17 criterion 1."""
        for text in (REFERENCE_REPORT, "", "Something odd", "The API returns error 500"):
            assert suggest_category(text).value in CATEGORIES

    @pytest.mark.parametrize(
        ("text", "category"),
        [
            (REFERENCE_REPORT, "Authentication"),
            ("The save button overlaps the menu in dark mode", "UI"),
            ("The search page is very slow, it takes 30 seconds to load", "Performance"),
            ("The orders endpoint returns status 500 with an empty json body", "API"),
            ("Records were not saved to the database after the migration", "Database"),
            ("Any user can see other users private files, a privacy leak", "Security"),
            ("The date picker only on Safari shows the wrong month", "Compatibility"),
            ("Totals on the invoice are calculated wrong", "Functional"),
        ],
    )
    def test_the_category_matches_the_wording(self, text, category):
        assert suggest_category(text).value == category

    def test_the_reason_names_the_words_that_triggered_it(self):
        suggestion = suggest_category(REFERENCE_REPORT)

        assert suggestion.reason == 'Mentions "login" and "password", so Authentication'

    def test_no_signal_is_functional_and_says_so(self):
        suggestion = suggest_category("Totals on the invoice are calculated wrong")

        assert suggestion.value == "Functional"
        assert suggestion.reason == "No category-specific wording found, so Functional"


class TestReproducibility:
    def test_sometimes_gives_sometimes(self):
        """US-17 criterion 2: "sometimes" in the text gives Reproducibility
        = Sometimes."""
        suggestion = suggest_reproducibility(REFERENCE_REPORT)

        assert suggestion.value == "Sometimes"
        assert suggestion.reason == 'Mentions "sometimes", so Sometimes'

    def test_no_signal_gives_unknown(self):
        """US-17 criterion 3: with no signal in the text, the value is
        Unknown."""
        suggestion = suggest_reproducibility("The export button does not respond")

        assert suggestion.value == "Unknown"

    @pytest.mark.parametrize(
        ("text", "value"),
        [
            ("It happens every time I click save", "Always"),
            ("It failed both times I tried", "Always"),
            ("It happens intermittently", "Sometimes"),
            ("It happens, but not every time", "Sometimes"),
            ("It is not always reproducible", "Sometimes"),
            ("It only happened once last week", "Rarely"),
            ("I cannot reproduce it on my machine", "Unable to reproduce"),
        ],
    )
    def test_each_wording_gives_its_dr04_value(self, text, value):
        """DR-04: Always, Sometimes, Rarely, Unable to reproduce, Unknown."""
        suggestion = suggest_reproducibility(text)

        assert suggestion.value == value
        assert suggestion.value in REPRODUCIBILITY


class TestTriageText:
    def test_explicit_extracted_values_are_read_and_others_are_not(self):
        """An answer to a follow-up question counts; an Inferred paraphrase
        does not."""
        extraction = _empty_extraction(
            frequency=ExtractedField(
                value="every time", source_quote="every time", label=Label.EXPLICIT
            ),
            summary=ExtractedField(
                value="The app crashes", source_quote="closes", label=Label.INFERRED
            ),
            environment=[
                EnvironmentDetail(
                    name="browser", value="Chrome", source_quote="chrome", label=Label.EXPLICIT
                )
            ],
        )

        text = triage_text("Report text", "a log line", extraction)

        assert "every time" in text
        assert "Chrome" in text
        assert "a log line" in text
        assert "The app crashes" not in text

    def test_the_reference_report_gets_all_four_suggestions(self):
        suggestions = suggest_triage(REFERENCE_REPORT, None, _empty_extraction())

        assert suggestions.severity.value == "High"
        assert suggestions.priority.value == "P2"
        assert suggestions.category.value == "Authentication"
        assert suggestions.reproducibility.value == "Sometimes"
