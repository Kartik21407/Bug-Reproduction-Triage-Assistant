"""Tests for the fixed report template (app/report/template.py): US-23,
FR-19, DR-07. A plain function, so no database and no model call."""

from app.analysis.schema import EnvironmentDetail, ExtractedField, ExtractionResult, Label
from app.report.template import (
    NO_SIMILAR_ISSUES,
    NOT_PROVIDED,
    CandidateEntry,
    TriageEntry,
    assemble_report,
)

US_23_SECTIONS = [
    "Title",
    "Summary",
    "Steps to Reproduce",
    "Expected",
    "Actual",
    "Environment",
    "Error Details",
    "Severity",
    "Priority",
    "Category",
    "Reproducibility",
    "Possible Duplicates",
    "Additional Information",
]


def _missing() -> ExtractedField:
    return ExtractedField(value=None, source_quote=None, label=Label.MISSING)


def _explicit(value: str) -> ExtractedField:
    return ExtractedField(value=value, source_quote=value, label=Label.EXPLICIT)


def _extraction(**overrides: object) -> ExtractionResult:
    fields: dict[str, object] = {
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


def _triage(**overrides: TriageEntry) -> dict[str, TriageEntry]:
    triage = {
        "severity": TriageEntry(
            value="High",
            suggested_value="High",
            reason='Mentions "crashes", so High',
            overridden=False,
        ),
        "priority": TriageEntry(
            value="P2",
            suggested_value="P2",
            reason="Follows severity High, so P2",
            overridden=False,
        ),
        "category": TriageEntry(
            value="UI", suggested_value="UI", reason='Mentions "button", so UI', overridden=False
        ),
        "reproducibility": TriageEntry(
            value="Unknown",
            suggested_value="Unknown",
            reason="No wording about how often it happens, so Unknown",
            overridden=False,
        ),
    }
    triage.update(overrides)
    return triage


def _section(report, heading: str):
    return next(section for section in report.sections if section.heading == heading)


class TestSections:
    def test_every_section_appears_in_the_stated_order(self):
        """US-23 criterion 1."""
        report = assemble_report(_extraction(), _triage(), None, None)

        assert [section.heading for section in report.sections] == US_23_SECTIONS

    def test_every_missing_value_reads_not_provided(self):
        """US-23 criterion 2: missing values appear as "Not provided"."""
        report = assemble_report(_extraction(), {}, None, None)

        for section in report.sections:
            assert section.provided is False
            assert [line.text for line in section.lines] == [NOT_PROVIDED]

    def test_extracted_values_keep_their_labels(self):
        """An Inferred value is never presented as confirmed (conflict C1)."""
        extraction = _extraction(
            title=_explicit("Login crashes on a wrong password"),
            summary=ExtractedField(
                value="Login closes instead of showing an error",
                source_quote="application closes",
                label=Label.INFERRED,
            ),
        )

        report = assemble_report(extraction, _triage(), None, None)

        assert _section(report, "Title").lines[0].label == Label.EXPLICIT
        assert _section(report, "Summary").lines[0].label == Label.INFERRED

    def test_steps_keep_their_order(self):
        extraction = _extraction(
            steps=[_explicit("Open the login page"), _explicit("Enter a wrong password")]
        )

        report = assemble_report(extraction, _triage(), None, None)

        assert [line.text for line in _section(report, "Steps to Reproduce").lines] == [
            "Open the login page",
            "Enter a wrong password",
        ]

    def test_environment_details_show_name_and_value(self):
        extraction = _extraction(
            environment=[
                EnvironmentDetail(
                    name="browser", value="Chrome 129", source_quote="Chrome", label=Label.EXPLICIT
                )
            ]
        )

        report = assemble_report(extraction, _triage(), None, None)

        assert _section(report, "Environment").lines[0].text == "browser: Chrome 129"

    def test_triage_values_carry_their_reason(self):
        report = assemble_report(_extraction(), _triage(), None, None)

        severity = _section(report, "Severity").lines[0]
        assert severity.text == "High"
        assert severity.note == 'Suggested: Mentions "crashes", so High'

    def test_an_overridden_value_says_a_person_changed_it(self):
        triage = _triage(
            severity=TriageEntry(value="Low", suggested_value="High", reason="x", overridden=True)
        )

        report = assemble_report(_extraction(), triage, None, None)

        assert _section(report, "Severity").lines[0].note == "Changed by a person; suggested High"

    def test_frequency_and_logs_go_under_additional_information(self):
        extraction = _extraction(frequency=_explicit("every time"))

        report = assemble_report(extraction, _triage(), None, "Traceback (most recent call last)")

        lines = _section(report, "Additional Information").lines
        assert lines[0].text == "Frequency: every time"
        assert lines[1].text == "Traceback (most recent call last)"
        assert lines[1].preformatted is True


class TestDuplicates:
    def test_candidates_appear_as_links(self):
        """US-23 criterion 3: duplicate candidates appear as links."""
        candidates = [
            CandidateEntry(
                title="Login crash",
                url="https://github.com/acme/app/issues/7",
                score=0.912,
                label="Likely duplicate",
            )
        ]

        report = assemble_report(_extraction(), _triage(), candidates, None)

        line = _section(report, "Possible Duplicates").lines[0]
        assert line.text == "Login crash"
        assert line.url == "https://github.com/acme/app/issues/7"
        assert line.note == "Likely duplicate, similarity 0.91"

    def test_no_search_yet_reads_not_provided(self):
        report = assemble_report(_extraction(), _triage(), None, None)

        assert _section(report, "Possible Duplicates").lines[0].text == NOT_PROVIDED

    def test_a_search_with_no_result_says_so(self):
        """A search that found nothing is a result, not a missing value."""
        report = assemble_report(_extraction(), _triage(), [], None)

        assert _section(report, "Possible Duplicates").lines[0].text == NO_SIMILAR_ISSUES
