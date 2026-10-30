"""Follow-up question filtering (FR-32, US-14, ADR-016).

The model proposes questions with a stated reason; this module is what
turns that proposal into what the user actually sees. Three rules, none of
them the model's to decide: a question for a field that is already
Explicit is dropped, a missing essential field always gets a question even
if the model did not propose one, and at most six are shown at once.

Nothing here calls a model, the same constraint `verification.py` and
`masking.py` follow: `filter_questions` takes the model's raw proposals and
an already-verified `ExtractionResult` as plain data.
"""

from pydantic import BaseModel

from app.analysis.schema import ExtractionResult, Label, RawFollowUpQuestion

MAX_QUESTIONS = 6

# The five essential fields (US-13 criterion 1). "environment" is not a
# field on ExtractionResult itself, it is the `environment` list; it is
# still named here the same way the model names it in a proposed question.
ESSENTIAL_FIELDS = ("expected_behaviour", "actual_behaviour", "frequency", "steps", "environment")

# Plain-language fallback questions, used only when an essential field is
# missing and the model did not propose a question about it. The
# essential-field guarantee does not depend on the model, so code needs its
# own wording to fall back on (ADR-016 consequences).
_FALLBACK_QUESTIONS: dict[str, tuple[str, str]] = {
    "expected_behaviour": (
        "What did you expect to happen?",
        "Expected behaviour is one of the essential fields and nothing was extracted for it.",
    ),
    "actual_behaviour": (
        "What actually happened instead?",
        "Actual behaviour is one of the essential fields and nothing was extracted for it.",
    ),
    "frequency": (
        "How often does this happen: always, sometimes, or just once?",
        "Frequency is one of the essential fields and nothing was extracted for it.",
    ),
    "steps": (
        "What steps led up to this happening?",
        "Reproduction steps are one of the essential fields and none were extracted.",
    ),
    "environment": (
        "What device, browser or operating system were you using?",
        "At least one environment detail is essential and none were extracted.",
    ),
}


class FollowUpQuestion(BaseModel):
    """One question as shown to the user: the model's proposal if there
    was one and it survived filtering, or code's own fallback wording for
    a missing essential field the model did not ask about."""

    field: str
    question: str
    reason: str
    model_proposed: bool


def is_field_verified(result: ExtractionResult, field_name: str) -> bool:
    """True when the named field is 'present and verified' (US-14
    criterion 2): Explicit for a scalar field, or at least one Explicit
    entry for a list field. Inferred and Unverified do not count, the same
    rule the completeness score uses (US-13 criterion 4)."""
    if field_name in ("steps", "environment", "error_messages"):
        entries = getattr(result, field_name)
        return any(entry.label == Label.EXPLICIT for entry in entries)

    field = getattr(result, field_name, None)
    if field is None:
        return False
    return field.label == Label.EXPLICIT


def is_essential_field_missing(result: ExtractionResult, field_name: str) -> bool:
    """True when nothing at all was extracted for an essential field:
    Missing for a scalar field, an empty list for steps or environment."""
    if field_name in ("steps", "environment"):
        return len(getattr(result, field_name)) == 0

    field = getattr(result, field_name)
    return field.label == Label.MISSING


def filter_questions(
    raw_questions: list[RawFollowUpQuestion], result: ExtractionResult
) -> list[FollowUpQuestion]:
    """Filters the model's proposed questions against an already-verified
    extraction result (FR-32, ADR-016):

    1. A question for a field that is already present and verified is
       dropped (US-14 criterion 2).
    2. A missing essential field always gets a question, using the
       model's proposal if it made one, or a fallback if it did not
       (US-14 criterion 3).
    3. At most six questions are shown, essential ones first, so the
       guarantee in step 2 is never pushed out by the cap
       (US-14 criterion 4).
    """
    proposed = [q for q in raw_questions if not is_field_verified(result, q.field)]

    missing_essential = [f for f in ESSENTIAL_FIELDS if is_essential_field_missing(result, f)]

    essential_questions: list[FollowUpQuestion] = []
    for field in missing_essential:
        match = next((q for q in proposed if q.field == field), None)
        if match is not None:
            essential_questions.append(
                FollowUpQuestion(
                    field=match.field,
                    question=match.question,
                    reason=match.reason,
                    model_proposed=True,
                )
            )
        else:
            question, reason = _FALLBACK_QUESTIONS[field]
            essential_questions.append(
                FollowUpQuestion(
                    field=field, question=question, reason=reason, model_proposed=False
                )
            )

    other_questions = [
        FollowUpQuestion(field=q.field, question=q.question, reason=q.reason, model_proposed=True)
        for q in proposed
        if q.field not in missing_essential
    ]

    return (essential_questions + other_questions)[:MAX_QUESTIONS]
