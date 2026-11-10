"""Request and response shapes for the triage endpoints (`docs/design.md`
section 7.3, US-15, US-16, US-17)."""

from pydantic import BaseModel, model_validator

from app.triage.rules import OPTIONS, TriageField


class TriageValueRead(BaseModel):
    """One triage field: the value in force, the rule-based suggestion and
    the reason for it, whether a person changed it, and every value it may
    take, so the interface can offer exactly those in its dropdown."""

    value: str
    suggested_value: str
    reason: str
    overridden: bool
    options: list[str]


class TriageRead(BaseModel):
    severity: TriageValueRead
    priority: TriageValueRead
    category: TriageValueRead
    reproducibility: TriageValueRead


class TriageOverrideRequest(BaseModel):
    """A person setting one triage field (US-15 criterion 4, US-16
    criterion 3). The value must be one of that field's own options."""

    field: TriageField
    value: str

    @model_validator(mode="after")
    def _value_is_an_option(self) -> "TriageOverrideRequest":
        options = OPTIONS[self.field]
        if self.value not in options:
            raise ValueError(f"{self.value} is not a {self.field} value; use one of {options}")
        return self
