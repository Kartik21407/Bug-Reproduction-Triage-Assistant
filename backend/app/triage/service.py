"""Stores triage suggestions on a report and applies a person's override.

Kept apart from `rules.py` so the rules stay plain functions of text,
testable without a database, while the two routers that need to refresh
triage (analysis and triage) share one implementation of how it is stored.
"""

from app.analysis.schema import ExtractionResult
from app.models.core import BugReport, User
from app.models.triage import TriageOverride, TriageValue
from app.triage.rules import TRIAGE_FIELDS, suggest_triage


def refresh_triage(report: BugReport, extraction: ExtractionResult) -> None:
    """Recomputes all four suggestions from the report as it stands now.

    A value nobody has changed follows the new suggestion. A value a person
    overrode keeps the person's choice, and only its suggestion and reason
    are refreshed beside it, so re-running analysis never silently undoes a
    decision (US-15 criterion 4). Does not commit; the caller does."""
    suggestions = suggest_triage(report.original_text, report.logs, extraction)
    existing = {row.field_name: row for row in report.triage_values}

    for field_name in TRIAGE_FIELDS:
        suggestion = getattr(suggestions, field_name)
        row = existing.get(field_name)
        if row is None:
            report.triage_values.append(
                TriageValue(
                    field_name=field_name,
                    suggested_value=suggestion.value,
                    reason=suggestion.reason,
                    value=suggestion.value,
                    overridden=False,
                )
            )
            continue
        row.suggested_value = suggestion.value
        row.reason = suggestion.reason
        if row.overridden:
            row.overridden = row.value != suggestion.value
        else:
            row.value = suggestion.value

    _sync_severity(report)


def apply_override(report: BugReport, user: User, field_name: str, value: str) -> None:
    """Sets one triage value to what a person chose, flags it as overridden
    when it differs from the suggestion, and records who changed it from
    what to what (FR-15). Choosing the value already in force records
    nothing. Does not commit; the caller does."""
    row = next(row for row in report.triage_values if row.field_name == field_name)
    if row.value == value:
        return

    report.triage_overrides.append(
        TriageOverride(user_id=user.id, field_name=field_name, old_value=row.value, new_value=value)
    )
    row.value = value
    row.overridden = value != row.suggested_value
    _sync_severity(report)


def _sync_severity(report: BugReport) -> None:
    """`bug_reports.severity` mirrors the severity in force, so the history
    list's severity filter (US-06) reflects triage without a join."""
    severity = next((row for row in report.triage_values if row.field_name == "severity"), None)
    report.severity = severity.value if severity else None
