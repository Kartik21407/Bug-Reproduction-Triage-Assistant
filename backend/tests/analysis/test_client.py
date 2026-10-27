"""Tests for the Gemini extraction call (FR-28, NFR-18, NFR-19).

Every test here injects a fake `model_call`, never a real Gemini client, so
this suite needs no network access and no API key, and cannot burn quota or
flake on a live model's output.
"""

import json

import pytest

from app.analysis.client import extract, load_system_prompt
from app.analysis.schema import RawExtractionResult
from app.config import Settings

VALID_RESPONSE = json.dumps(
    {
        "title": {
            "value": "Login crashes on wrong password",
            "source_quote": "login crashes",
            "confidence": 0.9,
            "reason": "Stated directly",
        }
    }
)


def _settings() -> Settings:
    return Settings(
        database_url="sqlite://",
        jwt_secret_key="test-secret",
        gemini_api_key="test-key",
    )


class TestLoadSystemPrompt:
    def test_loads_non_empty_text_from_the_prompt_file(self):
        prompt = load_system_prompt()
        assert len(prompt) > 100
        assert "bug triage assistant" in prompt.lower()

    def test_report_text_placeholder_is_never_interpolated_into_the_prompt(self):
        """The prompt file documents that report text is sent as a
        separate message, never concatenated into this string (ADR-019,
        NFR-20's structural boundary)."""
        prompt = load_system_prompt()
        assert "{report_text}" not in prompt
        assert "{{report}}" not in prompt


class TestExtractSuccess:
    def test_a_valid_first_response_is_returned_without_a_retry(self):
        calls = []

        def fake_call(system_prompt: str, report_text: str) -> str:
            calls.append((system_prompt, report_text))
            return VALID_RESPONSE

        result = extract("login crashes", model_call=fake_call, settings=_settings())
        assert isinstance(result, RawExtractionResult)
        assert result.title.value == "Login crashes on wrong password"
        assert len(calls) == 1


class TestExtractRetry:
    def test_a_malformed_first_response_is_retried_once(self):
        calls = []

        def fake_call(system_prompt: str, report_text: str) -> str:
            calls.append(system_prompt)
            if len(calls) == 1:
                return "not json at all"
            return VALID_RESPONSE

        result = extract("login crashes", model_call=fake_call, settings=_settings())
        assert result.title.value == "Login crashes on wrong password"
        assert len(calls) == 2

    def test_the_retry_prompt_includes_the_original_and_a_correction_note(self):
        calls = []

        def fake_call(system_prompt: str, report_text: str) -> str:
            calls.append(system_prompt)
            if len(calls) == 1:
                return "not json"
            return VALID_RESPONSE

        extract("login crashes", model_call=fake_call, settings=_settings())
        first_prompt, retry_prompt = calls
        assert retry_prompt.startswith(first_prompt)
        assert "did not match" in retry_prompt.lower()

    def test_a_response_that_does_not_match_the_schema_is_retried(self):
        calls = []

        def fake_call(system_prompt: str, report_text: str) -> str:
            calls.append(system_prompt)
            if len(calls) == 1:
                return json.dumps({"title": {"value": "only a value, missing required fields"}})
            return VALID_RESPONSE

        result = extract("login crashes", model_call=fake_call, settings=_settings())
        assert result.title.value == "Login crashes on wrong password"
        assert len(calls) == 2


class TestExtractFallback:
    def test_two_malformed_responses_fall_back_to_an_all_missing_result(self):
        """FR-28: after one retry also fails, the caller gets an empty
        analysis, never an exception."""

        def fake_call(system_prompt: str, report_text: str) -> str:
            return "still not json"

        result = extract("login crashes", model_call=fake_call, settings=_settings())
        assert result == RawExtractionResult()
        assert result.title is None

    def test_a_model_call_that_raises_falls_back_instead_of_propagating(self):
        """NFR-18: the model being unreachable, rate limited or timing out
        must not fail the request."""

        def fake_call(system_prompt: str, report_text: str) -> str:
            raise TimeoutError("the model did not respond in time")

        result = extract("login crashes", model_call=fake_call, settings=_settings())
        assert result == RawExtractionResult()

    def test_fallback_does_not_raise_even_when_every_attempt_raises(self):
        def fake_call(system_prompt: str, report_text: str) -> str:
            raise ConnectionError("unreachable")

        try:
            result = extract("login crashes", model_call=fake_call, settings=_settings())
        except Exception as exc:  # pragma: no cover - the assertion below is the real check
            pytest.fail(f"extract() must never raise, got {exc!r}")
        assert result == RawExtractionResult()
