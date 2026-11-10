"""Tests for GET and PATCH /api/reports/{id}/triage (app/api/triage.py), and
for triage being refreshed by analysis (US-15, US-16, US-17, FR-15).

Every analyze call replaces app.api.analysis.extract with a fake, so no
test makes a real Gemini call."""

from sqlalchemy import select

import app.api.analysis as analysis_module
from app.analysis.schema import RawExtractionResult
from app.models.triage import TriageOverride, TriageValue
from tests.conftest import TestingSessionLocal, create_report, register_and_login

CRASH_REPORT = "The app crashes when I click save on the settings page."


def _analyze_with_empty_extraction(client, monkeypatch, report_id: str) -> None:
    monkeypatch.setattr(analysis_module, "extract", lambda text: RawExtractionResult())
    client.post(f"/api/reports/{report_id}/analyze")


class TestReadTriage:
    def test_all_four_values_are_returned_with_reason_and_options(self, client):
        register_and_login(client)
        report_id = create_report(client, CRASH_REPORT).json()["id"]

        response = client.get(f"/api/reports/{report_id}/triage")

        assert response.status_code == 200
        body = response.json()
        assert body["severity"]["value"] == "High"
        assert body["severity"]["reason"] == 'Mentions "crashes", so High'
        assert body["severity"]["options"] == ["Critical", "High", "Medium", "Low"]
        assert body["priority"]["options"] == ["P1", "P2", "P3", "P4"]
        assert body["category"]["value"] in body["category"]["options"]
        assert body["reproducibility"]["value"] == "Unknown"
        assert all(not body[field]["overridden"] for field in body)

    def test_analysis_sets_the_reports_severity_for_the_history_filter(self, client, monkeypatch):
        """bug_reports.severity mirrors triage, so US-06's severity filter
        finally matches something."""
        register_and_login(client)
        report_id = create_report(client, CRASH_REPORT).json()["id"]

        _analyze_with_empty_extraction(client, monkeypatch, report_id)

        assert client.get(f"/api/reports/{report_id}").json()["severity"] == "High"
        listed = client.get("/api/reports", params={"severity": "High"}).json()
        assert [item["id"] for item in listed["items"]] == [report_id]

    def test_another_users_report_returns_404(self, client):
        """NFR-15."""
        register_and_login(client, "owner@example.com")
        report_id = create_report(client, CRASH_REPORT).json()["id"]
        client.post("/api/auth/logout")
        register_and_login(client, "other@example.com")

        response = client.get(f"/api/reports/{report_id}/triage")

        assert response.status_code == 404

    def test_not_signed_in_returns_401(self, client):
        response = client.get("/api/reports/00000000-0000-0000-0000-000000000000/triage")

        assert response.status_code == 401


class TestOverrideTriage:
    def test_an_override_is_saved_and_flagged(self, client):
        """US-15 criterion 4: if the user changes it, the override is saved
        and flagged."""
        register_and_login(client)
        report_id = create_report(client, CRASH_REPORT).json()["id"]

        response = client.patch(
            f"/api/reports/{report_id}/triage", json={"field": "severity", "value": "Low"}
        )

        assert response.status_code == 200
        severity = response.json()["severity"]
        assert severity["value"] == "Low"
        assert severity["suggested_value"] == "High"
        assert severity["overridden"] is True
        reread = client.get(f"/api/reports/{report_id}/triage").json()["severity"]
        assert reread["value"] == "Low"
        assert reread["overridden"] is True
        assert client.get(f"/api/reports/{report_id}").json()["severity"] == "Low"

    def test_an_override_records_who_changed_what_from_what_to_what(self, client):
        """FR-15: overrides are recorded."""
        register_and_login(client)
        user_id = client.get("/api/auth/me").json()["id"]
        report_id = create_report(client, CRASH_REPORT).json()["id"]

        client.patch(f"/api/reports/{report_id}/triage", json={"field": "severity", "value": "Low"})

        with TestingSessionLocal() as db:
            overrides = db.execute(select(TriageOverride)).scalars().all()
        assert len(overrides) == 1
        assert str(overrides[0].user_id) == user_id
        assert overrides[0].field_name == "severity"
        assert overrides[0].old_value == "High"
        assert overrides[0].new_value == "Low"
        assert overrides[0].created_at is not None

    def test_priority_is_editable_on_its_own(self, client):
        """US-16 criteria 1 and 3: priority is a separate, editable field;
        changing it leaves severity alone (DR-02)."""
        register_and_login(client)
        report_id = create_report(client, CRASH_REPORT).json()["id"]

        response = client.patch(
            f"/api/reports/{report_id}/triage", json={"field": "priority", "value": "P4"}
        )

        body = response.json()
        assert body["priority"]["value"] == "P4"
        assert body["priority"]["overridden"] is True
        assert body["severity"]["value"] == "High"
        assert body["severity"]["overridden"] is False

    def test_setting_a_value_back_to_the_suggestion_clears_the_flag(self, client):
        register_and_login(client)
        report_id = create_report(client, CRASH_REPORT).json()["id"]
        client.patch(f"/api/reports/{report_id}/triage", json={"field": "severity", "value": "Low"})

        response = client.patch(
            f"/api/reports/{report_id}/triage", json={"field": "severity", "value": "High"}
        )

        assert response.json()["severity"]["overridden"] is False

    def test_choosing_the_value_already_in_force_records_nothing(self, client):
        register_and_login(client)
        report_id = create_report(client, CRASH_REPORT).json()["id"]

        client.patch(
            f"/api/reports/{report_id}/triage", json={"field": "severity", "value": "High"}
        )

        with TestingSessionLocal() as db:
            assert db.execute(select(TriageOverride)).scalars().all() == []

    def test_a_value_from_another_fields_scale_is_rejected(self, client):
        """DR-02: a priority value is never accepted as a severity."""
        register_and_login(client)
        report_id = create_report(client, CRASH_REPORT).json()["id"]

        response = client.patch(
            f"/api/reports/{report_id}/triage", json={"field": "severity", "value": "P1"}
        )

        assert response.status_code == 422

    def test_a_category_outside_the_fixed_list_is_rejected(self, client):
        """US-17 criterion 1: category comes from a fixed list."""
        register_and_login(client)
        report_id = create_report(client, CRASH_REPORT).json()["id"]

        response = client.patch(
            f"/api/reports/{report_id}/triage", json={"field": "category", "value": "Billing"}
        )

        assert response.status_code == 422

    def test_an_unknown_field_is_rejected(self, client):
        register_and_login(client)
        report_id = create_report(client, CRASH_REPORT).json()["id"]

        response = client.patch(
            f"/api/reports/{report_id}/triage", json={"field": "owner", "value": "me"}
        )

        assert response.status_code == 422

    def test_overriding_another_users_report_returns_404(self, client):
        """NFR-15."""
        register_and_login(client, "owner@example.com")
        report_id = create_report(client, CRASH_REPORT).json()["id"]
        client.post("/api/auth/logout")
        register_and_login(client, "other@example.com")

        response = client.patch(
            f"/api/reports/{report_id}/triage", json={"field": "severity", "value": "Low"}
        )

        assert response.status_code == 404


