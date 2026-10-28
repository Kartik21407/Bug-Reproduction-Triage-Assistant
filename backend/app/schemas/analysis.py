"""Response shapes for the analysis endpoints (`docs/design.md` section 7.3).

Nested models mostly come straight from `app.analysis`: `MaskedItem`,
`ExtractionResult` and `CompletenessScore` are already plain Pydantic
models with no SQLAlchemy involved, so they are reused here rather than
redeclared. `PersistedQuestion` is the one exception: the domain model
`app.analysis.questions.FollowUpQuestion` deliberately has no `id`, since
it exists before persistence too (inside `filter_questions`, which never
touches the database); once a question has been persisted, the API needs
its id to let the frontend answer it, so that one additional field is
declared here instead of on the domain model.
"""

from datetime import datetime

from pydantic import BaseModel

from app.analysis.completeness import CompletenessScore
from app.analysis.masking import MaskedItem
from app.analysis.schema import ExtractionResult


class PersistedQuestion(BaseModel):
    """A follow-up question as read back after persistence: everything
    `FollowUpQuestion` carries, plus the row id an answer is posted to, and
    the answer itself once given."""

    id: str
    field: str
    question: str
    reason: str
    model_proposed: bool
    answer: str | None = None
    answered_at: datetime | None = None


class AnalyzeResult(BaseModel):
    """What `POST /api/reports/{report_id}/analyze` returns: what was
    masked before anything was sent to the model, the verified extraction,
    and the filtered follow-up questions, each carrying the id it was
    persisted under. `steps_flagged_for_review` is true when more than
    seven steps were extracted (US-09 criterion 5); the full list is
    always returned regardless, never shortened. See `app/api/analysis.py`."""

    masked_items: list[MaskedItem]
    extraction: ExtractionResult
    questions: list[PersistedQuestion]
    steps_flagged_for_review: bool


class AnalysisRead(BaseModel):
    """What `GET /api/reports/{report_id}/analysis` returns: the persisted
    extraction and follow-up questions read back, plus the completeness
    score (US-13) and the step-count review flag (US-09 criterion 5). No
    `masked_items`, since masking is only relevant to the single `analyze`
    call that produced this result, not to reading it back later."""

    extraction: ExtractionResult
    questions: list[PersistedQuestion]
    completeness: CompletenessScore
    steps_flagged_for_review: bool


class AnalyzeRequest(BaseModel):
    """Optional adjustments to masking, applied before analysis runs
    (US-32 criteria 2, 3 and 5). `restore_values` are detected items the
    user says are false positives, by their exact original text;
    `manual_mask_values` are values the user marks by hand, every
    occurrence of which is masked too. Both default to empty, so a plain
    `analyze` call with no body behaves exactly as before."""

    restore_values: list[str] = []
    manual_mask_values: list[str] = []


class AnswerQuestionRequest(BaseModel):
    """The user's answer to one follow-up question (US-14 criterion 5)."""

    answer: str


class EnvironmentCorrection(BaseModel):
    """One environment detail the user is correcting or adding by hand
    (US-33 criterion 1)."""

    name: str
    value: str


class EnvironmentReviewRequest(BaseModel):
    """US-33: corrections and removals to the captured environment
    details, and the answer to the one open question about anything else
    relevant (criteria 1 and 2), or what the reporter was using when
    nothing was captured at all (criterion 3). `additional_details` is
    passed through extraction and verification the same way the original
    report was, not stored as free text (criterion 4)."""

    corrections: list[EnvironmentCorrection] = []
    removals: list[str] = []
    additional_details: str | None = None
