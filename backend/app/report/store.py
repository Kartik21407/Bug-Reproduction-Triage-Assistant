"""How a report's extracted fields and environment details are stored, read
back and corrected (ADR-011, ADR-027).

Every row is either the model's (`source="model"`) or a person's
(`source="user"`). A person's version of a field never overwrites the
model's: it is stored beside it and always wins when the report is read.
That is what lets re-analysis refresh everything the model produced while
keeping every correction, answer and edit a person made, and what lets
"Reset to suggested" (US-24 criterion 3) simply delete the person's version
so the model's shows again.

- A scalar field (title, summary, expected and actual behaviour, frequency)
  reads as the person's row if there is one, else the model's.
- A list field (steps, error messages) is the person's list as a whole once
  they have touched it, else the model's. Adding one item copies the
  current list over first, so nothing the person saw disappears.
- Environment details are per name: a person's row for a name replaces the
  model's detail of that name, or hides it when marked `removed`; details
  the person added by hand are listed after the model's.

Nothing here commits; the caller does.
"""

from app.analysis.schema import EnvironmentDetail as EnvironmentDetailValue
from app.analysis.schema import ExtractedField as ExtractedFieldValue
from app.analysis.schema import ExtractionResult, Label
from app.models.analysis import EnvironmentDetail as EnvironmentDetailRow
from app.models.analysis import ExtractedField as ExtractedFieldRow
from app.models.core import BugReport

MODEL = "model"
USER = "user"

SCALAR_FIELDS = ("title", "summary", "expected_behaviour", "actual_behaviour", "frequency")
LIST_FIELDS = ("steps", "error_messages")
# A free-text note a person can add under Additional Information (US-24).
# Only ever a person's row; the model never writes one.
NOTE_FIELD = "additional_information"
EDITABLE_FIELDS = (*SCALAR_FIELDS, *LIST_FIELDS, "environment", NOTE_FIELD)

_USER_REASON = "Written by the user"


def _rows(report: BugReport, field_name: str, source: str) -> list[ExtractedFieldRow]:
    rows = [r for r in report.extracted_fields if r.field_name == field_name and r.source == source]
    return sorted(rows, key=lambda row: row.position or 0)


def _to_value(row: ExtractedFieldRow) -> ExtractedFieldValue:
    return ExtractedFieldValue(
        value=row.value,
        source_quote=row.source_quote,
        label=Label(row.label),
        confidence=row.confidence,
        reason=row.reason,
    )


def _missing() -> ExtractedFieldValue:
    return ExtractedFieldValue(value=None, source_quote=None, label=Label.MISSING)


def _scalar(report: BugReport, field_name: str) -> ExtractedFieldValue:
    for source in (USER, MODEL):
        rows = _rows(report, field_name, source)
        if rows:
            return _to_value(rows[0])
    return _missing()


def _list(report: BugReport, field_name: str) -> list[ExtractedFieldValue]:
    user_rows = _rows(report, field_name, USER)
    rows = user_rows if user_rows else _rows(report, field_name, MODEL)
    # An empty list a person saved is kept as one row with no value, so the
    # field still counts as theirs; it never reads back as an entry.
    return [_to_value(row) for row in rows if row.value is not None]


def _environment(report: BugReport) -> list[EnvironmentDetailValue]:
    model = [d for d in report.environment_details if d.source == MODEL]
    user = {d.name: d for d in report.environment_details if d.source == USER}
    shown: list[EnvironmentDetailRow] = []
    for detail in model:
        chosen = user.get(detail.name, detail)
        if not chosen.removed and chosen not in shown:
            shown.append(chosen)
    model_names = {d.name for d in model}
    shown += [d for d in user.values() if d.name not in model_names and not d.removed]
    return [
        EnvironmentDetailValue(
            name=d.name, value=d.value, source_quote=d.source_quote, label=Label(d.label)
        )
        for d in shown
    ]


def read_extraction(report: BugReport) -> ExtractionResult:
    """The report's fields as they stand now, a person's corrections
    included."""
    return ExtractionResult(
        title=_scalar(report, "title"),
        summary=_scalar(report, "summary"),
        expected_behaviour=_scalar(report, "expected_behaviour"),
        actual_behaviour=_scalar(report, "actual_behaviour"),
        frequency=_scalar(report, "frequency"),
        steps=_list(report, "steps"),
        environment=_environment(report),
        error_messages=_list(report, "error_messages"),
    )


def read_note(report: BugReport) -> str | None:
    rows = _rows(report, NOTE_FIELD, USER)
    return rows[0].value if rows else None


def edited_fields(report: BugReport) -> set[str]:
    """Every field a person has their own version of."""
    edited = {r.field_name for r in report.extracted_fields if r.source == USER}
    if any(d.source == USER for d in report.environment_details):
        edited.add("environment")
    return edited


