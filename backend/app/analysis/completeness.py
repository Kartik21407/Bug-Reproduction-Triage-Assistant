"""The completeness score (FR-11, US-13).

Deterministic, like every module here except `client.py`: given an already
verified `ExtractionResult`, decides nothing about labels, only counts what
verification already decided. Essential fields and "present and verified"
both come from `questions.py`, the single place those definitions live, so
the score and the question-filtering guarantee can never quietly disagree
about what counts.
"""

from pydantic import BaseModel

from app.analysis.questions import ESSENTIAL_FIELDS, is_essential_field_missing, is_field_verified
from app.analysis.schema import ExtractionResult


class CompletenessScore(BaseModel):
    """What US-13 shows the user: how many essential fields are present
    and verified, which essential fields are missing entirely (criterion
    2), and which are present but still need confirming because they came
    back Inferred or Unverified (criterion 4)."""

    verified_count: int
    total: int
    missing_fields: list[str]
    needs_confirmation_fields: list[str]


def compute_completeness(result: ExtractionResult) -> CompletenessScore:
    """Counts only essential fields that are present and verified
    (US-13 criterion 3); Inferred and Unverified fields are listed
    separately as needing confirmation, not counted as present
    (criterion 4); a field with nothing extracted at all is listed as
    missing (criterion 2)."""
    missing_fields = []
    needs_confirmation_fields = []
    verified_count = 0

    for field_name in ESSENTIAL_FIELDS:
        if is_essential_field_missing(result, field_name):
            missing_fields.append(field_name)
        elif is_field_verified(result, field_name):
            verified_count += 1
        else:
            needs_confirmation_fields.append(field_name)

    return CompletenessScore(
        verified_count=verified_count,
        total=len(ESSENTIAL_FIELDS),
        missing_fields=missing_fields,
        needs_confirmation_fields=needs_confirmation_fields,
    )
