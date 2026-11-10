"""Runs the extraction pipeline on a report and persists the result
(`docs/design.md` section 6.5 steps 1 to 6), reads a persisted result back
with its completeness score (US-13), previews and adjusts masking (US-32),
answers a follow-up question (US-14), and reviews environment details
(US-33)."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, status
from sqlalchemy.orm.session import Session

from app.analysis.client import extract
from app.analysis.completeness import compute_completeness
from app.analysis.masking import MaskingResult, apply_masking, detect_masked_items
from app.analysis.masking import mask_literal_occurrences as mask_every_occurrence
from app.analysis.questions import FollowUpQuestion as FilteredQuestion
from app.analysis.questions import filter_questions
from app.analysis.schema import EnvironmentDetail as EnvironmentDetailValue
from app.analysis.schema import ExtractedField as ExtractedFieldValue
from app.analysis.schema import ExtractionResult, Label
from app.analysis.verification import (
    normalise_environment_name,
    steps_need_review,
    verify_extraction,
)
from app.api.reports import get_owned_report_or_404
from app.deps import CurrentUser, DbSession
from app.models.analysis import EnvironmentDetail as EnvironmentDetailRow
from app.models.analysis import ExtractedField as ExtractedFieldRow
from app.models.analysis import FollowUpQuestion as FollowUpQuestionRow
from app.models.core import BugReport
from app.schemas.analysis import (
    AnalysisRead,
    AnalyzeRequest,
    AnalyzeResult,
    AnswerQuestionRequest,
    EnvironmentReviewRequest,
    PersistedQuestion,
)
from app.triage.service import refresh_triage

router = APIRouter(prefix="/reports", tags=["analysis"])

# Scalar fields, in the order app.analysis.schema.ExtractionResult declares
# them. List fields (steps, environment, error_messages) are handled
# separately, since each entry needs its own row.
_SCALAR_FIELDS = ("title", "summary", "expected_behaviour", "actual_behaviour", "frequency")


@router.post("/{report_id}/mask", response_model=MaskingResult)
def preview_masking(report_id: UUID, current_user: CurrentUser, db: DbSession) -> MaskingResult:
    """Detects likely secrets in the report's original text and previews
    the masked copy, without running analysis (US-32 criterion 1). Always
    returns `200` with `items: []` when nothing is detected, rather than a
    different shape, so a review is available either way
    (US-32 criterion 4). 404 rules match every other report endpoint
    (NFR-15)."""
    report = get_owned_report_or_404(db, current_user, report_id)
    items = detect_masked_items(report.original_text)
    return MaskingResult(masked_text=apply_masking(report.original_text, items), items=items)


@router.post("/{report_id}/analyze", response_model=AnalyzeResult)
def analyze_report(
    report_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    body: AnalyzeRequest = Body(default_factory=AnalyzeRequest),
) -> AnalyzeResult:
    """Masks the report's original text and its logs (if any), applying
    any review adjustments the user made first, sends the masked copy to
    the model, verifies every field, filters the proposed follow-up
    questions, persists the result, and moves the report to Analysed.
    404 rules match every other report endpoint (NFR-15).

    The logs field is appended under its own heading so error messages
    and stack-trace lines in it are extracted too, not just the
    description (US-11 criterion 2).

    Verification runs against the masked text, not the original: a
    source_quote is only ever trustworthy against the text the model was
    actually given, and only the masked copy is ever sent anywhere
    (FR-29, US-32 criterion 5)."""
    report = get_owned_report_or_404(db, current_user, report_id)

    items = detect_masked_items(report.original_text)
    items = [item for item in items if item.original_text not in body.restore_values]
    for value in body.manual_mask_values:
        items = mask_every_occurrence(report.original_text, items, value)
    masking_result = MaskingResult(
        masked_text=apply_masking(report.original_text, items), items=items
    )

    model_input = masking_result.masked_text
    if report.logs:
        # US-11 criterion 2: stack-trace lines from the log field are
        # extracted too, not just the description. Masked the same way as
        # the description (FR-29, NFR-06), and appended under its own
        # heading so the model can tell narrative from raw log output.
        log_items = detect_masked_items(report.logs)
        model_input += "\n\n--- Logs ---\n" + apply_masking(report.logs, log_items)
        masking_result.items += log_items

    raw = extract(model_input)
    extraction = verify_extraction(raw, model_input)
    questions = filter_questions(raw.proposed_questions, extraction)

    _persist_analysis(db, report, extraction, questions)

    return AnalyzeResult(
        masked_items=masking_result.items,
        extraction=extraction,
        questions=_read_questions(report),
        steps_flagged_for_review=steps_need_review(extraction.steps),
    )


@router.get("/{report_id}/analysis", response_model=AnalysisRead)
def read_analysis(report_id: UUID, current_user: CurrentUser, db: DbSession) -> AnalysisRead:
    """Reads back whatever was persisted by the most recent `analyze` call:
    the extraction, the follow-up questions, and the completeness score
    (US-13). A report that has never been analysed reads back as the same
    all-Missing shape `verify_extraction` produces for an empty response,
    not an error (FR-28's safe-fallback shape, extended to reading). 404
    rules match every other report endpoint (NFR-15)."""
    report = get_owned_report_or_404(db, current_user, report_id)

    extraction = _read_extraction(report)
    questions = _read_questions(report)
    completeness = compute_completeness(extraction)

    return AnalysisRead(
        extraction=extraction,
        questions=questions,
        completeness=completeness,
        steps_flagged_for_review=steps_need_review(extraction.steps),
    )


@router.post("/{report_id}/questions/{question_id}/answer", response_model=AnalysisRead)
def answer_question(
    report_id: UUID,
    question_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    body: AnswerQuestionRequest,
) -> AnalysisRead:
    """Answers one follow-up question. The answer is written into the
    matching field as though the user had stated it directly: a scalar
    field is set (or created) as Explicit with the user as the source; a
    list field (steps, error_messages) gets a new entry appended; the
    question row records the answer and when it was given. The
    completeness score in the response reflects the change immediately
    (US-14 criterion 5). 404 rules match every other report endpoint
    (NFR-15); an unknown or foreign question id is also 404, for the same
    reason."""
    report = get_owned_report_or_404(db, current_user, report_id)
    question = next((q for q in report.follow_up_questions if q.id == question_id), None)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    question.answer = body.answer
    question.answered_at = datetime.now(UTC)

    if question.field_name in _SCALAR_FIELDS:
        existing = next(
            (
                f
                for f in report.extracted_fields
                if f.field_name == question.field_name and f.position is None
            ),
            None,
        )
        if existing is None:
            existing = ExtractedFieldRow(field_name=question.field_name)
            report.extracted_fields.append(existing)
        existing.value = body.answer
        existing.source_quote = body.answer
        existing.label = str(Label.EXPLICIT)
        existing.confidence = None
        existing.reason = "Answered directly by the user"
        if question.field_name == "title":
            report.title = body.answer
    elif question.field_name in ("steps", "error_messages"):
        positions = [
            f.position
            for f in report.extracted_fields
            if f.field_name == question.field_name and f.position is not None
        ]
        report.extracted_fields.append(
            ExtractedFieldRow(
                field_name=question.field_name,
                position=(max(positions) + 1 if positions else 0),
                value=body.answer,
                source_quote=body.answer,
                label=str(Label.EXPLICIT),
                reason="Answered directly by the user",
            )
        )
    elif question.field_name == "environment":
        report.environment_details.append(
            EnvironmentDetailRow(
                name="additional",
                value=body.answer,
                source_quote=body.answer,
                label=str(Label.EXPLICIT),
            )
        )

    db.commit()

    extraction = _read_extraction(report)
    refresh_triage(report, extraction)
    db.commit()
    questions = _read_questions(report)
    return AnalysisRead(
        extraction=extraction,
        questions=questions,
        completeness=compute_completeness(extraction),
        steps_flagged_for_review=steps_need_review(extraction.steps),
    )


@router.post("/{report_id}/environment", response_model=AnalysisRead)
def review_environment(
    report_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    body: EnvironmentReviewRequest,
) -> AnalysisRead:
    """Applies corrections and removals to the captured environment
    details, and, if given, passes the answer to the open "anything else
    relevant" question through the same masking, extraction and
    verification path as the original report, merging any environment
    details it finds (US-33). A corrected or added detail is stored as
    Explicit, the value itself standing as its own source quote, since it
    is now the user's direct statement. 404 rules match every other report
    endpoint (NFR-15)."""
    report = get_owned_report_or_404(db, current_user, report_id)

    for name in body.removals:
        normalised_name = normalise_environment_name(name)
        report.environment_details[:] = [
            detail for detail in report.environment_details if detail.name != normalised_name
        ]

    for correction in body.corrections:
        normalised_name = normalise_environment_name(correction.name)
        existing = next((d for d in report.environment_details if d.name == normalised_name), None)
        if existing is None:
            report.environment_details.append(
                EnvironmentDetailRow(
                    name=normalised_name,
                    value=correction.value,
                    source_quote=correction.value,
                    label=str(Label.EXPLICIT),
                )
            )
        else:
            existing.value = correction.value
            existing.source_quote = correction.value
            existing.label = str(Label.EXPLICIT)

    if body.additional_details:
        items = detect_masked_items(body.additional_details)
        masked_text = apply_masking(body.additional_details, items)
        raw = extract(masked_text)
        verified = verify_extraction(raw, masked_text)
        existing_names = {detail.name for detail in report.environment_details}
        for detail in verified.environment:
            if detail.name in existing_names:
                continue
            report.environment_details.append(
                EnvironmentDetailRow(
                    name=detail.name,
                    value=detail.value,
                    source_quote=detail.source_quote,
                    label=str(detail.label),
                )
            )

    db.commit()

    extraction = _read_extraction(report)
    refresh_triage(report, extraction)
    db.commit()
    questions = _read_questions(report)
    return AnalysisRead(
        extraction=extraction,
        questions=questions,
        completeness=compute_completeness(extraction),
        steps_flagged_for_review=steps_need_review(extraction.steps),
    )


def _read_extraction(report: BugReport) -> ExtractionResult:
    """Rebuilds an `ExtractionResult` from this report's `extracted_fields`
    and `environment_details` rows, the reverse of `_persist_analysis`."""
    rows_by_field: dict[str, list[ExtractedFieldRow]] = {}
    for row in report.extracted_fields:
        rows_by_field.setdefault(row.field_name, []).append(row)

    def scalar(field_name: str) -> ExtractedFieldValue:
        rows = rows_by_field.get(field_name)
        if not rows:
            return ExtractedFieldValue(value=None, source_quote=None, label=Label.MISSING)
        return _to_extracted_field_value(rows[0])

    def ordered_list(field_name: str) -> list[ExtractedFieldValue]:
        rows = sorted(rows_by_field.get(field_name, []), key=lambda row: row.position or 0)
        return [_to_extracted_field_value(row) for row in rows]

    return ExtractionResult(
        title=scalar("title"),
        summary=scalar("summary"),
        expected_behaviour=scalar("expected_behaviour"),
        actual_behaviour=scalar("actual_behaviour"),
        frequency=scalar("frequency"),
        steps=ordered_list("steps"),
        environment=[
            EnvironmentDetailValue(
                name=detail.name,
                value=detail.value,
                source_quote=detail.source_quote,
                label=Label(detail.label),
            )
            for detail in report.environment_details
        ],
        error_messages=ordered_list("error_messages"),
    )


def _to_extracted_field_value(row: ExtractedFieldRow) -> ExtractedFieldValue:
    return ExtractedFieldValue(
        value=row.value,
        source_quote=row.source_quote,
        label=Label(row.label),
        confidence=row.confidence,
        reason=row.reason,
    )


def _read_questions(report: BugReport) -> list[PersistedQuestion]:
    return [
        PersistedQuestion(
            id=str(row.id),
            field=row.field_name,
            question=row.question,
            reason=row.reason,
            model_proposed=row.model_proposed,
            answer=row.answer,
            answered_at=row.answered_at,
        )
        for row in report.follow_up_questions
    ]


def _persist_analysis(
    db: Session,
    report: BugReport,
    extraction: ExtractionResult,
    questions: list[FilteredQuestion],
) -> None:
    """Replaces this report's extracted fields, environment details and
    follow-up questions with the result of the analysis just run, sets
    `title` from the extraction, and moves the report to Analysed.
    Re-running analysis (after an edit resets the report to Draft, US-07
    criterion 1) replaces rather than accumulates, since the old rows
    describe text that no longer exists once `original_text` has changed."""
    report.extracted_fields.clear()
    report.environment_details.clear()
    report.follow_up_questions.clear()

    for field_name in _SCALAR_FIELDS:
        field = getattr(extraction, field_name)
        report.extracted_fields.append(
            ExtractedFieldRow(
                field_name=field_name,
                value=field.value,
                source_quote=field.source_quote,
                label=str(field.label),
                confidence=field.confidence,
                reason=field.reason,
            )
        )

    for position, step in enumerate(extraction.steps):
        report.extracted_fields.append(
            ExtractedFieldRow(
                field_name="steps",
                position=position,
                value=step.value,
                source_quote=step.source_quote,
                label=str(step.label),
                confidence=step.confidence,
                reason=step.reason,
            )
        )

    for position, error in enumerate(extraction.error_messages):
        report.extracted_fields.append(
            ExtractedFieldRow(
                field_name="error_messages",
                position=position,
                value=error.value,
                source_quote=error.source_quote,
                label=str(error.label),
                confidence=error.confidence,
                reason=error.reason,
            )
        )

    for detail in extraction.environment:
        report.environment_details.append(
            EnvironmentDetailRow(
                name=detail.name,
                value=detail.value,
                source_quote=detail.source_quote,
                label=str(detail.label),
            )
        )

    for question in questions:
        report.follow_up_questions.append(
            FollowUpQuestionRow(
                field_name=question.field,
                question=question.question,
                reason=question.reason,
                model_proposed=question.model_proposed,
            )
        )

    report.title = extraction.title.value
    report.state = "Analysed"
    refresh_triage(report, extraction)

    db.commit()
