"""Deterministic triage rules (FR-13, FR-14; US-15, US-16, US-17).

Every suggestion is a fixed set of word patterns checked against the
report's text, its logs, and whichever extracted fields are Explicit
(including the user's own answers to follow-up questions). Every
suggestion carries the reason behind it, naming the words that triggered
it (US-15 criterion 2, NFR-10). Nothing here calls a model, and the same
input always produces the same output.

These rules suggest; they never decide. Every value is shown in an
editable field and a person's change always wins (US-15 criterion 4,
DR-02).
"""

import re
from typing import Literal

from pydantic import BaseModel

from app.analysis.schema import ExtractionResult, Label

# DR-03.
SEVERITIES = ("Critical", "High", "Medium", "Low")
# The requirements leave the priority scale open; the team chose P1 to P4 so
# it can never be mistaken for a severity value (DR-02). See ADR-023.
PRIORITIES = ("P1", "P2", "P3", "P4")
# US-17 criterion 1, in the order the story lists them.
CATEGORIES = (
    "UI",
    "Authentication",
    "Performance",
    "Database",
    "API",
    "Functional",
    "Security",
    "Compatibility",
)
# DR-04.
REPRODUCIBILITY = ("Always", "Sometimes", "Rarely", "Unable to reproduce", "Unknown")

TriageField = Literal["severity", "priority", "category", "reproducibility"]
TRIAGE_FIELDS: tuple[TriageField, ...] = ("severity", "priority", "category", "reproducibility")
OPTIONS: dict[str, tuple[str, ...]] = {
    "severity": SEVERITIES,
    "priority": PRIORITIES,
    "category": CATEGORIES,
    "reproducibility": REPRODUCIBILITY,
}


class Suggestion(BaseModel):
    value: str
    reason: str


class TriageSuggestions(BaseModel):
    severity: Suggestion
    priority: Suggestion
    category: Suggestion
    reproducibility: Suggestion


def _compile(*phrases: str) -> list[re.Pattern[str]]:
    return [re.compile(rf"\b{phrase}\b", re.IGNORECASE) for phrase in phrases]


# --- Severity (DR-03) --------------------------------------------------------

_CRITICAL = _compile(
    r"data loss",
    r"lost (?:all |my |the |our )?(?:data|work|files?|records?|changes)",
    r"(?:deleted|wiped|erased) (?:all|every|my|our)",
    r"corrupt(?:ed|s|ion)?",
    r"security (?:hole|issue|breach|flaw|vulnerability|problem)",
    r"breach(?:ed)?",
    r"vulnerab\w*",
    r"(?:exposes?|exposed|leaks?|leaked|leaking) (?:\w+ )?(?:passwords?|tokens?|keys?|"
    r"credentials|personal data|user data|data)",
    r"sql injection",
    r"xss",
    r"cross[- ]site scripting",
    r"unauthori[sz]ed access",
    r"privilege escalation",
    r"(?:anyone|any user|other users?) can (?:see|access|view|read|edit)",
)

_HIGH = _compile(
    r"crash(?:es|ed|ing)?",
    r"freez(?:e|es|ing)",
    r"froze(?:n)?",
    r"hangs?",
    r"hanging",
    r"(?:not|stops?|stopped) responding",
    r"unresponsive",
    r"(?:cannot|can ?not|can't|unable to|could ?not|couldn't) (?:log ?in|sign ?in|login|access|"
    r"save|open|use|submit|load|upload|download|complete|check ?out|pay)",
    r"(?:does ?n[o']t|did ?n[o']t|do ?n[o']t) work",
    r"not working",
    r"stopped working",
    r"broken",
    r"blocked",
    r"blocking",
    r"blocker",
    r"(?:does|did) nothing",
    r"nothing happens",
    r"(?:does|did) not respond",
    r"fails?",
    r"failed",
    r"failing",
    r"failure",
    r"(?:error|status) 5\d\d",
    r"5\d\d (?:internal )?(?:server )?error",
    r"internal server error",
    r"exceptions?",
    r"traceback",
    r"uncaught",
    r"fatal",
    r"(?:application|app|page|browser|tab|window) (?:closes|closed|quits|shuts down)",
)

_LOW = _compile(
    r"typos?",
    r"spelling",
    r"misspel\w*",
    r"cosmetic",
    r"misaligned",
    r"alignment",
    r"not aligned",
    r"colou?rs?",
    r"fonts?",
    r"padding",
    r"spacing",
    r"margins?",
    r"overlap(?:s|ping)?",
    r"tooltips?",
    r"text (?:is )?(?:cut off|truncated)",
)

_WORKAROUND = _compile(
    r"work[- ]?around",
    r"(?:but|still) works (?:if|when|after)",
    r"works (?:if|when|after) (?:i|you|we)",
    r"(?:refresh(?:ing)?|reload(?:ing)?|restart(?:ing)?) (?:the page |the app )?"
    r"(?:fixes|solves|helps)",
)

# --- Priority (DR-02) --------------------------------------------------------

_SEVERITY_TO_PRIORITY = {"Critical": "P1", "High": "P2", "Medium": "P3", "Low": "P4"}

