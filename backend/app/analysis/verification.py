"""Deterministic verification of model-extracted fields (FR-27, ADR-014).

Nothing the model produces is trusted until it passes through here. This
module decides every label; the model's own stated confidence is carried
through for the user to see but never decides anything (the governing
principle in the root CLAUDE.md). Nothing in this module calls a model or
depends on one being reachable, which is what lets it be tested completely
on its own.
"""

import re

from app.analysis.schema import (
    EnvironmentDetail,
    ExtractedField,
    ExtractionResult,
    Label,
    RawEnvironmentDetail,
    RawExtractionResult,
    RawModelField,
)

# Title, summary and condensed reproduction steps are written by the model,
# not copied, so a verbatim substring check cannot apply to them. These are
# judged on whether the value shares real content with the report itself
# (ADR-014, US-09 criterion 4), and the only two outcomes are Explicit or
# Inferred; Missing is handled separately when the model leaves the field
# out entirely.
WRITTEN_FIELDS = frozenset({"title", "summary", "steps"})

# US-10 criterion 3: the same concept written differently by different
# reporters is stored under one name (for example "chrome" and "Chrome
# browser" both become "browser", ADR-015). This is a code decision, not
# left to the model's own wording, since two reports about the same kind
# of detail must be comparable later without the model having to be
# consistent across calls. Not a fixed list of environment fields (FR-07);
# only these aliases for common concepts are collapsed, everything else
# the model names passes through unchanged, lowercased and trimmed.
_ENVIRONMENT_NAME_SYNONYMS: dict[str, str] = {
    "chrome": "browser",
    "firefox": "browser",
    "safari": "browser",
    "edge": "browser",
    "chrome browser": "browser",
    "web browser": "browser",
    "browser type": "browser",
    "browser name": "browser",
    "browser version": "browser",
    "windows": "os",
    "macos": "os",
    "mac os": "os",
    "linux": "os",
    "ios": "os",
    "android": "os",
    "operating system": "os",
    "os version": "os",
    "platform": "os",
    "app version": "version",
    "application version": "version",
    "software version": "version",
    "version number": "version",
    "device type": "device",
    "device model": "device",
    "db": "database",
    "database version": "database",
    "database type": "database",
    "runtime version": "runtime",
    "language version": "runtime",
    "node version": "runtime",
}


def normalise_environment_name(name: str) -> str:
    """Collapses a known alias to its canonical environment detail name
    (US-10 criterion 3). An unrecognised name is still lowercased and
    trimmed, so "Browser" and "browser" from two different reports are at
    least comparable, without inventing a canonical name for a concept
    this list does not know about."""
    cleaned = re.sub(r"\s+", " ", name.strip().lower())
    return _ENVIRONMENT_NAME_SYNONYMS.get(cleaned, cleaned)


_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "to",
        "of",
        "in",
        "on",
        "at",
        "for",
        "with",
        "and",
        "or",
        "but",
        "it",
        "its",
        "this",
        "that",
        "i",
        "my",
        "me",
        "so",
        "then",
        "when",
        "there",
        "here",
        "has",
        "have",
        "had",
        "not",
        "no",
    }
)

_WORD_PATTERN = re.compile(r"[a-z0-9]+")


def _content_words(text: str) -> set[str]:
    """Lowercased words with stopwords and punctuation stripped. Not a
    linguistic tool, just enough to compare whether two pieces of text are
    talking about the same thing."""
    words = _WORD_PATTERN.findall(text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}


def shares_content(a: str, b: str) -> bool:
    """True when a and b share enough content words that one can be said
    to support the other. At least half of the shorter text's content
    words have to appear in the longer one."""
    words_a = _content_words(a)
    words_b = _content_words(b)
    if not words_a or not words_b:
        return False
    shared = words_a & words_b
    if not shared:
        return False
    shorter = min(len(words_a), len(words_b))
    return len(shared) / shorter >= 0.5


