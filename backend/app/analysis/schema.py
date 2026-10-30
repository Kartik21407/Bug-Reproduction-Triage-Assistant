"""The extraction schema (design.md section 6.5, FR-27, FR-33).

Two families of models live here. The `Raw*` models are what the model
itself returns: a candidate value, a source quote, a confidence and a
reason, never a label. The plain models (`ExtractedField`,
`EnvironmentDetail`, `ExtractionResult`) are what verification produces:
the same data, plus the label that decides whether any of it is trusted.
The model never assigns a label; only `app.analysis.verification` does
(the governing principle in the root CLAUDE.md).
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class Label(StrEnum):
    """The four verification outcomes (FR-09, FR-27). Always one of these
    four, never anything else, in code and in the interface alike."""

    EXPLICIT = "Explicit"
    INFERRED = "Inferred"
    UNVERIFIED = "Unverified"
    MISSING = "Missing"


# --- What the model returns, before verification ---------------------------


class RawModelField(BaseModel):
    """One field as the model proposes it. Carries a confidence and a
    reason, but never a label; verification decides that."""

    value: str
    source_quote: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


class RawEnvironmentDetail(BaseModel):
    """One environment name and value pair as the model proposes it
    (FR-07, ADR-015). Open-ended: the model may return any name."""

    name: str
    value: str
    source_quote: str


class RawFollowUpQuestion(BaseModel):
    """One follow-up question as the model proposes it, with its reason.
    Filtering which of these are actually shown happens in
    app.analysis.questions, not here (FR-32, ADR-016)."""

    field: str
    question: str
    reason: str


class RawExtractionResult(BaseModel):
    """The model's full raw response, matching the output contract in
    app/analysis/prompts/extraction.v1.md. Every field is optional: the model
    marks a field Missing simply by leaving it out."""

    title: RawModelField | None = None
    summary: RawModelField | None = None
    expected_behaviour: RawModelField | None = None
    actual_behaviour: RawModelField | None = None
    frequency: RawModelField | None = None
    steps: list[RawModelField] = Field(default_factory=list)
    environment: list[RawEnvironmentDetail] = Field(default_factory=list)
    error_messages: list[RawModelField] = Field(default_factory=list)
    proposed_questions: list[RawFollowUpQuestion] = Field(default_factory=list)


# --- What verification produces ---------------------------------------------


class ExtractedField(BaseModel):
    """One extracted field after verification: its value, the source
    quote, the label verification assigned, and the model's own
    confidence and reason, carried through for explainability (NFR-10,
    FR-33) but never used to decide the label."""

    value: str | None
    source_quote: str | None
    label: Label
    confidence: float | None = None
    reason: str | None = None


class EnvironmentDetail(BaseModel):
    """One environment name and value pair after verification (FR-07,
    ADR-015)."""

    name: str
    value: str
    source_quote: str
    label: Label


class ExtractionResult(BaseModel):
    """The fully verified extraction result. Every field has passed
    through verification and carries a label (FR-27)."""

    title: ExtractedField
    summary: ExtractedField
    expected_behaviour: ExtractedField
    actual_behaviour: ExtractedField
    frequency: ExtractedField
    steps: list[ExtractedField]
    environment: list[EnvironmentDetail]
    error_messages: list[ExtractedField]
