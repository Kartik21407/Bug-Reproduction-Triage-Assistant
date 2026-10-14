"""Tests for US-04 (submit a report), US-05 (optional logs field), US-06
(history search and filters) and US-07 (edit and delete)."""

import time
from uuid import UUID

from tests.conftest import (
    VALID_REPORT_TEXT,
    TestingSessionLocal,
    create_report,
    register_and_login,
)

from app.models.core import BugReport


class TestCreateReport:
    def test_valid_text_is_accepted(self, client):
        # Arrange
        register_and_login(client)

        # Act
        response = create_report(client, VALID_REPORT_TEXT)

        # Assert
        assert response.status_code == 201
        body = response.json()
        assert body["original_text"] == VALID_REPORT_TEXT
        assert body["state"] == "Draft"
        assert body["title"] is None
        assert body["severity"] is None

    def test_original_text_is_stored_exactly_as_submitted(self, client):
        """US-04 criterion 3: the original text is saved unchanged,
        including line breaks and irregular spacing."""
        # Arrange
        register_and_login(client)
        text = "Step 1: open the app.\n\nStep 2:   click   twice.\nExpected nothing, got a crash."

        # Act
        response = create_report(client, text)

        # Assert
        assert response.status_code == 201
        assert response.json()["original_text"] == text

    def test_a_timestamp_is_recorded_on_creation(self, client):
        """US-04 criterion 3: saved with a timestamp."""
        # Arrange
        register_and_login(client)

        # Act
        response = create_report(client)

        # Assert
        body = response.json()
        assert body["created_at"] is not None
        assert body["updated_at"] is not None

    def test_exactly_20_characters_is_accepted(self, client):
        """US-04 criterion 1: the lower bound."""
        # Arrange
        register_and_login(client)
        text = "x" * 20

        # Act
        response = create_report(client, text)

        # Assert
        assert response.status_code == 201

    def test_19_characters_is_rejected(self, client):
        """US-04 criterion 1: one below the lower bound."""
        # Arrange
        register_and_login(client)
        text = "x" * 19

        # Act
        response = create_report(client, text)

        # Assert
        assert response.status_code == 422

    def test_exactly_10000_characters_is_accepted(self, client):
        """US-04 criterion 1: the upper bound."""
        # Arrange
        register_and_login(client)
        text = "x" * 10_000

        # Act
        response = create_report(client, text)

        # Assert
        assert response.status_code == 201

    def test_10001_characters_is_rejected(self, client):
        """US-04 criterion 1: one above the upper bound."""
        # Arrange
        register_and_login(client)
        text = "x" * 10_001

        # Act
        response = create_report(client, text)

        # Assert
        assert response.status_code == 422

    def test_empty_text_is_rejected(self, client):
        """US-04 criterion 2: empty input is not submitted."""
        # Arrange
        register_and_login(client)

        # Act
        response = create_report(client, "")

        # Assert
        assert response.status_code == 422

    def test_whitespace_only_text_is_rejected(self, client):
        """Whitespace does not count towards the minimum length
        (design.md section 8.4), even when there is enough of it to pass a
        naive length check."""
        # Arrange
        register_and_login(client)
        text = " " * 25

        # Act
        response = create_report(client, text)

        # Assert
        assert response.status_code == 422

    def test_text_with_surrounding_whitespace_within_bounds_is_stored_unstripped(self, client):
        """The length check strips whitespace, but storage does not
        (US-04 criterion 3)."""
        # Arrange
        register_and_login(client)
        text = "   " + "x" * 20 + "   "

        # Act
        response = create_report(client, text)

        # Assert
        assert response.status_code == 201
        assert response.json()["original_text"] == text

    def test_creating_a_report_requires_authentication(self, client):
        # Arrange / Act
        response = create_report(client)

        # Assert
        assert response.status_code == 401


class TestReportLogs:
    def test_logs_field_is_optional(self, client):
        """US-05 criterion 1: optional."""
        # Arrange
        register_and_login(client)

        # Act
        response = create_report(client, VALID_REPORT_TEXT)

        # Assert
        assert response.status_code == 201
        assert response.json()["logs"] is None

    def test_logs_up_to_50000_characters_are_accepted_and_stored_unmodified(self, client):
        """US-05 criterion 1 and 2: up to 50,000 characters, unmodified."""
        # Arrange
        register_and_login(client)
        prefix = "Traceback (most recent call last):\n  "
        logs = prefix + ("x" * (50_000 - len(prefix)))
        assert len(logs) == 50_000

        # Act
        response = create_report(client, VALID_REPORT_TEXT, logs=logs)

        # Assert
        assert response.status_code == 201
        assert response.json()["logs"] == logs

    def test_logs_over_50000_characters_are_rejected(self, client):
        # Arrange
        register_and_login(client)
        logs = "x" * 50_001

        # Act
        response = create_report(client, VALID_REPORT_TEXT, logs=logs)

        # Assert
        assert response.status_code == 422


