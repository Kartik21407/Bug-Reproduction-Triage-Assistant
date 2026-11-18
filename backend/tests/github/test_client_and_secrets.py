"""Tests for the GitHub client's request handling (app/github/client.py,
DR-09) and the encryption of stored secrets (app/security.py, US-26
criterion 3). The network is never touched."""

import pytest
from cryptography.fernet import Fernet

from app.config import get_settings
from app.github import client
from app.security import (
    SecretStoreUnavailableError,
    SecretUnreadableError,
    decrypt_secret,
    encrypt_secret,
)


class TestErrors:
    @pytest.mark.parametrize(
        ("status", "headers", "expected"),
        [
            (401, {}, "GitHub did not accept this token."),
            (429, {}, "rate limit"),
            (403, {"x-ratelimit-remaining": "0"}, "rate limit"),
            (403, {}, "Issues: Read and write"),
            (404, {}, "could not find this repository"),
            (410, {}, "Issues are switched off"),
            (422, {}, "rejected the issue: Validation Failed"),
            (500, {}, "error (500)"),
        ],
    )
    def test_each_github_refusal_becomes_a_readable_message(
        self, monkeypatch, status, headers, expected
    ):
        monkeypatch.setattr(
            client, "_send", lambda *a: (status, headers, {"message": "Validation Failed"})
        )

        with pytest.raises(client.GitHubError) as raised:
            client.create_issue("t", "o/r", "title", "body", [])

        assert expected in raised.value.message
        assert raised.value.status == status

    def test_an_invalid_token_is_its_own_error_type(self, monkeypatch):
        monkeypatch.setattr(client, "_send", lambda *a: (401, {}, None))

        with pytest.raises(client.GitHubAuthError):
            client.authenticated_login("t")

    def test_no_message_ever_contains_the_token(self, monkeypatch):
        monkeypatch.setattr(client, "_send", lambda *a: (403, {}, {"message": "nope"}))

        with pytest.raises(client.GitHubError) as raised:
            client.create_issue("secret-token-value", "o/r", "t", "b", [])

        assert "secret-token-value" not in raised.value.message


class TestRepositoryPages:
    def test_every_page_is_followed(self, monkeypatch):
        pages = {
            "first": (
                200,
                {"link": '<https://api.github.com/next>; rel="next"'},
                [{"full_name": "b/two", "has_issues": True}],
            ),
            "https://api.github.com/next": (200, {}, [{"full_name": "a/one", "has_issues": True}]),
        }

        def fake(method, url, token, body):
            return pages["first"] if "user/repos" in url else pages[url]

        monkeypatch.setattr(client, "_send", fake)

        names = [r.full_name for r in client.issue_repositories("t")]

        assert names == ["a/one", "b/two"]


class TestSecrets:
    def test_a_secret_round_trips_and_is_not_stored_in_plain_text(self):
        ciphertext = encrypt_secret("ghp_example")

        assert "ghp_example" not in ciphertext
        assert decrypt_secret(ciphertext) == "ghp_example"

    def test_without_a_key_nothing_can_be_stored(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "token_encryption_key", "")

        with pytest.raises(SecretStoreUnavailableError):
            encrypt_secret("x")

    def test_a_secret_stored_under_another_key_is_unreadable(self, monkeypatch):
        ciphertext = encrypt_secret("x")
        monkeypatch.setattr(get_settings(), "token_encryption_key", Fernet.generate_key().decode())

        with pytest.raises(SecretUnreadableError):
            decrypt_secret(ciphertext)
