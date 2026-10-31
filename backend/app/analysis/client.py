"""The Gemini extraction call (design.md section 6.5 steps 3 and 4; FR-28,
NFR-18, NFR-19).

This is the one module under `app.analysis` that talks to a model; every
other module here is deterministic Python. `extract` validates the
response against `RawExtractionResult`, retries once with the validation
error on failure, and falls back to an empty analysis (every field
Missing) rather than raising, so a model outage, a timeout or a malformed
response never blocks report submission (NFR-18). Nothing here decides a
label; the raw result still has to pass through `verification.py`.

The default model call is real Gemini, but `extract` takes a `model_call`
override so this module stays testable without a network call, the same
testability the rest of `app.analysis` has (see
`backend/tests/analysis/test_client.py`).
"""

from collections.abc import Callable
from pathlib import Path

from google import genai
from google.genai import types

from app.analysis.schema import RawExtractionResult
from app.config import Settings, get_settings

# NFR-19 says "about 8 seconds", but the google-genai SDK rejects an
# http_options timeout below 10 seconds outright ("Manually set deadline Ns
# is too short. Minimum allowed deadline is 10s"), confirmed against the
# real API. 10 is the floor the SDK allows, not a deliberate reinterpretation
# of the requirement; see docs/status.md for this as a recorded drift point,
# to flag back against NFR-19's wording.
TIMEOUT_SECONDS = 10

# Lives under app/analysis/, not docs/, since it is read by this module at
# runtime, not written material (see root CLAUDE.md's commit plan
# conventions: nothing under docs/ is ever committed).
_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "extraction.v1.md"
_PROMPT_MARKER = "## System prompt text"

# (system_prompt, report_text) -> the model's raw response text.
ModelCall = Callable[[str, str], str]


def load_system_prompt() -> str:
    """Reads the literal prompt text out of the fenced code block in
    `app/analysis/prompts/extraction.v1.md`, so the prompt has exactly one
    home and application code never holds its own copy that could drift
    from the versioned file (ADR-019)."""
    text = _PROMPT_PATH.read_text(encoding="utf-8")
    if _PROMPT_MARKER not in text:
        raise ValueError(f"{_PROMPT_PATH} has no '{_PROMPT_MARKER}' section")
    after_marker = text[text.index(_PROMPT_MARKER) :]
    fence_start = after_marker.index("```") + 3
    fence_end = after_marker.index("```", fence_start)
    return after_marker[fence_start:fence_end].strip()


def _default_model_call(settings: Settings) -> ModelCall:
    client = genai.Client(api_key=settings.gemini_api_key)

    def call(system_prompt: str, report_text: str) -> str:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=report_text,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=RawExtractionResult,
                http_options=types.HttpOptions(timeout=TIMEOUT_SECONDS * 1000),
            ),
        )
        return response.text

    return call


def extract(
    report_text: str,
    *,
    model_call: ModelCall | None = None,
    settings: Settings | None = None,
) -> RawExtractionResult:
    """Calls the model once, validates the response, and on any failure
    (malformed JSON, a schema mismatch, a timeout, the model being
    unreachable) retries exactly once with the validation error appended
    to the prompt. If the retry also fails, returns an empty
    `RawExtractionResult` (every field Missing) rather than raising
    (FR-28). The caller still has to run the result through
    `verification.py`; nothing returned from here is trusted yet."""
    settings = settings or get_settings()
    call = model_call or _default_model_call(settings)
    system_prompt = load_system_prompt()

    result = _attempt(call, system_prompt, report_text)
    if result is not None:
        return result

    retry_prompt = (
        f"{system_prompt}\n\nYour previous response did not match the required "
        "JSON schema. Return only valid JSON matching the schema, nothing else."
    )
    result = _attempt(call, retry_prompt, report_text)
    if result is not None:
        return result

    return RawExtractionResult()


def _attempt(call: ModelCall, system_prompt: str, report_text: str) -> RawExtractionResult | None:
    """One call-and-validate attempt. Returns None on any failure, never
    raises: a model outage must fall back, not crash the request
    (NFR-18)."""
    try:
        raw_text = call(system_prompt, report_text)
        return RawExtractionResult.model_validate_json(raw_text)
    except Exception:
        return None
