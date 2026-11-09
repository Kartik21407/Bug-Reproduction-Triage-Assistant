"""Tests for the duplicate label boundaries (app/corpus/search.py,
US-20 criterion 2), checked at the exact threshold values."""

import pytest

from app.corpus.search import LIKELY_DUPLICATE, POSSIBLE_DUPLICATE, label_for


@pytest.mark.parametrize(
    ("score", "label"),
    [
        (1.0, LIKELY_DUPLICATE),
        (0.80, LIKELY_DUPLICATE),
        (0.7999, POSSIBLE_DUPLICATE),
        (0.60, POSSIBLE_DUPLICATE),
        (0.5999, None),
        (0.0, None),
    ],
)
def test_score_boundaries(score, label):
    """US-20 criterion 2: a score of 0.80 or above is labelled "Likely
    duplicate", 0.60 to 0.80 "Possible duplicate", and lower scores are
    hidden."""
    assert label_for(score) == label


def test_neither_label_states_that_a_report_is_a_duplicate():
    """US-20 criterion 3."""
    for label in (LIKELY_DUPLICATE, POSSIBLE_DUPLICATE):
        assert label.split()[0] in ("Likely", "Possible")
