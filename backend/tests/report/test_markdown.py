"""Tests for the Markdown rendering of the generated report
(app/report/markdown.py, US-25 criterion 2: the Markdown renders correctly
on GitHub). Checked as GitHub-flavoured Markdown structure: headings,
ordered and bullet lists, links, escaping and fenced code."""

from app.analysis.schema import EnvironmentDetail, ExtractedField, ExtractionResult, Label
from app.report.markdown import escape, render_markdown
from app.report.template import CandidateEntry, TriageEntry, assemble_report


def _field(value: str | None, label: Label = Label.EXPLICIT) -> ExtractedField:
    if value is None:
        return ExtractedField(value=None, source_quote=None, label=Label.MISSING)
    return ExtractedField(value=value, source_quote=value, label=label)


def _report(logs: str | None = None, candidates=None, **overrides):
    fields: dict[str, object] = {
        "title": _field("Login crashes"),
        "summary": _field("Wrong password closes the app", Label.INFERRED),
        "expected_behaviour": _field("An error message"),
        "actual_behaviour": _field("The app closes"),
        "frequency": _field("every time"),
        "steps": [_field("Open the login page"), _field("Enter a wrong password")],
        "environment": [
            EnvironmentDetail(name="browser", value="Chrome", source_quote="c", label="Explicit"),
            EnvironmentDetail(name="os", value="Windows", source_quote="w", label="Explicit"),
        ],
        "error_messages": [],
    }
    fields.update(overrides)
    triage = {
        "severity": TriageEntry(
            value="High", suggested_value="High", reason="crash", overridden=False
        )
    }
    return assemble_report(ExtractionResult(**fields), triage, candidates, logs)


def test_every_section_is_a_second_level_heading_in_order():
    markdown = render_markdown(_report())

    headings = [line for line in markdown.splitlines() if line.startswith("## ")]
    assert headings[:3] == ["## Title", "## Summary", "## Steps to Reproduce"]
    assert headings[-1] == "## Additional Information"
    assert len(headings) == 13


def test_steps_are_an_ordered_list():
    markdown = render_markdown(_report())

    assert "1. Open the login page\n2. Enter a wrong password" in markdown


def test_several_values_are_a_bullet_list():
    markdown = render_markdown(_report())

    assert "- browser: Chrome\n- os: Windows" in markdown


def test_a_missing_section_reads_not_provided():
    markdown = render_markdown(_report())

    assert "## Error Details\n\n*Not provided*" in markdown


def test_a_value_that_is_not_explicit_keeps_its_label():
    markdown = render_markdown(_report())

    assert "Wrong password closes the app *(Inferred)*" in markdown


def test_a_corpus_candidate_is_a_link_and_an_own_report_is_named_only():
    """An own report's address is an in-app path, meaningless on GitHub."""
    candidates = [
        CandidateEntry(
            title="Login crash",
            url="https://github.com/acme/app/issues/7",
            score=0.91,
            label="Likely duplicate",
            decision="duplicate",
        ),
        CandidateEntry(
            title="My earlier report",
            url="/reports/abc",
            score=0.7,
            label="Possible duplicate",
            own_report=True,
        ),
    ]

    markdown = render_markdown(_report(candidates=candidates))

    assert "- [Login crash](https://github.com/acme/app/issues/7) (Likely duplicate" in markdown
    assert "you marked it a duplicate" in markdown
    assert "- My earlier report (Possible duplicate" in markdown
    assert "](/reports/abc)" not in markdown


def test_logs_go_into_a_fence_longer_than_any_backticks_inside_them():
    logs = "Traceback\n```\nnested fence\n```"

    markdown = render_markdown(_report(logs=logs))

    assert "````\nTraceback\n```\nnested fence\n```\n````" in markdown


def test_text_that_looks_like_markdown_is_shown_literally():
    markdown = render_markdown(_report(title=_field("# not a heading *or bold* <b>")))

    assert "\\# not a heading \\*or bold\\* \\<b\\>" in markdown
    assert escape("a_b|c") == "a\\_b\\|c"


def test_an_issue_body_leaves_the_title_out():
    markdown = render_markdown(_report(), include_title=False)

    assert "## Title" not in markdown
    assert markdown.startswith("## Summary")
