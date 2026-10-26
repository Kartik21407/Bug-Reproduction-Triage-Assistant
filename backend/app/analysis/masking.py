"""Pattern-based masking of likely secrets (FR-29, NFR-06, ADR-017).

Detection here is the automatic half of masking only: emails, passwords,
API keys and tokens found by pattern, before anything is stored or sent to
a model. The review half (restoring a false positive, marking further text
by hand) is a user action; `mask_literal_occurrences` is what the API layer
calls once the user picks a value to mask manually, since every occurrence
of that value must be masked too (US-32 criterion 3).

Nothing here calls a model or depends on one being reachable, the same
constraint `verification.py` follows, so detection is fully testable with
plain text.
"""

import re
from enum import StrEnum

# pyrefly: ignore[missing-import]
from pydantic import BaseModel

PLACEHOLDER = "[masked]"


class MaskedItemType(StrEnum):
    """The categories shown to the user during masking review (US-32
    criterion 1). MANUAL covers anything the user chose to mask by hand,
    which by definition was not caught by a pattern."""

    EMAIL = "email"
    PASSWORD = "password"
    API_KEY = "api_key"
    TOKEN = "token"
    MANUAL = "manual"


class MaskedItem(BaseModel):
    """One detected or manually marked span. `start`/`end` are offsets into
    the original text, so a false positive can be restored by putting the
    exact original text back (US-32 criterion 2)."""

    type: MaskedItemType
    original_text: str
    start: int
    end: int


class MaskingResult(BaseModel):
    """What masking review shows the user: the masked copy that would be
    sent onward, and the list of items it was masked for (US-32 criteria 1
    and 5)."""

    masked_text: str
    items: list[MaskedItem]


# Order matters: more specific patterns run first, since a token or API key
# can otherwise be mistaken for something else once it has already been
# consumed by a looser match.
_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# "password", "pwd" or "passwd" followed by a separator and a value with no
# whitespace. Deliberately narrow: a false negative (an unflagged password
# in free prose) is safer than flooding review with false positives on
# every sentence containing the word "password".
_PASSWORD_PATTERN = re.compile(r"(?i)\b(?:password|pwd|passwd)\b\s*[:=]\s*(?P<value>\S+)")

# Common token and API key shapes: a provider prefix followed by an
# unbroken run of key characters, a bearer header, or a three-part
# dot-separated JWT.
_API_KEY_PATTERN = re.compile(
    r"\b(?:sk|pk|ghp|gho|ghu|ghs|ghr|xox[baprs])-[A-Za-z0-9_-]{10,}\b"
    r"|\bAKIA[0-9A-Z]{16}\b"
)
_BEARER_TOKEN_PATTERN = re.compile(r"(?i)\bBearer\s+(?P<value>[A-Za-z0-9._-]{10,})")
_JWT_PATTERN = re.compile(r"\b[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")


def _non_overlapping_matches(
    pattern: re.Pattern[str], text: str, item_type: MaskedItemType, group: str | None = None
) -> list[MaskedItem]:
    items = []
    for match in pattern.finditer(text):
        start, end = match.span(group) if group else match.span()
        items.append(
            MaskedItem(type=item_type, original_text=text[start:end], start=start, end=end)
        )
    return items


def detect_masked_items(text: str) -> list[MaskedItem]:
    """Runs every pattern and returns the detected items, sorted by
    position with overlaps resolved in favour of whichever pattern matched
    first (the more specific ones, checked first)."""
    candidates: list[MaskedItem] = []
    candidates += _non_overlapping_matches(
        _PASSWORD_PATTERN, text, MaskedItemType.PASSWORD, "value"
    )
    candidates += _non_overlapping_matches(_API_KEY_PATTERN, text, MaskedItemType.API_KEY)
    candidates += _non_overlapping_matches(
        _BEARER_TOKEN_PATTERN, text, MaskedItemType.TOKEN, "value"
    )
    candidates += _non_overlapping_matches(_JWT_PATTERN, text, MaskedItemType.TOKEN)
    candidates += _non_overlapping_matches(_EMAIL_PATTERN, text, MaskedItemType.EMAIL)

    candidates.sort(key=lambda item: item.start)

    resolved: list[MaskedItem] = []
    last_end = -1
    for item in candidates:
        if item.start >= last_end:
            resolved.append(item)
            last_end = item.end
    return resolved


def apply_masking(text: str, items: list[MaskedItem]) -> str:
    """Replaces each item's span with the masking placeholder. Items are
    applied from the end of the text backwards so earlier offsets stay
    valid as later ones are replaced."""
    result = text
    for item in sorted(items, key=lambda i: i.start, reverse=True):
        result = result[: item.start] + PLACEHOLDER + result[item.end :]
    return result


def mask_literal_occurrences(text: str, items: list[MaskedItem], value: str) -> list[MaskedItem]:
    """Adds one manual item for every occurrence of `value` in `text`
    (US-32 criterion 3), skipping any span already covered by an existing
    item. Returns the combined, position-sorted list; it does not mutate
    `items`."""
    if not value:
        return list(items)

    covered = [(item.start, item.end) for item in items]
    manual: list[MaskedItem] = []
    start = 0
    while True:
        index = text.find(value, start)
        if index == -1:
            break
        end = index + len(value)
        if not any(index < c_end and end > c_start for c_start, c_end in covered):
            manual.append(
                MaskedItem(type=MaskedItemType.MANUAL, original_text=value, start=index, end=end)
            )
        start = index + 1

    return sorted([*items, *manual], key=lambda item: item.start)


def mask(text: str) -> MaskingResult:
    """The full automatic masking step (FR-29 step 1): detect, then
    produce the masked copy. The review step that follows (restoring a
    false positive, masking further text) works from this result's
    `items`, not from calling this function again."""
    items = detect_masked_items(text)
    return MaskingResult(masked_text=apply_masking(text, items), items=items)