class TestReportListFilters:
    def test_list_is_sorted_newest_first(self, client):
        """US-06 criterion 1. SQLite's CURRENT_TIMESTAMP only has second
        resolution, unlike PostgreSQL's, so the two creates are separated by
        a full second to guarantee distinct timestamps here."""
        # Arrange
        register_and_login(client)
        create_report(client, "The first report created, so it should sort last.")
        time.sleep(1.1)
        create_report(client, "The second report created, so it should sort first.")

        # Act
        response = client.get("/api/reports")

        # Assert
        items = response.json()["items"]
        assert [item["original_text"] for item in items] == [
            "The second report created, so it should sort first.",
            "The first report created, so it should sort last.",
        ]

    def test_list_shows_title_severity_state_and_created_at(self, client):
        """US-06 criterion 1: the list shows title, severity, status and
        date. All four are present on every item, even while title and
        severity are unset this sprint."""
        # Arrange
        register_and_login(client)
        create_report(client)

        # Act
        response = client.get("/api/reports")

        # Assert
        item = response.json()["items"][0]
        assert {"title", "severity", "state", "created_at"}.issubset(item.keys())

    def test_filtering_by_state_matches_every_report_this_sprint(self, client):
        """US-06 criterion 2. Every report is Draft this sprint, so
        filtering by Draft returns everything."""
        # Arrange
        register_and_login(client)
        create_report(client)

        # Act
        response = client.get("/api/reports", params={"state": "Draft"})

        # Assert
        assert response.json()["total"] == 1

    def test_filtering_by_a_state_no_report_has_returns_an_empty_list(self, client):
        """US-06 criterion 2. No report is Analysed yet, since triage
        arrives in Sprint 3; the filter still works correctly."""
        # Arrange
        register_and_login(client)
        create_report(client)

        # Act
        response = client.get("/api/reports", params={"state": "Analysed"})

        # Assert
        assert response.json() == {"items": [], "total": 0}

    def test_filtering_by_an_invalid_state_is_rejected(self, client):
        # Arrange
        register_and_login(client)

        # Act
        response = client.get("/api/reports", params={"state": "NotAState"})

        # Assert
        assert response.status_code == 422

    def test_filtering_by_severity_matches_nothing_this_sprint(self, client):
        """US-06 criterion 2. Severity is unset until triage (Sprint 3), so
        any severity filter correctly returns nothing yet."""
        # Arrange
        register_and_login(client)
        create_report(client)

        # Act
        response = client.get("/api/reports", params={"severity": "Critical"})

        # Assert
        assert response.json() == {"items": [], "total": 0}

    def test_filtering_by_an_invalid_severity_is_rejected(self, client):
        # Arrange
        register_and_login(client)

        # Act
        response = client.get("/api/reports", params={"severity": "Severe"})

        # Assert
        assert response.status_code == 422

    def test_search_matches_the_original_text(self, client):
        """US-06 criterion 3: keyword search covers the original text."""
        # Arrange
        register_and_login(client)
        create_report(client, "The login button does nothing when clicked twice.")
        create_report(client, "Uploading a file larger than 5MB silently fails.")

        # Act
        response = client.get("/api/reports", params={"search": "login button"})

        # Assert
        body = response.json()
        assert body["total"] == 1
        assert "login button" in body["items"][0]["original_text"]

    def test_search_is_case_insensitive(self, client):
        # Arrange
        register_and_login(client)
        create_report(client, "The login button does nothing when clicked twice.")

        # Act
        response = client.get("/api/reports", params={"search": "LOGIN BUTTON"})

        # Assert
        assert response.json()["total"] == 1

    def test_search_with_no_match_returns_an_empty_list(self, client):
        # Arrange
        register_and_login(client)
        create_report(client, "The login button does nothing when clicked twice.")

        # Act
        response = client.get("/api/reports", params={"search": "duplicate key constraint"})

        # Assert
        assert response.json() == {"items": [], "total": 0}

    def test_a_blank_search_is_treated_as_no_filter(self, client):
        # Arrange
        register_and_login(client)
        create_report(client)

        # Act
        response = client.get("/api/reports", params={"search": "   "})

        # Assert
        assert response.json()["total"] == 1

    def test_search_treats_percent_and_underscore_as_literal_characters(self, client):
        """A search containing a LIKE wildcard character should not act as
        a wildcard."""
        # Arrange
        register_and_login(client)
        create_report(client, "Discount code SAVE_10% is rejected at checkout.")
        create_report(client, "Login page throws a 500 error on every attempt.")

        # Act
        response = client.get("/api/reports", params={"search": "10%"})

        # Assert
        body = response.json()
        assert body["total"] == 1
        assert "SAVE_10%" in body["items"][0]["original_text"]

    def test_search_and_state_filters_combine(self, client):
        # Arrange
        register_and_login(client)
        create_report(client, "The login button does nothing when clicked twice.")

        # Act
        matching = client.get("/api/reports", params={"search": "login", "state": "Draft"})
        non_matching = client.get("/api/reports", params={"search": "login", "state": "Reviewed"})

        # Assert
        assert matching.json()["total"] == 1
        assert non_matching.json()["total"] == 0


