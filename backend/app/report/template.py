"""The fixed report template (FR-19, US-23).

`assemble_report` is a plain function of values already verified, triaged
and searched: it adds nothing of its own. Sections always appear, in the
order US-23 criterion 1 lists them; a section with nothing to show reads
"Not provided" (criterion 2, DR-07), never a guessed value; duplicate
candidates carry their link (criterion 3). An extracted value that is not
Explicit keeps its label, so an Inferred value is never presented as
confirmed.
"""

from pydantic import BaseModel

from app.analysis.schema import ExtractedField, ExtractionResult, Label

NOT_PROVIDED = "Not provided"
NO_SIMILAR_ISSUES = "No similar issues found"


class ReportLine(BaseModel):
    text: str
    # The verification label of an extracted value. None for anything that
    # is not an extracted value (triage, duplicates, logs, "Not provided").
    label: Label | None = None
    # A short explanation shown beside the line: a triage reason, or a
    # duplicate candidate's label and score.
    note: str | None = None
    url: str | None = None
    # True for raw log output, which is shown unmodified in monospace.
    preformatted: bool = False


class ReportSection(BaseModel):
    key: str
    heading: str
    provided: bool
    lines: list[ReportLine]
    # The fields this section is built from and can be edited through
    # (US-24 criterion 1). Possible Duplicates has none: a person acts on
    # it by confirming or rejecting a candidate instead (US-21).
    fields: list[str] = []
    # True when a person's own version is in force, so "Reset to suggested"
    # has something to restore (US-24 criterion 3).
    edited: bool = False


class EnvironmentValue(BaseModel):
    name: str
    value: str


class EditableValues(BaseModel):
    """The current value of every editable field, for an editor to start
    from."""

    title: str | None
    summary: str | None
    expected_behaviour: str | None
    actual_behaviour: str | None
    frequency: str | None
    additional_information: str | None
    steps: list[str]
    error_messages: list[str]
    environment: list[EnvironmentValue]


class GeneratedReport(BaseModel):
    sections: list[ReportSection]
    values: EditableValues


class TriageEntry(BaseModel):
    value: str
    suggested_value: str
    reason: str
    overridden: bool


class CandidateEntry(BaseModel):
    title: str
    url: str
    score: float
    label: str
    # "duplicate" or "not_duplicate" once a person decided (US-21).
    decision: str | None = None
    # One of the user's own earlier reports: its url is an in-app path, not
    # a public address, so Markdown names it rather than linking it.
    own_report: bool = False


# US-23 criterion 1, in its order.
SECTIONS = (
    ("title", "Title"),
    ("summary", "Summary"),
    ("steps", "Steps to Reproduce"),
    ("expected", "Expected"),
    ("actual", "Actual"),
    ("environment", "Environment"),
    ("error_details", "Error Details"),
    ("severity", "Severity"),
    ("priority", "Priority"),
    ("category", "Category"),
    ("reproducibility", "Reproducibility"),
    ("duplicates", "Possible Duplicates"),
    ("additional", "Additional Information"),
)

# Which editable fields each section is built from (US-24).
SECTION_FIELDS: dict[str, list[str]] = {
    "title": ["title"],
    "summary": ["summary"],
    "steps": ["steps"],
    "expected": ["expected_behaviour"],
    "actual": ["actual_behaviour"],
    "environment": ["environment"],
    "error_details": ["error_messages"],
    "severity": ["severity"],
    "priority": ["priority"],
    "category": ["category"],
    "reproducibility": ["reproducibility"],
    "duplicates": [],
    "additional": ["frequency", "additional_information"],
}
_TRIAGE_SECTIONS = ("severity", "priority", "category", "reproducibility")
_DECISION_NOTES = {
    "duplicate": "you marked it a duplicate",
    "not_duplicate": "you marked it not a duplicate",
}


def _extracted(field: ExtractedField) -> list[ReportLine]:
    if field.label == Label.MISSING or not field.value:
        return []
    return [ReportLine(text=field.value, label=field.label)]


