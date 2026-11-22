"""Tests for the administrator role and its endpoints (app/api/admin.py,
app/admin.py): deactivating accounts (US-03), setting the duplicate
thresholds (US-31), and controlling the automatic corpus import (US-28)."""

import pytest

from app.admin import admin_emails, set_admin
from app.corpus import sync
from tests.conftest import (
    TestingSessionLocal,
    create_report,
    login_user,
    register_and_login,
    register_user,
)

ADMIN = "admin@example.com"
MEMBER = "member@example.com"


def _make_admin(email: str = ADMIN) -> None:
    with TestingSessionLocal() as db:
        set_admin(db, email, is_admin=True)


def _signed_in_admin(client) -> None:
    register_user(client, ADMIN)
    _make_admin()
    login_user(client, ADMIN)


def _user_id(client, email: str) -> str:
    users = client.get("/api/admin/users").json()
    return next(user["id"] for user in users if user["email"] == email)


class TestAdminCommand:
    def test_make_admin_grants_the_role(self, client):
        """ADR-030: the role is granted by the operator command only."""
        register_user(client, ADMIN)

        with TestingSessionLocal() as db:
            message = set_admin(db, "ADMIN@example.com ", is_admin=True)
            emails = admin_emails(db)

        assert message == "admin@example.com is now an administrator."
        assert emails == [ADMIN]

    def test_revoke_admin_removes_the_role(self, client):
        register_user(client, ADMIN)
        _make_admin()

        with TestingSessionLocal() as db:
            set_admin(db, ADMIN, is_admin=False)
            emails = admin_emails(db)

        assert emails == []

    def test_an_unknown_email_is_refused(self, client):
        with TestingSessionLocal() as db, pytest.raises(LookupError):
            set_admin(db, "nobody@example.com", is_admin=True)

    def test_the_current_user_says_whether_they_are_an_administrator(self, client):
        _signed_in_admin(client)

        body = client.get("/api/auth/me").json()

        assert body["is_admin"] is True


class TestOnlyAdministrators:
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("get", "/api/admin/users"),
            ("get", "/api/admin/settings/duplicate-thresholds"),
            ("get", "/api/admin/corpus-sync"),
            ("post", "/api/admin/corpus-sync/run"),
        ],
    )
    def test_an_ordinary_user_gets_403(self, client, method, path):
        """US-03 criterion 3: only the administrator role sees this option."""
        register_and_login(client, MEMBER)

        response = getattr(client, method)(path)

        assert response.status_code == 403
        assert response.json() == {"detail": "Administrators only"}

    def test_no_session_gets_401(self, client):
        assert client.get("/api/admin/users").status_code == 401

    def test_a_user_cannot_make_themselves_admin_through_the_api(self, client):
        register_and_login(client, MEMBER)

        client.patch("/api/auth/me", json={"is_admin": True})

        assert client.get("/api/auth/me").json()["is_admin"] is False


class TestDeactivation:
    def test_the_user_list_shows_every_account_with_its_report_count(self, client):
        register_and_login(client, MEMBER)
        create_report(client)
        _signed_in_admin(client)

        users = {user["email"]: user for user in client.get("/api/admin/users").json()}

        assert users[MEMBER]["report_count"] == 1
        assert users[MEMBER]["is_active"] is True
        assert users[ADMIN]["is_admin"] is True
        assert "password_hash" not in users[MEMBER]

    def test_a_deactivated_user_cannot_log_in(self, client):
        """US-03 criterion 1."""
        register_user(client, MEMBER)
        _signed_in_admin(client)
        client.patch(f"/api/admin/users/{_user_id(client, MEMBER)}", json={"is_active": False})

        response = login_user(client, MEMBER)

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "This account has been deactivated. Contact an administrator."
        )

    def test_a_wrong_password_on_a_deactivated_account_reveals_nothing(self, client):
        """The deactivated message is only shown to someone who knows the
        password; anyone else gets the usual generic message (US-01
        criterion 3)."""
        register_user(client, MEMBER)
        _signed_in_admin(client)
        client.patch(f"/api/admin/users/{_user_id(client, MEMBER)}", json={"is_active": False})

        response = login_user(client, MEMBER, "not-the-password")

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"

    def test_a_deactivated_users_session_ends_at_once(self, client):
        """US-03 criterion 1: a session already open stops working too."""
        register_user(client, MEMBER)
        _signed_in_admin(client)
        member_id = _user_id(client, MEMBER)
        login_user(client, MEMBER)
        cookie = client.cookies.get("session")
        login_user(client, ADMIN)
        client.patch(f"/api/admin/users/{member_id}", json={"is_active": False})
        client.cookies.set("session", cookie)

        response = client.get("/api/auth/me")

        assert response.status_code == 401

    def test_the_users_data_remains_intact(self, client):
        """US-03 criterion 2."""
        register_and_login(client, MEMBER)
        report_id = create_report(client).json()["id"]
        _signed_in_admin(client)
        member_id = _user_id(client, MEMBER)
        client.patch(f"/api/admin/users/{member_id}", json={"is_active": False})

        client.patch(f"/api/admin/users/{member_id}", json={"is_active": True})
        login_user(client, MEMBER)

        assert client.get(f"/api/reports/{report_id}").status_code == 200

    def test_deactivating_keeps_the_report_count(self, client):
        """US-03 criterion 2, seen from the admin list."""
        register_and_login(client, MEMBER)
        create_report(client)
        _signed_in_admin(client)
        member_id = _user_id(client, MEMBER)

        body = client.patch(f"/api/admin/users/{member_id}", json={"is_active": False}).json()

        assert body["is_active"] is False
        assert body["report_count"] == 1

    def test_an_administrator_cannot_deactivate_themselves(self, client):
        _signed_in_admin(client)

        response = client.patch(
            f"/api/admin/users/{_user_id(client, ADMIN)}", json={"is_active": False}
        )

        assert response.status_code == 409
        assert client.get("/api/auth/me").status_code == 200

    def test_an_unknown_user_is_404(self, client):
        _signed_in_admin(client)

        response = client.patch(
            "/api/admin/users/00000000-0000-4000-8000-000000000000", json={"is_active": False}
        )

        assert response.status_code == 404