def _normalise_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def quote_is_verbatim(quote: str, report_text: str) -> bool:
    """Case insensitive, whitespace normalised substring check: does the
    quote appear in the report at all (FR-27's first check)."""
    if not quote.strip():
        return False
    return _normalise_whitespace(quote) in _normalise_whitespace(report_text)


def _label_written_field(raw: RawModelField, report_text: str) -> Label:
    """Written fields (title, summary, steps) skip the verbatim check,
    since a paraphrase is never a literal substring by definition, and are
    judged only on whether the value shares real content with the report
    (US-09 criterion 4)."""
    if shares_content(raw.value, report_text):
        return Label.EXPLICIT
    return Label.INFERRED


def _label_ordinary_field(raw: RawModelField, report_text: str) -> Label:
    """The general FR-27 rule: the quote must be verbatim in the report
    first; only then does whether it supports the value decide Explicit
    versus Inferred."""
    if not quote_is_verbatim(raw.source_quote, report_text):
        return Label.UNVERIFIED
    quote_normalised = _normalise_whitespace(raw.source_quote)
    value_normalised = _normalise_whitespace(raw.value)
    if value_normalised in quote_normalised or shares_content(raw.value, raw.source_quote):
        return Label.EXPLICIT
    return Label.INFERRED


def verify_field(field_name: str, raw: RawModelField | None, report_text: str) -> ExtractedField:
    """Verifies one field against the report text and assigns its label.
    A field the model did not fill is Missing; nothing else needs
    checking in that case (FR-09)."""
    if raw is None:
        return ExtractedField(value=None, source_quote=None, label=Label.MISSING)

    if field_name in WRITTEN_FIELDS:
        label = _label_written_field(raw, report_text)
    else:
        label = _label_ordinary_field(raw, report_text)

    return ExtractedField(
        value=raw.value,
        source_quote=raw.source_quote,
        label=label,
        confidence=raw.confidence,
        reason=raw.reason,
    )


def verify_environment_detail(raw: RawEnvironmentDetail, report_text: str) -> EnvironmentDetail:
    """Verifies one environment name/value pair the same way an ordinary
    field is verified: the quote must be verbatim, and must support the
    value (FR-07, ADR-015)."""
    if not quote_is_verbatim(raw.source_quote, report_text):
        label = Label.UNVERIFIED
    else:
        quote_normalised = _normalise_whitespace(raw.source_quote)
        value_normalised = _normalise_whitespace(raw.value)
        if value_normalised in quote_normalised or shares_content(raw.value, raw.source_quote):
            label = Label.EXPLICIT
        else:
            label = Label.INFERRED

    return EnvironmentDetail(
        name=normalise_environment_name(raw.name),
        value=raw.value,
        source_quote=raw.source_quote,
        label=label,
    )


# US-09 criterion 5: a report producing more than seven steps is flagged
# for human review rather than shortened automatically. The threshold is
# a code decision, like everything else in this module; the full list is
# always kept, never truncated to fit it.
MAX_STEPS_BEFORE_REVIEW = 7


def steps_need_review(steps: list[ExtractedField]) -> bool:
    """True when the step count is over the threshold that calls for a
    human to look the list over, rather than trusting it was condensed
    correctly (US-09 criterion 5)."""
    return len(steps) > MAX_STEPS_BEFORE_REVIEW


def verify_extraction(raw: RawExtractionResult, report_text: str) -> ExtractionResult:
    """Runs verification over an entire raw model response, producing the
    fully labelled result nothing downstream trusts until it has passed
    through this function."""
    return ExtractionResult(
        title=verify_field("title", raw.title, report_text),
        summary=verify_field("summary", raw.summary, report_text),
        expected_behaviour=verify_field("expected_behaviour", raw.expected_behaviour, report_text),
        actual_behaviour=verify_field("actual_behaviour", raw.actual_behaviour, report_text),
        frequency=verify_field("frequency", raw.frequency, report_text),
        steps=[verify_field("steps", step, report_text) for step in raw.steps],
        environment=[verify_environment_detail(detail, report_text) for detail in raw.environment],
        error_messages=[
            verify_field("error_messages", msg, report_text) for msg in raw.error_messages
        ],
    )