def _triage(entry: TriageEntry | None) -> list[ReportLine]:
    if entry is None:
        return []
    if entry.overridden:
        note = f"Changed by a person; suggested {entry.suggested_value}"
    else:
        note = f"Suggested: {entry.reason}"
    return [ReportLine(text=entry.value, note=note)]


def _duplicates(candidates: list[CandidateEntry] | None) -> list[ReportLine] | None:
    """None when no search has run, so the section reads "Not provided";
    an explicit line when a search ran and found nothing above the
    threshold, since that is a result, not a missing value."""
    if candidates is None:
        return None
    if not candidates:
        return [ReportLine(text=NO_SIMILAR_ISSUES)]
    lines = []
    for c in candidates:
        note = f"{c.label}, similarity {c.score:.2f}"
        if c.decision in _DECISION_NOTES:
            note += f"; {_DECISION_NOTES[c.decision]}"
        lines.append(ReportLine(text=c.title, url=c.url, note=note))
    return lines


def _values(extraction: ExtractionResult, note: str | None) -> EditableValues:
    return EditableValues(
        title=extraction.title.value,
        summary=extraction.summary.value,
        expected_behaviour=extraction.expected_behaviour.value,
        actual_behaviour=extraction.actual_behaviour.value,
        frequency=extraction.frequency.value,
        additional_information=note,
        steps=[s.value for s in extraction.steps if s.value],
        error_messages=[e.value for e in extraction.error_messages if e.value],
        environment=[
            EnvironmentValue(name=d.name, value=d.value) for d in extraction.environment if d.value
        ],
    )


def assemble_report(
    extraction: ExtractionResult,
    triage: dict[str, TriageEntry],
    candidates: list[CandidateEntry] | None,
    logs: str | None,
    note: str | None = None,
    edited_fields: set[str] | None = None,
) -> GeneratedReport:
    """Every section of the template, in order, from what is known now.
    `note` is a person's own Additional Information text, and
    `edited_fields` the fields they have their own version of."""
    edited_fields = edited_fields or set()
    additional = _extracted(extraction.frequency)
    if additional:
        additional[0].text = f"Frequency: {additional[0].text}"
    if note:
        additional.append(ReportLine(text=note, label=Label.EXPLICIT))
    if logs:
        additional.append(ReportLine(text=logs, preformatted=True))

    duplicate_lines = _duplicates(candidates)

    content: dict[str, list[ReportLine]] = {
        "title": _extracted(extraction.title),
        "summary": _extracted(extraction.summary),
        "steps": [line for step in extraction.steps for line in _extracted(step)],
        "expected": _extracted(extraction.expected_behaviour),
        "actual": _extracted(extraction.actual_behaviour),
        "environment": [
            ReportLine(text=f"{detail.name}: {detail.value}", label=detail.label)
            for detail in extraction.environment
            if detail.label != Label.MISSING and detail.value
        ],
        "error_details": [
            line for error in extraction.error_messages for line in _extracted(error)
        ],
        "severity": _triage(triage.get("severity")),
        "priority": _triage(triage.get("priority")),
        "category": _triage(triage.get("category")),
        "reproducibility": _triage(triage.get("reproducibility")),
        "duplicates": duplicate_lines or [],
        "additional": additional,
    }

    sections = []
    for key, heading in SECTIONS:
        lines = content[key]
        provided = bool(lines)
        if key in _TRIAGE_SECTIONS:
            entry = triage.get(key)
            edited = bool(entry and entry.overridden)
        else:
            edited = any(field in edited_fields for field in SECTION_FIELDS[key])
        sections.append(
            ReportSection(
                key=key,
                heading=heading,
                provided=provided,
                lines=lines if provided else [ReportLine(text=NOT_PROVIDED)],
                fields=SECTION_FIELDS[key],
                edited=edited,
            )
        )
    return GeneratedReport(sections=sections, values=_values(extraction, note))
