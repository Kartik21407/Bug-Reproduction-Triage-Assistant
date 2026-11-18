"""Response shapes for the duplicate candidate endpoints (`docs/design.md`
section 7.3, US-20)."""

from typing import Literal

from pydantic import BaseModel

Decision = Literal["duplicate", "not_duplicate"]


class DuplicateCandidateRead(BaseModel):
    """One candidate. `id` is the issue's or earlier report's id;
    `candidate_id` is this candidate row's, the one a decision is posted
    against. `url` is the issue's own address for a corpus issue, or the
    in-app path of the user's own earlier report. `label` is only ever
    "Likely duplicate" or "Possible duplicate" (US-20 criterion 3);
    `decision` is a person's, never the system's (US-21, DR-05)."""

    id: str
    candidate_id: str
    source: Literal["corpus", "report"]
    title: str
    url: str
    score: float
    label: str
    rank: int
    decision: Decision | None = None


class DuplicateDecisionRequest(BaseModel):
    """A person's decision on one candidate (US-21 criterion 1). `null`
    takes a decision back."""

    decision: Decision | None


class DuplicatesRead(BaseModel):
    """`searched` is false until a search has run for this report.
    `compared_count` is how many corpus issues and earlier reports of the
    user's a search compares against, so an empty result can be read
    correctly."""

    searched: bool
    compared_count: int
    candidates: list[DuplicateCandidateRead]
