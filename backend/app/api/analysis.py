"""Runs the extraction pipeline on a report and persists the result
(`docs/design.md` section 6.5 steps 1 to 6), reads a persisted result back
with its completeness score (US-13), previews and adjusts masking (US-32),
answers a follow-up question (US-14), and reviews environment details
(US-33).

Every read and write of a report's fields goes through `app.report.store`,
so a person's corrections, answers and edits survive re-analysis (ADR-011,
ADR-027)."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, status
from sqlalchemy.orm.session import Session

from app.analysis.client import extract
from app.analysis.completeness import compute_completeness
from app.analysis.masking import MaskingResult, apply_masking, detect_masked_items
from app.analysis.masking import mask_literal_occurrences as mask_every_occurrence
from app.analysis.questions import filter_questions
from app.analysis.schema import ExtractionResult, RawFollowUpQuestion
from app.analysis.verification import (
    normalise_environment_name,
    steps_need_review,
    verify_extraction,
)
from app.api.reports import get_owned_report_or_404
from app.deps import CurrentUser, DbSession
from app.models.analysis import FollowUpQuestion as FollowUpQuestionRow
from app.models.core import BugReport
from app.report import store
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
    (FR-29, US-32 criterion 5).

    Running analysis again keeps every correction a person made; only what
    the model produced is replaced (ADR-011). The extraction returned is
    the report as it now stands, corrections included."""
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
    extraction = _persist_analysis(
        db, report, verify_extraction(raw, model_input), raw.proposed_questions
    )

    return AnalyzeResult(
        masked_items=masking_result.items,
        extraction=extraction,
        questions=_read_questions(report),
        steps_flagged_for_review=steps_need_review(extraction.steps),
    )


@router.get("/{report_id}/analysis", response_model=AnalysisRead)
def read_analysis(report_id: UUID, current_user: CurrentUser, db: DbSession) -> AnalysisRead:
    """Reads back whatever was persisted by the most recent `analyze` call,
    with every correction since: the extraction, the follow-up questions,
    the completeness score (US-13), and which fields a person has
    corrected. A report that has never been analysed reads back as the
    all-Missing shape, not an error (FR-28's safe-fallback shape, extended
    to reading). 404 rules match every other report endpoint (NFR-15)."""
    report = get_owned_report_or_404(db, current_user, report_id)
    return _analysis_read(report)


@router.post("/{report_id}/questions/{question_id}/answer", response_model=AnalysisRead)
def answer_question(
    report_id: UUID,
    question_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    body: AnswerQuestionRequest,
) -> AnalysisRead:
    """Answers one follow-up question. The answer becomes the person's own
    version of the matching field, Explicit, beside whatever the model
    produced: a scalar field takes the answer, a list field (steps,
    error_messages) gets it appended, and an environment answer becomes a
    detail of its own. The question row records the answer and when. The
    completeness score in the response reflects the change immediately
    (US-14 criterion 5), and re-analysis keeps the answer (ADR-011). 404
    rules match every other report endpoint (NFR-15); an unknown or foreign
    question id is also 404, for the same reason."""
    report = get_owned_report_or_404(db, current_user, report_id)
    question = next((q for q in report.follow_up_questions if q.id == question_id), None)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    question.answer = body.answer
    question.answered_at = datetime.now(UTC)

    if question.field_name in store.SCALAR_FIELDS:
        store.set_scalar(report, question.field_name, body.answer)
    elif question.field_name in store.LIST_FIELDS:
        store.append_to_list(report, question.field_name, body.answer)
    elif question.field_name == "environment":
        store.set_environment_detail(report, "additional", body.answer)

    # An answer can carry exactly the wording triage reads ("it crashes
    # every time"), so the suggestions are refreshed with it.
    refresh_triage(report, store.read_extraction(report))
    db.commit()
    return _analysis_read(report)


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
    details it finds (US-33). A corrected or added detail is stored as the
    person's own, Explicit, the value standing as its own source quote; a
    removed one stays removed through re-analysis (ADR-011). 404 rules
    match every other report endpoint (NFR-15)."""
    report = get_owned_report_or_404(db, current_user, report_id)

    for name in body.removals:
        store.remove_environment_detail(report, normalise_environment_name(name))

    for correction in body.corrections:
        store.set_environment_detail(
            report, normalise_environment_name(correction.name), correction.value
        )

    if body.additional_details:
        items = detect_masked_items(body.additional_details)
        masked_text = apply_masking(body.additional_details, items)
        verified = verify_extraction(extract(masked_text), masked_text)
        store.add_stated_environment(report, verified.environment)

    refresh_triage(report, store.read_extraction(report))
    db.commit()
    return _analysis_read(report)


def _analysis_read(report: BugReport) -> AnalysisRead:
    extraction = store.read_extraction(report)
    return AnalysisRead(
        extraction=extraction,
        questions=_read_questions(report),
        completeness=compute_completeness(extraction),
        steps_flagged_for_review=steps_need_review(extraction.steps),
        corrected_fields=sorted(store.edited_fields(report)),
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
    proposed_questions: list[RawFollowUpQuestion],
) -> ExtractionResult:
    """Stores a new analysis result and returns the report's fields as they
    now stand. The model's rows are replaced; a person's corrections and
    answered questions are kept (ADR-011). Questions are filtered against
    the fields as they stand with corrections, so nothing already answered
    is asked again. Sets `title`, moves the report to Analysed, and
    refreshes triage."""
    store.replace_model_result(report, extraction)
    current = store.read_extraction(report)

    report.follow_up_questions[:] = [q for q in report.follow_up_questions if q.answer is not None]
    answered = {q.field_name for q in report.follow_up_questions}
    for question in filter_questions(proposed_questions, current):
        if question.field in answered:
            continue
        report.follow_up_questions.append(
            FollowUpQuestionRow(
                field_name=question.field,
                question=question.question,
                reason=question.reason,
                model_proposed=question.model_proposed,
            )
        )

    report.title = current.title.value
    report.state = "Analysed"

    # Pipeline step 8 (docs/design.md section 6.5). A triage value a person
    # already changed keeps their choice; only untouched values follow the
    # new suggestion.
    refresh_triage(report, current)

    db.commit()
    return current