_URGENT = _compile(
    r"urgent(?:ly)?",
    r"asap",
    r"as soon as possible",
    r"immediately",
    r"production",
    r"in prod",
    r"live site",
    r"all (?:our |the )?(?:users|customers)",
    r"every (?:user|customer)",
    r"customers? (?:are|can't|cannot|complain\w*)",
    r"deadline",
    r"before (?:the )?(?:release|launch|demo)",
    r"blocker",
    r"(?:losing|lost) (?:money|revenue|sales|customers)",
)

# --- Category (US-17 criterion 1) -------------------------------------------

# Checked in this order when two categories match equally often, so the more
# specific one wins: a login form with a broken button is Authentication,
# not UI.
_CATEGORY_PRECEDENCE = (
    "Security",
    "Authentication",
    "Database",
    "API",
    "Performance",
    "Compatibility",
    "UI",
)

_CATEGORY_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "Security": _compile(
        r"security",
        r"permissions?",
        r"csrf",
        r"injection",
        r"vulnerab\w*",
        r"exposed",
        r"leak(?:s|ed|ing)?",
        r"unauthori[sz]ed",
        r"privacy",
        r"xss",
    ),
    "Authentication": _compile(
        r"log ?in",
        r"log ?out",
        r"sign[- ]?in",
        r"sign[- ]?out",
        r"sign[- ]?up",
        r"register(?:ing|ed)?",
        r"registration",
        r"passwords?",
        r"credentials",
        r"authenticat\w*",
        r"2fa",
        r"two[- ]factor",
        r"otp",
        r"session (?:expired|timeout|times out)",
        r"sso",
        r"oauth",
        r"account (?:is )?locked",
    ),
    "Database": _compile(
        r"database",
        r"db",
        r"sql",
        r"quer(?:y|ies)",
        r"migrations?",
        r"postgres\w*",
        r"mysql",
        r"sqlite",
        r"mongo\w*",
        r"(?:data|record|records|changes?|entry|entries) (?:is |are |was |were )?"
        r"(?:not saved|not persisted|lost|missing|duplicated)",
        r"duplicate (?:records|entries|rows)",
        r"deadlock",
    ),
    "API": _compile(
        r"api",
        r"endpoints?",
        r"(?:http|status|error) (?:code )?[45]\d\d",
        r"[45]\d\d (?:error|response|status)",
        r"requests? (?:fails?|failed|times? out|timed out)",
        r"json",
        r"graphql",
        r"webhooks?",
        r"cors",
    ),
    "Performance": _compile(
        r"slow(?:ly|er|ness)?",
        r"lag(?:s|gy|ging)?",
        r"latency",
        r"takes (?:a long time|forever|ages|\d+ (?:seconds|minutes))",
        r"loading (?:forever|takes)",
        r"time(?:s|d)? ?out",
        r"timeouts?",
        r"memory",
        r"cpu",
        r"performance",
        r"freez(?:e|es|ing)",
        r"froze",
        r"hangs?",
    ),
    "Compatibility": _compile(
        r"only (?:on|in|with) (?:safari|firefox|chrome|edge|opera|ios|android|mac(?:os)?|"
        r"windows|linux|mobile|ipad|iphone)",
        r"works (?:fine )?(?:on|in) \w+(?: \w+)? but not",
        r"compatib\w*",
        r"not supported (?:on|in|by)",
        r"older (?:version|browser)s?",
        r"internet explorer",
        r"ie ?11",
        r"(?:different|other) browsers?",
        r"cross[- ]browser",
    ),
    "UI": _compile(
        r"buttons?",
        r"layout",
        r"render(?:s|ed|ing)?",
        r"css",
        r"fonts?",
        r"colou?rs?",
        r"align\w*",
        r"modal",
        r"dialog",
        r"dropdown",
        r"menu",
        r"icons?",
        r"scroll(?:s|ing|bar)?",
        r"styl(?:e|es|ing)",
        r"tooltips?",
        r"dark mode",
        r"screen",
        r"overlap\w*",
        r"typos?",
        r"spelling",
        r"ui",
        r"checkbox(?:es)?",
    ),
}

# --- Reproducibility (DR-04, US-17 criteria 2 and 3) -------------------------

_UNABLE_TO_REPRODUCE = _compile(
    r"(?:can ?not|can't|cannot|could ?n[o']t|couldn't|unable to|not able to) reproduce",
    r"not reproducible",
    r"(?:cannot|can't|couldn't) (?:make|get) it (?:to )?happen again",
)
# Checked before Always, so "not always" reads as Sometimes rather than as
# the word "always".
_SOMETIMES = _compile(
    r"sometimes",
    r"intermittent(?:ly)?",
    r"occasionally",
    r"randomly",
    r"at random",
    r"now and (?:then|again)",
    r"not (?:always|every time)",
    r"some of the time",
    r"once in a while",
    r"hit or miss",
    r"flaky",
)
_RARELY = _compile(
    r"rarely",
    r"seldom",
    r"(?:happened|happens|occurred) (?:only )?once",
    r"only once",
    r"hardly ever",
)
_ALWAYS = _compile(
    r"always",
    r"every ?time",
    r"each time",
    r"consistently",
    r"every single time",
    r"reproducible",
    r"(?:both|all) times",
    r"(?:each|every) attempt",
    r"whenever",
    r"reliably",
    r"without fail",
)


