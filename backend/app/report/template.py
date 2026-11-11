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


class GeneratedReport(BaseModel):
    sections: list[ReportSection]


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
    return [
        ReportLine(text=c.title, url=c.url, note=f"{c.label}, similarity {c.score:.2f}")
        for c in candidates
    ]


def assemble_report(
    extraction: ExtractionResult,
    triage: dict[str, TriageEntry],
    candidates: list[CandidateEntry] | None,
    logs: str | None,
) -> GeneratedReport:
    """Every section of the template, in order, from what is known now."""
    additional = _extracted(extraction.frequency)
    if additional:
        additional[0].text = f"Frequency: {additional[0].text}"
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
        sections.append(
            ReportSection(
                key=key,
                heading=heading,
                provided=provided,
                lines=lines if provided else [ReportLine(text=NOT_PROVIDED)],
            )
        )
    return GeneratedReport(sections=sections)
