"""Response shape for the dashboard (`docs/design.md` section 7.7, US-29)."""

from datetime import date

from pydantic import BaseModel


class Count(BaseModel):
    name: str
    count: int


class PeriodCount(BaseModel):
    # The Monday that starts the week.
    week_start: date
    count: int


class AnalyticsRead(BaseModel):
    """Three series, all from the signed-in user's own reports (US-29
    criterion 1). `total_reports` of zero is the empty state (criterion 2)."""

    total_reports: int
    by_severity: list[Count]
    by_category: list[Count]
    by_week: list[PeriodCount]