def _first_match(text: str, patterns: list[re.Pattern[str]]) -> str | None:
    """Returns the matched words of the first pattern, in list order, that
    appears anywhere in the text. Earlier patterns are the more specific
    ones, so their wording is what the reason quotes."""
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(0).lower()
    return None


def _all_matches(text: str, patterns: list[re.Pattern[str]]) -> list[str]:
    return [m.group(0).lower() for p in patterns if (m := p.search(text))]


def suggest_severity(text: str) -> Suggestion:
    """US-15. Critical for data loss, corruption or a security breach;
    High for a crash, freeze or a major function that does not work, unless
    a workaround is mentioned, which makes it Medium (DR-03); Low for
    cosmetic wording; Medium otherwise."""
    if word := _first_match(text, _CRITICAL):
        return Suggestion(value="Critical", reason=f'Mentions "{word}", so Critical')
    if word := _first_match(text, _HIGH):
        if workaround := _first_match(text, _WORKAROUND):
            return Suggestion(
                value="Medium",
                reason=f'Mentions "{word}" but also "{workaround}", so Medium',
            )
        return Suggestion(value="High", reason=f'Mentions "{word}", so High')
    if word := _first_match(text, _LOW):
        return Suggestion(value="Low", reason=f'Mentions "{word}", so Low')
    return Suggestion(
        value="Medium",
        reason="No crash, data loss, security or cosmetic wording found, so Medium",
    )


def suggest_priority(text: str, severity: str) -> Suggestion:
    """US-16. Starts from the severity (Critical P1 through Low P4) and
    moves up one step when the report mentions urgency, such as production
    or every user being affected. Always a separate value from severity
    (DR-02), for the project manager to decide."""
    base = _SEVERITY_TO_PRIORITY[severity]
    if word := _first_match(text, _URGENT):
        raised = PRIORITIES[max(PRIORITIES.index(base) - 1, 0)]
        return Suggestion(
            value=raised, reason=f'Severity {severity} and mentions "{word}", so {raised}'
        )
    return Suggestion(value=base, reason=f"Follows severity {severity}, so {base}")


def suggest_category(text: str) -> Suggestion:
    """US-17 criterion 1. The category whose words appear most often wins,
    ties going to the more specific category; with no signal at all, the
    general Functional category."""
    matches = {
        category: _all_matches(text, patterns) for category, patterns in _CATEGORY_PATTERNS.items()
    }
    best = max(
        _CATEGORY_PRECEDENCE,
        key=lambda category: (len(matches[category]), -_CATEGORY_PRECEDENCE.index(category)),
    )
    words = list(dict.fromkeys(matches[best]))
    if not words:
        return Suggestion(
            value="Functional", reason="No category-specific wording found, so Functional"
        )
    quoted = " and ".join(f'"{word}"' for word in words[:2])
    return Suggestion(value=best, reason=f"Mentions {quoted}, so {best}")


def suggest_reproducibility(text: str) -> Suggestion:
    """US-17 criteria 2 and 3: "sometimes" gives Sometimes, and with no
    signal in the text the value is Unknown."""
    for value, patterns in (
        ("Unable to reproduce", _UNABLE_TO_REPRODUCE),
        ("Sometimes", _SOMETIMES),
        ("Rarely", _RARELY),
        ("Always", _ALWAYS),
    ):
        if word := _first_match(text, patterns):
            return Suggestion(value=value, reason=f'Mentions "{word}", so {value}')
    return Suggestion(value="Unknown", reason="No wording about how often it happens, so Unknown")


def triage_text(original_text: str, logs: str | None, extraction: ExtractionResult) -> str:
    """The text the rules read: the report as submitted, its logs, and every
    extracted value that is Explicit. Inferred and Unverified values are
    left out, since a suggestion should rest on what the reporter actually
    said, not on a paraphrase the verification layer could not confirm."""
    parts = [original_text]
    if logs:
        parts.append(logs)
    scalars = (
        extraction.title,
        extraction.summary,
        extraction.expected_behaviour,
        extraction.actual_behaviour,
        extraction.frequency,
    )
    for field in (*scalars, *extraction.steps, *extraction.error_messages):
        if field.label == Label.EXPLICIT and field.value:
            parts.append(field.value)
    for detail in extraction.environment:
        if detail.label == Label.EXPLICIT:
            parts.append(detail.value)
    return "\n".join(parts)


def suggest_triage(
    original_text: str, logs: str | None, extraction: ExtractionResult
) -> TriageSuggestions:
    """All four suggestions for one report."""
    text = triage_text(original_text, logs, extraction)
    severity = suggest_severity(text)
    return TriageSuggestions(
        severity=severity,
        priority=suggest_priority(text, severity.value),
        category=suggest_category(text),
        reproducibility=suggest_reproducibility(text),
    )
