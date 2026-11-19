"""Tests for GET /api/analytics (app/api/analytics.py, US-29): three series
built from the signed-in user's own reports, and the empty state."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import update

from app.models.core import BugReport
from tests.conftest import TestingSessionLocal, create_report, register_and_login


def _counts(series: list[dict]) -> dict[str, int]:
    return {item["name"]: item["count"] for item in series}


def test_no_reports_is_the_empty_state(client):
    """US-29 criterion 2."""
    register_and_login(client)

    body = client.get("/api/analytics").json()

    assert body["total_reports"] == 0
    assert body["by_week"] == []
    assert all(item["count"] == 0 for item in body["by_severity"] + body["by_category"])


def test_three_series_are_built_from_the_users_reports(client):
    """US-29 criterion 1: by severity, by category and over time."""
    register_and_login(client)
    crash = create_report(client, "The app crashes when I open my login page.").json()["id"]
    create_report(client, "There is a typo in the footer of the settings page.")
    create_report(client, "Never analysed, so this one has no triage yet.")
    client.get(f"/api/reports/{crash}/triage")

    body = client.get("/api/analytics").json()

    assert body["total_reports"] == 3
    severity = _counts(body["by_severity"])
    assert severity["High"] == 1
    assert severity["Not triaged"] == 2
    assert list(severity) == ["Critical", "High", "Medium", "Low", "Not triaged"]
    assert _counts(body["by_category"])["Authentication"] == 1
    assert sum(week["count"] for week in body["by_week"]) == 3


def test_another_users_reports_never_count(client):
    """NFR-15, applied to the dashboard."""
    register_and_login(client, "owner@example.com")
    create_report(client, "The app crashes when I open my login page.")
    client.post("/api/auth/logout")
    register_and_login(client, "other@example.com")

    assert client.get("/api/analytics").json()["total_reports"] == 0


def test_weeks_without_reports_are_listed_with_zero(client):
    register_and_login(client)
    create_report(client, "The app crashes when I open my login page.")
    three_weeks_ago = datetime.now(UTC) - timedelta(weeks=3)
    with TestingSessionLocal() as db:
        db.execute(update(BugReport).values(created_at=three_weeks_ago))
        db.commit()
    create_report(client, "A second report written this week, to compare.")

    weeks = client.get("/api/analytics").json()["by_week"]

    assert [week["count"] for week in weeks] == [1, 0, 0, 1]
    assert datetime.fromisoformat(weeks[0]["week_start"]).weekday() == 0


def test_not_signed_in_returns_401(client):
    assert client.get("/api/analytics").status_code == 401