def replace_model_result(report: BugReport, extraction: ExtractionResult) -> None:
    """Re-analysis: replaces every row the model produced with the new
    result, and touches nothing a person wrote. The model's version of a
    field a person corrected is still refreshed, so "Reset to suggested"
    always restores the latest suggestion."""
    report.extracted_fields[:] = [r for r in report.extracted_fields if r.source == USER]
    report.environment_details[:] = [d for d in report.environment_details if d.source == USER]

    for field_name in SCALAR_FIELDS:
        report.extracted_fields.append(
            _model_row(field_name, None, getattr(extraction, field_name))
        )
    for field_name in LIST_FIELDS:
        for position, entry in enumerate(getattr(extraction, field_name)):
            report.extracted_fields.append(_model_row(field_name, position, entry))
    for detail in extraction.environment:
        report.environment_details.append(
            EnvironmentDetailRow(
                name=detail.name,
                value=detail.value,
                source_quote=detail.source_quote,
                label=str(detail.label),
                source=MODEL,
            )
        )


def _model_row(
    field_name: str, position: int | None, value: ExtractedFieldValue
) -> ExtractedFieldRow:
    return ExtractedFieldRow(
        field_name=field_name,
        position=position,
        value=value.value,
        source_quote=value.source_quote,
        label=str(value.label),
        confidence=value.confidence,
        reason=value.reason,
        source=MODEL,
    )


def _user_row(field_name: str, position: int | None, value: str | None) -> ExtractedFieldRow:
    """A person's own statement: Explicit, with itself as the source quote.
    An empty value means the person cleared the field, so it reads as
    Missing ("Not provided") rather than as an empty string."""
    if value is not None and value.strip() == "":
        value = None
    return ExtractedFieldRow(
        field_name=field_name,
        position=position,
        value=value,
        source_quote=value,
        label=str(Label.EXPLICIT if value is not None else Label.MISSING),
        reason=_USER_REASON if value is not None else None,
        source=USER,
    )


def _drop_user_rows(report: BugReport, field_name: str) -> None:
    report.extracted_fields[:] = [
        r for r in report.extracted_fields if not (r.field_name == field_name and r.source == USER)
    ]


def set_scalar(report: BugReport, field_name: str, value: str | None) -> None:
    """A person's version of a scalar field, or of the note."""
    _drop_user_rows(report, field_name)
    report.extracted_fields.append(_user_row(field_name, None, value))
    if field_name == "title":
        report.title = read_extraction(report).title.value


def set_list(report: BugReport, field_name: str, values: list[str]) -> None:
    """A person's version of a whole list field. Blank items are dropped;
    an empty list is kept as the person's choice."""
    _drop_user_rows(report, field_name)
    items = [v for v in values if v.strip()]
    if not items:
        report.extracted_fields.append(_user_row(field_name, 0, None))
        return
    for position, item in enumerate(items):
        report.extracted_fields.append(_user_row(field_name, position, item))


def append_to_list(report: BugReport, field_name: str, value: str) -> None:
    """Adds one item a person stated (an answered follow-up question) to the
    end of the list as they currently see it."""
    current = [entry.value for entry in _list(report, field_name) if entry.value]
    set_list(report, field_name, [*current, value])


def set_environment_detail(report: BugReport, name: str, value: str) -> None:
    """A person's own value for one environment detail, corrected or new."""
    report.environment_details[:] = [
        d for d in report.environment_details if not (d.source == USER and d.name == name)
    ]
    report.environment_details.append(
        EnvironmentDetailRow(
            name=name, value=value, source_quote=value, label=str(Label.EXPLICIT), source=USER
        )
    )


def add_stated_environment(report: BugReport, details: list[EnvironmentDetailValue]) -> None:
    """Details extracted from a person's own free-text answer (US-33
    criterion 4). They keep the label verification gave them, and are the
    person's, so re-analysis keeps them. A name already shown is skipped."""
    shown = {d.name for d in _environment(report)}
    for detail in details:
        if detail.name in shown:
            continue
        shown.add(detail.name)
        report.environment_details.append(
            EnvironmentDetailRow(
                name=detail.name,
                value=detail.value,
                source_quote=detail.source_quote,
                label=str(detail.label),
                source=USER,
            )
        )


def remove_environment_detail(report: BugReport, name: str) -> None:
    """Hides a detail, and keeps it hidden through re-analysis."""
    report.environment_details[:] = [
        d for d in report.environment_details if not (d.source == USER and d.name == name)
    ]
    if any(d.name == name for d in report.environment_details):
        report.environment_details.append(
            EnvironmentDetailRow(
                name=name,
                value="",
                source_quote="",
                label=str(Label.MISSING),
                source=USER,
                removed=True,
            )
        )


def set_environment(report: BugReport, details: list[tuple[str, str]]) -> None:
    """A person's version of the whole environment list: every detail given
    is theirs, and every shown detail not given is removed."""
    given = dict(details)
    for current in _environment(report):
        if current.name not in given:
            remove_environment_detail(report, current.name)
    for name, value in given.items():
        set_environment_detail(report, name, value)


def reset_field(report: BugReport, field_name: str) -> None:
    """Restores the suggested version (US-24 criterion 3) by deleting the
    person's own rows for the field."""
    if field_name == "environment":
        report.environment_details[:] = [d for d in report.environment_details if d.source != USER]
    else:
        _drop_user_rows(report, field_name)
    if field_name == "title":
        report.title = read_extraction(report).title.value
