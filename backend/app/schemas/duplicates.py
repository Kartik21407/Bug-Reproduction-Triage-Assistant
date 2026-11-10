"""Response shapes for the duplicate candidate endpoints (`docs/design.md`
section 7.3, US-20)."""

from typing import Literal

from pydantic import BaseModel


class DuplicateCandidateRead(BaseModel):
    """One candidate. `url` is the issue's own address for a corpus issue,
    or the in-app path of the user's own earlier report. `label` is only
    ever "Likely duplicate" or "Possible duplicate" (US-20 criterion 3)."""

    id: str
    source: Literal["corpus", "report"]
    title: str
    url: str
    score: float
    label: str
    rank: int


class DuplicatesRead(BaseModel):
    """`searched` is false until a search has run for this report.
    `compared_count` is how many corpus issues and earlier reports of the
    user's a search compares against, so an empty result can be read
    correctly."""

    searched: bool
    compared_count: int
    candidates: list[DuplicateCandidateRead]
