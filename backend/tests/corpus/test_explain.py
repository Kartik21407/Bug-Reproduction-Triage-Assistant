"""Tests for why a candidate was considered similar (app/corpus/explain.py,
US-22)."""

from app.corpus.explain import MAX_TERMS, explain

REPORT = (
    "The login page crashes on Chrome when I submit a wrong password. "
    "Console shows TypeError: Cannot read properties of undefined."
)
CANDIDATE = (
    "Login page crash after a wrong password\n"
    "On Chrome 120 the login form throws TypeError and the page goes blank."
)


def _fields(explanation) -> set[tuple[str, str]]:
    return {(f.field, f.value) for f in explanation.matching_fields}


def test_shared_key_terms_are_shown():
    """US-22 criterion 1: shared key terms."""
    result = explain(REPORT, CANDIDATE)

    assert {"login", "page", "crashes", "password", "wrong"} <= set(result.shared_terms)


def test_ordinary_words_are_not_key_terms():
    result = explain("The app shows an error when I click it", "It shows an error when I click")

    assert result.shared_terms == []


def test_the_same_error_is_a_matching_field():
    """US-22 criterion 1: "same error"."""
    assert ("Error", "TypeError") in _fields(explain(REPORT, CANDIDATE))


def test_the_same_component_is_a_matching_field():
    """US-22 criterion 1: "same component", read by the same rules that
    suggest the category."""
    assert ("Component", "Authentication") in _fields(explain(REPORT, CANDIDATE))


def test_the_same_platform_is_a_matching_field():
    assert ("Environment", "Chrome") in _fields(explain(REPORT, CANDIDATE))


def test_nothing_matches_when_the_texts_differ():
    result = explain(
        "Uploading a photo fails with HTTP 413 on Firefox",
        "The dark theme colours are wrong in Safari settings",
    )

    assert result.shared_terms == []
    assert result.matching_fields == []


def test_different_errors_do_not_match():
    result = explain("Crash with TypeError in the cart", "Crash with ValueError in the cart")

    assert ("Error", "TypeError") not in _fields(result)
    assert all(field.field != "Error" for field in result.matching_fields)


def test_at_most_eight_terms_most_frequent_first():
    words = "alpha bravo charlie delta foxtrot golf hotel india juliet kilo"
    report = f"{words} kilo kilo"
    candidate = f"{words} kilo"

    result = explain(report, candidate)

    assert len(result.shared_terms) == MAX_TERMS
    assert result.shared_terms[0] == "kilo"
