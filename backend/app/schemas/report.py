"""Request and response shapes for editing and exporting the generated
report (`docs/design.md` section 7.5, US-24, US-25). The report itself is
`app.report.template.GeneratedReport`, used as the response model directly."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.report.store import LIST_FIELDS

EditableField = Literal[
    "title",
    "summary",
    "expected_behaviour",
    "actual_behaviour",
    "frequency",
    "steps",
    "error_messages",
    "environment",
    "additional_information",
]

# bug_reports.title is varchar(200).
MAX_TITLE_LENGTH = 200
MAX_TEXT_LENGTH = 10_000
MAX_ITEMS = 50
MAX_ITEM_LENGTH = 2_000


class EnvironmentEntry(BaseModel):
    # environment_details.name is varchar(64).
    name: str = Field(min_length=1, max_length=64)
    value: str = Field(min_length=1, max_length=MAX_ITEM_LENGTH)


class ReportEditRequest(BaseModel):
    """A person's own version of one field (US-24 criteria 1 and 2). A
    single-value field takes `text` (empty or null clears it, so it reads
    "Not provided"); steps and error messages take `items`; the
    environment takes `environment`. Nothing else is accepted for a field."""

    field: EditableField
    text: str | None = None
    items: list[str] | None = None
    environment: list[EnvironmentEntry] | None = None

    @model_validator(mode="after")
    def _shape_matches_field(self) -> "ReportEditRequest":
        if self.field in LIST_FIELDS:
            self._check_items()
        elif self.field == "environment":
            self._check_environment()
        else:
            self._check_text()
        return self

    def _check_items(self) -> None:
        if self.items is None or self.text is not None or self.environment is not None:
            raise ValueError(f"{self.field} takes a list of items")
        if len(self.items) > MAX_ITEMS:
            raise ValueError(f"At most {MAX_ITEMS} items")
        if any(len(item) > MAX_ITEM_LENGTH for item in self.items):
            raise ValueError(f"Each item is at most {MAX_ITEM_LENGTH} characters")

    def _check_environment(self) -> None:
        if self.environment is None or self.text is not None or self.items is not None:
            raise ValueError("environment takes a list of name and value pairs")
        if len(self.environment) > MAX_ITEMS:
            raise ValueError(f"At most {MAX_ITEMS} environment details")

    def _check_text(self) -> None:
        if self.items is not None or self.environment is not None:
            raise ValueError(f"{self.field} takes text")
        limit = MAX_TITLE_LENGTH if self.field == "title" else MAX_TEXT_LENGTH
        if self.text is not None and len(self.text) > limit:
            raise ValueError(f"{self.field} is at most {limit} characters")


class MarkdownRead(BaseModel):
    """The report as Markdown (US-25), and anything worth knowing before it
    is shared: unanswered questions and missing essential fields (US-14
    criterion 6). A warning never blocks exporting."""

    markdown: str
    warnings: list[str]
