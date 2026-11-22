"""Why a candidate was considered similar (US-22, FR-17): the key terms the
report and the candidate share, and the fields that match, such as the
same error or the same component.

The similarity score itself comes from embeddings, which cannot say why
two texts are close. This is a separate, deterministic reading of the two
texts that gives a person something concrete to check, so it never changes
a score or a label. Computed when the candidates are read, never stored.
"""

import re
from collections import Counter

from pydantic import BaseModel

from app.triage.rules import suggest_category

MAX_TERMS = 8

# Words that carry no meaning about the bug itself: ordinary English
# function words, and words every bug report uses.
_STOPWORDS = frozenset(
    " ".join(
        (
            "about above after again against all also although always am an and any are",
            "around as at be because been before being below between both but by can",
            "cannot could did does doing done down during each either else even ever every",
            "for from further get gets getting got had has have having he her here hers",
            "him his how however i if in into is it its itself just let like may me might",
            "more most much must my never no nor not now of off on once one only or other",
            "our out over own per please same see seen she should since so some still such",
            "than that the their them then there these they this those though through to",
            "too try tried trying under until up upon us very via was way we were what",
            "when where whether which while who whom why will with within without would yet",
            "you your yours",
            "bug bugs issue issues problem problems report reported reporting reproduce",
            "expected actual behaviour behavior steps step instead happens happened",
            "happening occur occurs occurred error errors using use used works working",
            "work worked time times thing things something anything nothing app",
            "application user users click clicked clicking open opened opening shows",
            "shown show showing want wanted need needs able unable seems seem new",
            "go goes going gone went come comes came get make makes made",
        )
    ).split()
)

_ERROR_PATTERNS = (
    re.compile(r"\b[A-Z][A-Za-z0-9]*(?:Error|Exception)\b"),
    re.compile(r"\bHTTP\s?[1-5]\d{2}\b", re.IGNORECASE),
    re.compile(r"\b(?:status|code)\s?[45]\d{2}\b", re.IGNORECASE),
    re.compile(r"\b(?:ERR|E)_[A-Z0-9_]{2,}\b"),
    re.compile(r"\b(?:segmentation fault|null pointer|stack overflow|out of memory)\b", re.I),
)

_PLATFORMS = {
    "chrome": "Chrome",
    "chromium": "Chromium",
    "firefox": "Firefox",
    "safari": "Safari",
    "edge": "Edge",
    "opera": "Opera",
    "windows": "Windows",
    "macos": "macOS",
    "linux": "Linux",
    "ubuntu": "Ubuntu",
    "android": "Android",
    "ios": "iOS",
    "iphone": "iPhone",
    "ipad": "iPad",
}

_WORD = re.compile(r"[a-z][a-z0-9_+#.-]*[a-z0-9]|[a-z]")


class MatchingField(BaseModel):
    """One field both texts agree on: its name and the shared value."""

    field: str
    value: str


class Explanation(BaseModel):
    """US-22 criterion 1: shared key terms, and matching fields such as the
    same component or the same error."""

    shared_terms: list[str]
    matching_fields: list[MatchingField]


def _normalise(word: str) -> str:
    """A light plural fold, so "crashes" and "crash", or "settings" and
    "setting", count as one term."""
    if len(word) > 4 and word.endswith("es") and (word[-3] in "sxz" or word[-4:-2] in ("ch", "sh")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def _terms(text: str) -> tuple[Counter[str], dict[str, str]]:
    """Each key term's count, folded, and the form the text first used for
    it, which is what a person is shown."""
    counts: Counter[str] = Counter()
    written: dict[str, str] = {}
    for raw in _WORD.findall(text.lower()):
        word = raw.strip(".-")
        if len(word) < 3 or word in _STOPWORDS or word.isdigit():
            continue
        folded = _normalise(word)
        if folded in _STOPWORDS:
            continue
        counts[folded] += 1
        written.setdefault(folded, word)
    return counts, written


def _errors(text: str) -> set[str]:
    found: set[str] = set()
    for pattern in _ERROR_PATTERNS:
        found.update(" ".join(match.split()) for match in pattern.findall(text))
    return found


def _platforms(text: str) -> set[str]:
    words = set(re.findall(r"[a-z]+", text.lower()))
    return {name for word, name in _PLATFORMS.items() if word in words}


def _component(text: str) -> str | None:
    """The category the triage rules read in the text, when they found any
    specific wording. Functional is what they give with no signal, so it
    says nothing about a shared component and is left out."""
    category = suggest_category(text).value
    return None if category == "Functional" else category


def explain(report_text: str, candidate_text: str) -> Explanation:
    """The shared key terms, most frequent across both texts first, as the
    report wrote them, and the fields that match."""
    report_terms, written = _terms(report_text)
    candidate_terms, _ = _terms(candidate_text)
    shared = set(report_terms) & set(candidate_terms)
    ranked = sorted(shared, key=lambda t: (-(report_terms[t] + candidate_terms[t]), t))
    ranked = [written[term] for term in ranked]

    fields: list[MatchingField] = []
    errors_lower = {e.lower(): e for e in _errors(candidate_text)}
    for error in sorted(_errors(report_text)):
        if error.lower() in errors_lower:
            fields.append(MatchingField(field="Error", value=error))
    component = _component(report_text)
    if component is not None and component == _component(candidate_text):
        fields.append(MatchingField(field="Component", value=component))
    for platform in sorted(_platforms(report_text) & _platforms(candidate_text)):
        fields.append(MatchingField(field="Environment", value=platform))

    return Explanation(shared_terms=ranked[:MAX_TERMS], matching_fields=fields)