class TestUpdateReport:
    def test_editing_original_text_updates_it(self, client):
        # Arrange
        register_and_login(client)
        created = create_report(client, VALID_REPORT_TEXT)
        report_id = created.json()["id"]
        new_text = "The button still does nothing, but now on the second click too."

        # Act
        response = client.patch(f"/api/reports/{report_id}", json={"original_text": new_text})

        # Assert
        assert response.status_code == 200
        assert response.json()["original_text"] == new_text

    def test_editing_original_text_rejects_under_20_characters(self, client):
        """US-04 criterion 1 applies equally to an edit."""
        # Arrange
        register_and_login(client)
        created = create_report(client, VALID_REPORT_TEXT)
        report_id = created.json()["id"]

        # Act
        response = client.patch(f"/api/reports/{report_id}", json={"original_text": "too short"})

        # Assert
        assert response.status_code == 422

    def test_editing_original_text_rejects_over_10000_characters(self, client):
        # Arrange
        register_and_login(client)
        created = create_report(client, VALID_REPORT_TEXT)
        report_id = created.json()["id"]

        # Act
        response = client.patch(f"/api/reports/{report_id}", json={"original_text": "x" * 10_001})

        # Assert
        assert response.status_code == 422

    def test_editing_logs_updates_it(self, client):
        # Arrange
        register_and_login(client)
        created = create_report(client, VALID_REPORT_TEXT)
        report_id = created.json()["id"]

        # Act
        response = client.patch(f"/api/reports/{report_id}", json={"logs": "new log line"})

        # Assert
        assert response.status_code == 200
        assert response.json()["logs"] == "new log line"

    def test_editing_logs_rejects_over_50000_characters(self, client):
        # Arrange
        register_and_login(client)
        created = create_report(client, VALID_REPORT_TEXT)
        report_id = created.json()["id"]

        # Act
        response = client.patch(f"/api/reports/{report_id}", json={"logs": "x" * 50_001})

        # Assert
        assert response.status_code == 422

    def test_editing_only_logs_leaves_original_text_untouched(self, client):
        # Arrange
        register_and_login(client)
        created = create_report(client, VALID_REPORT_TEXT, logs="original logs")
        report_id = created.json()["id"]

        # Act
        response = client.patch(f"/api/reports/{report_id}", json={"logs": "updated logs"})

        # Assert
        body = response.json()
        assert body["original_text"] == VALID_REPORT_TEXT
        assert body["logs"] == "updated logs"

    def test_editing_only_original_text_leaves_logs_untouched(self, client):
        # Arrange
        register_and_login(client)
        created = create_report(client, VALID_REPORT_TEXT, logs="keep these logs")
        report_id = created.json()["id"]
        new_text = "A different description of the same underlying problem."

        # Act
        response = client.patch(f"/api/reports/{report_id}", json={"original_text": new_text})

        # Assert
        body = response.json()
        assert body["original_text"] == new_text
        assert body["logs"] == "keep these logs"

    def test_editing_original_text_resets_the_state_to_draft(self, client):
        """US-07 criterion 1: after editing the original text, analysis can
        be run again. No endpoint sets a state other than Draft yet, since
        extraction and triage do not exist until Sprint 2 and 3, so the
        state is set directly in the database to prove the reset actually
        happens rather than merely never being contradicted."""
        # Arrange
        register_and_login(client)
        created = create_report(client, VALID_REPORT_TEXT)
        report_id = created.json()["id"]
        with TestingSessionLocal() as db:
            report = db.get(BugReport, UUID(report_id))
            report.state = "Analysed"
            db.commit()

        # Act
        response = client.patch(
            f"/api/reports/{report_id}", json={"original_text": "A revised description of the bug."}
        )

        # Assert
        assert response.json()["state"] == "Draft"

    def test_editing_logs_only_does_not_change_the_state(self, client):
        # Arrange
        register_and_login(client)
        created = create_report(client, VALID_REPORT_TEXT)
        report_id = created.json()["id"]
        with TestingSessionLocal() as db:
            report = db.get(BugReport, UUID(report_id))
            report.state = "Reviewed"
            db.commit()

        # Act
        response = client.patch(f"/api/reports/{report_id}", json={"logs": "just logs"})

        # Assert
        assert response.json()["state"] == "Reviewed"

    def test_updated_at_changes_after_an_edit(self, client):
        """SQLite's CURRENT_TIMESTAMP only has second resolution, unlike
        PostgreSQL's, so the edit is delayed by a full second to guarantee a
        distinct timestamp here."""
        # Arrange
        register_and_login(client)
        created = create_report(client, VALID_REPORT_TEXT)
        report_id = created.json()["id"]
        original_updated_at = created.json()["updated_at"]
        time.sleep(1.1)

        # Act
        response = client.patch(
            f"/api/reports/{report_id}", json={"original_text": "A later edit to the same report."}
        )

        # Assert
        assert response.json()["updated_at"] != original_updated_at

    def test_updating_another_users_report_returns_404(self, client):
        # Arrange
        register_and_login(client, "owner@example.com")
        created = create_report(client, VALID_REPORT_TEXT)
        report_id = created.json()["id"]
        client.post("/api/auth/logout")
        register_and_login(client, "attacker@example.com")

        # Act
        response = client.patch(f"/api/reports/{report_id}", json={"original_text": "x" * 25})

        # Assert
        assert response.status_code == 404

    def test_updating_an_unknown_report_returns_404(self, client):
        # Arrange
        register_and_login(client)
        unknown_id = "00000000-0000-0000-0000-000000000000"

        # Act
        response = client.patch(f"/api/reports/{unknown_id}", json={"original_text": "x" * 25})

        # Assert
        assert response.status_code == 404

    def test_updating_a_report_requires_authentication(self, client):
        # Arrange / Act
        response = client.patch(
            "/api/reports/00000000-0000-0000-0000-000000000000",
            json={"original_text": "x" * 25},
        )

        # Assert
        assert response.status_code == 401


