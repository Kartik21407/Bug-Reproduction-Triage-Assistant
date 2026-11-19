"""Request and response shapes for GitHub integration (`docs/design.md`
section 7.6, US-26, US-27). No response here has a field that could carry
the token (US-26 criterion 3); it is only ever accepted, never returned."""

from pydantic import BaseModel, Field


class GitHubTokenRequest(BaseModel):
    # GitHub tokens are well under this; the limit only stops abuse.
    token: str = Field(min_length=1, max_length=500)


class GitHubConnectionRead(BaseModel):
    connected: bool
    # The GitHub account the token belongs to.
    login: str | None = None
    # owner/name, once chosen.
    repository: str | None = None


class RepositoryRead(BaseModel):
    full_name: str
    private: bool


class RepositoryChoice(BaseModel):
    repository: str = Field(min_length=3, max_length=200)


class LikelyDuplicate(BaseModel):
    title: str
    url: str
    score: float


class IssuePreview(BaseModel):
    """Exactly what Confirm would send (US-27 criterion 1): the same title,
    body and labels are rebuilt and sent, nothing else. `warnings` repeats
    the export warnings (unanswered questions, missing fields).
    `likely_duplicates` must be acknowledged before filing (criterion 3)."""

    repository: str | None
    title: str
    body: str
    labels: list[str]
    likely_duplicates: list[LikelyDuplicate]
    warnings: list[str]
    issue_url: str | None


class IssueRequest(BaseModel):
    acknowledge_likely_duplicates: bool = False


class IssueCreated(BaseModel):
    """`created` is false when the report had already been filed; the
    existing issue is returned and no second one is made (criterion 4)."""

    issue_url: str
    issue_number: int | None
    created: bool
