"""The dashboard's numbers (US-29, FR-25): reports by severity, by category
and by week, from the signed-in user's own reports only."""

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.models.core import BugReport
from app.models.triage import TriageValue
from app.schemas.analytics import AnalyticsRead, Count, PeriodCount
from app.triage.rules import CATEGORIES, SEVERITIES

router = APIRouter(tags=["analytics"])

NOT_TRIAGED = "Not triaged"
# The timeline covers at most this many weeks, ending this week.
MAX_WEEKS = 26


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


@router.get("/analytics", response_model=AnalyticsRead)
def read_analytics(current_user: CurrentUser, db: DbSession) -> AnalyticsRead:
    """Counts for the three dashboard charts (US-29 criterion 1). Every
    query filters by the current user, so another user's reports never
    count (NFR-15). A report not yet triaged counts as "Not triaged" rather
    than being guessed into a value. Weeks with no reports are listed with
    a zero, so the timeline has no gaps."""
    reports = db.execute(select(BugReport).where(BugReport.user_id == current_user.id)).scalars()
    reports = list(reports)
    categories = dict(
        db.execute(
            select(TriageValue.report_id, TriageValue.value)
            .join(BugReport, TriageValue.report_id == BugReport.id)
            .where(BugReport.user_id == current_user.id, TriageValue.field_name == "category")
        ).all()
    )

    severity_counts = dict.fromkeys((*SEVERITIES, NOT_TRIAGED), 0)
    category_counts = dict.fromkeys((*CATEGORIES, NOT_TRIAGED), 0)
    week_counts: dict[date, int] = {}
    for report in reports:
        severity_counts[report.severity or NOT_TRIAGED] += 1
        category_counts[categories.get(report.id, NOT_TRIAGED)] += 1
        created = report.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        week = _week_start(created.date())
        week_counts[week] = week_counts.get(week, 0) + 1

    by_week: list[PeriodCount] = []
    if week_counts:
        this_week = _week_start(datetime.now(UTC).date())
        first = max(min(week_counts), this_week - timedelta(weeks=MAX_WEEKS - 1))
        week = first
        while week <= this_week:
            by_week.append(PeriodCount(week_start=week, count=week_counts.get(week, 0)))
            week += timedelta(weeks=1)

    return AnalyticsRead(
        total_reports=len(reports),
        by_severity=[Count(name=k, count=v) for k, v in severity_counts.items()],
        by_category=[Count(name=k, count=v) for k, v in category_counts.items()],
        by_week=by_week,
    )
