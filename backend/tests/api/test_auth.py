"""Tests for US-01: register, log in, log out, and that passwords are
stored hashed."""

from sqlalchemy import select

from app.models.core import User
from tests.conftest import (
    VALID_PASSWORD,
    TestingSessionLocal,
    login_user,
    register_and_login,
    register_user,
)


class TestRegister:
    def test_valid_registration_succeeds(self, client):
        # Arrange
        payload = {"email": "new.user@example.com", "password": VALID_PASSWORD}

        # Act
        response = register_user(client, payload["email"], payload["password"])

        # Assert
        assert response.status_code == 201
        body = response.json()
        assert body["email"] == payload["email"]
        assert "password" not in body
        assert "password_hash" not in body

    def test_password_under_8_characters_is_rejected(self, client):
        """US-01 criterion 1: registration requires a password of at least
        8 characters."""
        # Arrange / Act
        response = register_user(client, "short.pw@example.com", "short1")

        # Assert
        assert response.status_code == 422

    def test_invalid_email_is_rejected(self, client):
        """US-01 criterion 1: registration requires a valid email."""
        # Arrange / Act
        response = register_user(client, "not-an-email", VALID_PASSWORD)

        # Assert
        assert response.status_code == 422

    def test_duplicate_email_returns_account_already_exists(self, client):
        """US-01 criterion 2: a duplicate email shows "Account already
        exists"."""
        # Arrange
        register_user(client, "taken@example.com")

        # Act
        response = register_user(client, "taken@example.com")

        # Assert
        assert response.status_code == 409
        assert response.json()["detail"] == "Account already exists"

    def test_email_is_stored_lowercase_so_case_cannot_bypass_the_duplicate_check(self, client):
        # Arrange
        register_user(client, "Mixed.Case@Example.com")

        # Act
        response = register_user(client, "mixed.case@example.com")

        # Assert
        assert response.status_code == 409

    def test_password_is_stored_hashed_not_plaintext(self, client):
        """US-01 criterion 4 and NFR-03: passwords are stored only as
        salted hashes."""
        # Arrange / Act
        register_user(client, "hashed@example.com", VALID_PASSWORD)

        # Assert
        with TestingSessionLocal() as db:
            user = db.execute(select(User).where(User.email == "hashed@example.com")).scalar_one()
            assert user.password_hash != VALID_PASSWORD
            assert VALID_PASSWORD not in user.password_hash
            assert user.password_hash.startswith("$argon2")


class TestLogin:
    def test_valid_credentials_return_the_user_and_set_a_session_cookie(self, client):
        # Arrange
        register_user(client, "login@example.com")

        # Act
        response = login_user(client, "login@example.com")

        # Assert
        assert response.status_code == 200
        assert response.json()["email"] == "login@example.com"
        assert "session" in response.cookies

    def test_session_cookie_is_httponly_and_samesite_lax(self, client):
        # Arrange
        register_user(client, "cookieflags@example.com")

        # Act
        response = login_user(client, "cookieflags@example.com")

        # Assert
        set_cookie = response.headers.get("set-cookie", "")
        assert "HttpOnly" in set_cookie
        assert "samesite=lax" in set_cookie.lower()

    def test_wrong_password_returns_generic_error(self, client):
        """US-01 criterion 3: wrong credentials show a generic error that
        does not reveal which field was wrong."""
        # Arrange
        register_user(client, "wrongpw@example.com")

        # Act
        response = login_user(client, "wrongpw@example.com", "not-the-password")

        # Assert
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"

    def test_unknown_email_returns_the_same_generic_error(self, client):
        """US-01 criterion 3: the message for an unknown email matches the
        message for a wrong password, so neither is distinguishable."""
        # Arrange / Act
        response = login_user(client, "never-registered@example.com", VALID_PASSWORD)

        # Assert
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"


class TestCurrentUser:
    def test_me_without_a_session_returns_401(self, client):
        # Arrange / Act
        response = client.get("/api/auth/me")

        # Assert
        assert response.status_code == 401

    def test_me_with_a_session_returns_the_user(self, client):
        # Arrange
        register_and_login(client, "me@example.com")

        # Act
        response = client.get("/api/auth/me")

        # Assert
        assert response.status_code == 200
        assert response.json()["email"] == "me@example.com"


class TestLogout:
    def test_logout_ends_the_session(self, client):
        """US-01 criterion 5: logging out ends the session."""
        # Arrange
        register_and_login(client, "logout@example.com")
        assert client.get("/api/auth/me").status_code == 200

        # Act
        logout_response = client.post("/api/auth/logout")

        # Assert
        assert logout_response.status_code == 204
        assert client.get("/api/auth/me").status_code == 401

    def test_logout_without_a_session_returns_401(self, client):
        # Arrange / Act
        response = client.post("/api/auth/logout")

        # Assert
        assert response.status_code == 401