class TestDeleteReport:
    def test_deleting_own_report_succeeds(self, client):
        # Arrange
        register_and_login(client)
        created = create_report(client, VALID_REPORT_TEXT)
        report_id = created.json()["id"]

        # Act
        response = client.delete(f"/api/reports/{report_id}")

        # Assert
        assert response.status_code == 204

    def test_a_deleted_report_can_no_longer_be_read(self, client):
        # Arrange
        register_and_login(client)
        created = create_report(client, VALID_REPORT_TEXT)
        report_id = created.json()["id"]
        client.delete(f"/api/reports/{report_id}")

        # Act
        response = client.get(f"/api/reports/{report_id}")

        # Assert
        assert response.status_code == 404

    def test_a_deleted_report_no_longer_appears_in_the_list(self, client):
        # Arrange
        register_and_login(client)
        created = create_report(client, VALID_REPORT_TEXT)
        report_id = created.json()["id"]
        client.delete(f"/api/reports/{report_id}")

        # Act
        response = client.get("/api/reports")

        # Assert
        assert response.json() == {"items": [], "total": 0}

    def test_deleting_another_users_report_returns_404_and_does_not_delete_it(self, client):
        """US-02 criterion 2 and NFR-15 apply to delete too: a foreign id
        returns 404, and critically the report survives the attempt."""
        # Arrange
        register_and_login(client, "owner@example.com")
        created = create_report(client, VALID_REPORT_TEXT)
        report_id = created.json()["id"]
        client.post("/api/auth/logout")
        register_and_login(client, "attacker@example.com")

        # Act
        delete_response = client.delete(f"/api/reports/{report_id}")

        # Assert
        assert delete_response.status_code == 404
        client.post("/api/auth/logout")
        register_and_login(client, "owner@example.com")
        assert client.get(f"/api/reports/{report_id}").status_code == 200

    def test_deleting_an_unknown_report_returns_404(self, client):
        # Arrange
        register_and_login(client)
        unknown_id = "00000000-0000-0000-0000-000000000000"

        # Act
        response = client.delete(f"/api/reports/{unknown_id}")

        # Assert
        assert response.status_code == 404

    def test_deleting_a_report_requires_authentication(self, client):
        # Arrange / Act
        response = client.delete("/api/reports/00000000-0000-0000-0000-000000000000")

        # Assert
        assert response.status_code == 401
