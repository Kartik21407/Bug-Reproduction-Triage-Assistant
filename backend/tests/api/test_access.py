"""Tests for US-02 and NFR-15: a user sees only their own reports, and
another user's report id returns 404."""

from tests.conftest import create_report, register_and_login


class TestReportList:
    def test_list_returns_only_the_current_users_reports(self, client):
        """US-02 criterion 1: the report list returns only the logged-in
        user's reports."""
        # Arrange
        register_and_login(client, "owner@example.com")
        create_report(client, "This report belongs to the owner account.")
        client.post("/api/auth/logout")
        register_and_login(client, "someone-else@example.com")
        create_report(client, "This report belongs to someone else entirely.")

        # Act
        response = client.get("/api/reports")

        # Assert
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["original_text"] == "This report belongs to someone else entirely."

    def test_list_is_empty_for_a_user_with_no_reports(self, client):
        # Arrange
        register_and_login(client)

        # Act
        response = client.get("/api/reports")

        # Assert
        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0}

    def test_listing_reports_requires_authentication(self, client):
        # Arrange / Act
        response = client.get("/api/reports")

        # Assert
        assert response.status_code == 401


class TestReportOwnership:
    def test_requesting_another_users_report_id_returns_404(self, client):
        """US-02 criterion 2 and NFR-15: requesting another user's report id
        returns 404, not 403."""
        # Arrange
        register_and_login(client, "owner@example.com")
        created = create_report(client, "A report only the owner should be able to read.")
        other_users_report_id = created.json()["id"]
        client.post("/api/auth/logout")
        register_and_login(client, "attacker@example.com")

        # Act
        response = client.get(f"/api/reports/{other_users_report_id}")

        # Assert
        assert response.status_code == 404

    def test_requesting_an_unknown_report_id_returns_404(self, client):
        # Arrange
        register_and_login(client)
        unknown_id = "00000000-0000-0000-0000-000000000000"

        # Act
        response = client.get(f"/api/reports/{unknown_id}")

        # Assert
        assert response.status_code == 404

    def test_unknown_and_foreign_ids_return_the_identical_response(self, client):
        """Both cases return the same body, so a 404 never becomes a signal
        that distinguishes 'does not exist' from 'exists but is not
        yours' (NFR-15)."""
        # Arrange
        register_and_login(client, "owner@example.com")
        created = create_report(client, "A report used to compare the two 404 responses.")
        other_users_report_id = created.json()["id"]
        unknown_id = "00000000-0000-0000-0000-000000000000"
        client.post("/api/auth/logout")
        register_and_login(client, "attacker@example.com")

        # Act
        foreign_response = client.get(f"/api/reports/{other_users_report_id}")
        unknown_response = client.get(f"/api/reports/{unknown_id}")

        # Assert
        assert foreign_response.status_code == unknown_response.status_code == 404
        assert foreign_response.json() == unknown_response.json()

    def test_owner_can_read_their_own_report(self, client):
        # Arrange
        register_and_login(client)
        created = create_report(client, "A report the owner should be able to read back.")
        report_id = created.json()["id"]

        # Act
        response = client.get(f"/api/reports/{report_id}")

        # Assert
        assert response.status_code == 200
        assert response.json()["id"] == report_id

    def test_reading_a_report_requires_authentication(self, client):
        # Arrange
        register_and_login(client)
        created = create_report(client, "A report used only to get a real id.")
        report_id = created.json()["id"]
        client.post("/api/auth/logout")

        # Act
        response = client.get(f"/api/reports/{report_id}")

        # Assert
        assert response.status_code == 401