class TestThresholds:
    def test_the_defaults_are_shown_until_changed(self, client):
        _signed_in_admin(client)

        body = client.get("/api/admin/settings/duplicate-thresholds").json()

        assert body == {
            "likely": 0.8,
            "possible": 0.6,
            "default_likely": 0.8,
            "default_possible": 0.6,
            "customised": False,
        }

    def test_two_thresholds_between_0_and_1_can_be_set(self, client):
        """US-31 criterion 1."""
        _signed_in_admin(client)

        response = client.put(
            "/api/admin/settings/duplicate-thresholds", json={"likely": 0.9, "possible": 0.5}
        )

        assert response.status_code == 200
        assert response.json()["likely"] == 0.9
        assert response.json()["possible"] == 0.5
        assert response.json()["customised"] is True

    @pytest.mark.parametrize(
        ("likely", "possible", "message"),
        [
            (1.2, 0.5, "The likely threshold must be between 0 and 1."),
            (0.8, -0.1, "The possible threshold must be between 0 and 1."),
            (0.6, 0.6, "The possible threshold must be lower than the likely threshold."),
            (0.5, 0.7, "The possible threshold must be lower than the likely threshold."),
        ],
    )
    def test_invalid_thresholds_are_rejected_with_a_reason(self, client, likely, possible, message):
        """US-31 criterion 1: "with validation"."""
        _signed_in_admin(client)

        response = client.put(
            "/api/admin/settings/duplicate-thresholds",
            json={"likely": likely, "possible": possible},
        )

        assert response.status_code == 422
        assert response.json() == {"detail": message}
        assert client.get("/api/admin/settings/duplicate-thresholds").json()["likely"] == 0.8

    def test_reset_goes_back_to_the_defaults(self, client):
        _signed_in_admin(client)
        client.put(
            "/api/admin/settings/duplicate-thresholds", json={"likely": 0.9, "possible": 0.5}
        )

        body = client.delete("/api/admin/settings/duplicate-thresholds").json()

        assert (body["likely"], body["possible"], body["customised"]) == (0.8, 0.6, False)


class TestCorpusSyncSettings:
    def test_no_repository_means_no_automatic_import(self, client):
        _signed_in_admin(client)

        body = client.get("/api/admin/corpus-sync").json()

        assert body["repository"] is None
        assert body["state"] is None
        assert body["running"] is False

    def test_a_repository_can_be_chosen(self, client):
        _signed_in_admin(client)

        body = client.put("/api/admin/corpus-sync", json={"repository": " acme/app "}).json()

        assert body["repository"] == "acme/app"

    def test_a_repository_that_is_not_owner_slash_name_is_rejected(self, client):
        _signed_in_admin(client)

        response = client.put("/api/admin/corpus-sync", json={"repository": "not a repo"})

        assert response.status_code == 422
        assert "owner/name" in response.json()["detail"]

    def test_an_empty_repository_switches_the_import_off(self, client):
        _signed_in_admin(client)
        client.put("/api/admin/corpus-sync", json={"repository": "acme/app"})

        body = client.put("/api/admin/corpus-sync", json={"repository": ""}).json()

        assert body["repository"] is None

    def test_running_without_a_repository_is_refused(self, client):
        _signed_in_admin(client)

        response = client.post("/api/admin/corpus-sync/run")

        assert response.status_code == 409

    def test_run_now_imports_and_reports_progress(self, client, monkeypatch):
        """US-28: started by hand from the admin page."""
        pages = {
            sync.first_page_url("acme/app"): (
                [{"number": 1, "title": "Crash", "body": "It crashes", "html_url": "https://x/1"}],
                None,
            )
        }
        monkeypatch.setattr(sync.github, "_get_page", lambda url, token: pages[url])
        _signed_in_admin(client)
        client.put("/api/admin/corpus-sync", json={"repository": "acme/app"})

        response = client.post("/api/admin/corpus-sync/run")
        state = client.get("/api/admin/corpus-sync").json()["state"]

        assert response.status_code == 202
        assert state["status"] == "complete"
        assert state["imported"] == 1