class TestRefreshOnAnalysis:
    def test_re_analysis_keeps_a_persons_override(self, client, monkeypatch):
        """US-15 criterion 4: a saved override is not silently undone when
        analysis runs again; the suggestion beside it is refreshed."""
        register_and_login(client)
        report_id = create_report(client, CRASH_REPORT).json()["id"]
        _analyze_with_empty_extraction(client, monkeypatch, report_id)
        client.patch(f"/api/reports/{report_id}/triage", json={"field": "severity", "value": "Low"})

        _analyze_with_empty_extraction(client, monkeypatch, report_id)

        severity = client.get(f"/api/reports/{report_id}/triage").json()["severity"]
        assert severity["value"] == "Low"
        assert severity["overridden"] is True
        assert severity["suggested_value"] == "High"

    def test_an_untouched_value_follows_an_edit_and_re_analysis(self, client, monkeypatch):
        register_and_login(client)
        report_id = create_report(client, CRASH_REPORT).json()["id"]
        _analyze_with_empty_extraction(client, monkeypatch, report_id)

        client.patch(
            f"/api/reports/{report_id}", json={"original_text": "There is a typo in the footer."}
        )
        _analyze_with_empty_extraction(client, monkeypatch, report_id)

        severity = client.get(f"/api/reports/{report_id}/triage").json()["severity"]
        assert severity["value"] == "Low"
        assert severity["overridden"] is False

    def test_answering_a_question_refreshes_the_suggestions(self, client, monkeypatch):
        """An answer is Explicit and is read by the rules, so saying "it
        happens sometimes" moves Reproducibility to Sometimes (US-17
        criterion 2)."""
        register_and_login(client)
        report_id = create_report(client, CRASH_REPORT).json()["id"]
        _analyze_with_empty_extraction(client, monkeypatch, report_id)
        questions = client.get(f"/api/reports/{report_id}/analysis").json()["questions"]
        frequency_question = next(q for q in questions if q["field"] == "frequency")

        client.post(
            f"/api/reports/{report_id}/questions/{frequency_question['id']}/answer",
            json={"answer": "It happens sometimes"},
        )

        triage = client.get(f"/api/reports/{report_id}/triage").json()
        assert triage["reproducibility"]["value"] == "Sometimes"

    def test_each_report_has_exactly_one_row_per_field(self, client, monkeypatch):
        register_and_login(client)
        report_id = create_report(client, CRASH_REPORT).json()["id"]

        _analyze_with_empty_extraction(client, monkeypatch, report_id)
        _analyze_with_empty_extraction(client, monkeypatch, report_id)

        with TestingSessionLocal() as db:
            rows = db.execute(select(TriageValue)).scalars().all()
        assert sorted(row.field_name for row in rows) == [
            "category",
            "priority",
            "reproducibility",
            "severity",
        ]
