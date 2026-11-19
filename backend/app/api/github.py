"""Connecting a GitHub token and choosing a repository (US-26, FR-22), and
previewing then filing a report as an issue (US-27, FR-23)."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.api.duplicates import read_candidates
from app.api.generated_report import assemble, warnings
from app.api.reports import get_owned_report_or_404
from app.corpus.search import LIKELY_DUPLICATE
from app.deps import CurrentUser, DbSession
from app.github import client
from app.models.core import BugReport, User
from app.models.github import GitHubConnection
from app.report import store
from app.report.markdown import render_markdown
from app.schemas.github import (
    GitHubConnectionRead,
    GitHubTokenRequest,
    IssueCreated,
    IssuePreview,
    IssueRequest,
    LikelyDuplicate,
    RepositoryChoice,
    RepositoryRead,
)
from app.security import (
    SecretStoreUnavailableError,
    SecretUnreadableError,
    decrypt_secret,
    encrypt_secret,
)

router = APIRouter(tags=["github"])

# DR-08: labels are optional. "bug" exists in every new GitHub repository.
ISSUE_LABELS = ["bug"]
_MAX_TITLE_LENGTH = 200


def _unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="GitHub integration is not set up on this server.",
    )


def _github_failure(error: client.GitHubError) -> HTTPException:
    """A GitHub refusal, passed on in words the person can act on. Rate
    limits are 503, since waiting fixes them; everything else is 502."""
    code = status.HTTP_503_SERVICE_UNAVAILABLE if error.status in (0, 429) else 502
    if error.status == 403 and "rate limit" in error.message:
        code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HTTPException(status_code=code, detail=error.message)


def _connection_read(connection: GitHubConnection | None) -> GitHubConnectionRead:
    if connection is None:
        return GitHubConnectionRead(connected=False)
    return GitHubConnectionRead(
        connected=True, login=connection.login, repository=connection.repository
    )


def _token(connection: GitHubConnection | None) -> str:
    if connection is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Connect GitHub first")
    try:
        return decrypt_secret(connection.encrypted_token)
    except SecretStoreUnavailableError as error:
        raise _unavailable() from error
    except SecretUnreadableError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The saved GitHub token can no longer be read. Connect it again.",
        ) from error


@router.get("/github/connection", response_model=GitHubConnectionRead)
def read_connection(current_user: CurrentUser) -> GitHubConnectionRead:
    """Whether a token is connected, the GitHub account it belongs to, and
    the chosen repository. Never the token (US-26 criterion 3)."""
    return _connection_read(current_user.github_connection)


@router.put("/github/connection", response_model=GitHubConnectionRead)
def connect(
    body: GitHubTokenRequest, current_user: CurrentUser, db: DbSession
) -> GitHubConnectionRead:
    """Checks the token with GitHub and stores it encrypted (US-26 criteria
    1 and 3). A token GitHub does not accept is a 400 with a clear message,
    and nothing is stored (criterion 2). Connecting a different account
    clears the chosen repository."""
    token = body.token.strip()
    try:
        login = client.authenticated_login(token)
    except client.GitHubAuthError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=error.message
        ) from error
    except client.GitHubError as error:
        raise _github_failure(error) from error
    try:
        encrypted = encrypt_secret(token)
    except SecretStoreUnavailableError as error:
        raise _unavailable() from error

    connection = current_user.github_connection
    if connection is None:
        connection = GitHubConnection(encrypted_token=encrypted, login=login)
        current_user.github_connection = connection
    else:
        if connection.login != login:
            connection.repository = None
        connection.encrypted_token = encrypted
        connection.login = login
    db.commit()
    return _connection_read(connection)


@router.delete("/github/connection", status_code=status.HTTP_204_NO_CONTENT)
def disconnect(current_user: CurrentUser, db: DbSession) -> Response:
    """Deletes the stored token. Issues already filed are unaffected."""
    if current_user.github_connection is not None:
        current_user.github_connection = None
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/github/repositories", response_model=list[RepositoryRead])
def list_repositories(current_user: CurrentUser) -> list[RepositoryRead]:
    """Only repositories the token can file issues in (US-26 criterion 4)."""
    token = _token(current_user.github_connection)
    try:
        repositories = client.issue_repositories(token)
    except client.GitHubError as error:
        raise _github_failure(error) from error
    return [RepositoryRead(full_name=r.full_name, private=r.private) for r in repositories]


@router.put("/github/connection/repository", response_model=GitHubConnectionRead)
def choose_repository(
    body: RepositoryChoice, current_user: CurrentUser, db: DbSession
) -> GitHubConnectionRead:
    """Chooses where issues are filed. Only a repository the token can file
    issues in is accepted, checked with GitHub again rather than trusted
    from the request."""
    connection = current_user.github_connection
    token = _token(connection)
    try:
        allowed = {r.full_name for r in client.issue_repositories(token)}
    except client.GitHubError as error:
        raise _github_failure(error) from error
    if body.repository not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This token cannot file issues in that repository.",
        )
    connection.repository = body.repository
    db.commit()
    return _connection_read(connection)


def _likely_duplicates(db: Session, report: BugReport) -> list[LikelyDuplicate]:
    """Likely duplicates the person has not ruled out (US-27 criterion 3)."""
    return [
        LikelyDuplicate(title=c.title, url=c.url, score=c.score)
        for c in read_candidates(db, report).candidates
        if c.label == LIKELY_DUPLICATE and c.decision != "not_duplicate"
    ]


def _issue_title(report: BugReport) -> str:
    title = store.read_extraction(report).title.value or report.original_text.strip()
    title = " ".join(title.split())
    return title if len(title) <= _MAX_TITLE_LENGTH else title[: _MAX_TITLE_LENGTH - 3] + "..."


def _preview(db: Session, report: BugReport, user: User) -> IssuePreview:
    connection = user.github_connection
    return IssuePreview(
        repository=connection.repository if connection else None,
        title=_issue_title(report),
        body=render_markdown(assemble(db, report), include_title=False),
        labels=list(ISSUE_LABELS),
        likely_duplicates=_likely_duplicates(db, report),
        warnings=warnings(report),
        issue_url=report.github_issue_url,
    )


@router.get("/reports/{report_id}/github/preview", response_model=IssuePreview)
def preview_issue(report_id: UUID, current_user: CurrentUser, db: DbSession) -> IssuePreview:
    """The exact title, body and labels Confirm would send (US-27 criterion
    1). Makes no GitHub call at all (criterion 2). 404 rules match every
    other report endpoint (NFR-15)."""
    report = get_owned_report_or_404(db, current_user, report_id)
    return _preview(db, report, current_user)


@router.post("/reports/{report_id}/github/issue", response_model=IssueCreated)
def create_issue(
    report_id: UUID, body: IssueRequest, current_user: CurrentUser, db: DbSession
) -> IssueCreated:
    """Files the report as an issue, only on the person's explicit Confirm
    (US-27). A report already filed returns its existing issue and files
    nothing (criterion 4). Likely duplicates must be acknowledged first
    (criterion 3). The report is claimed with a conditional update before
    GitHub is called, so two Confirms at once cannot both file. On success
    the issue URL is stored and the report is Submitted (criterion 5); on
    failure the claim is released, nothing else changes, and GitHub's
    reason is returned (criterion 6)."""
    report = get_owned_report_or_404(db, current_user, report_id)
    if report.github_issue_url:
        return IssueCreated(
            issue_url=report.github_issue_url,
            issue_number=report.github_issue_number,
            created=False,
        )
    if report.state == "Draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Analyse the report first")
    connection = current_user.github_connection
    if connection is None or connection.repository is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Connect GitHub and choose a repository first",
        )
    if _likely_duplicates(db, report) and not body.acknowledge_likely_duplicates:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A likely duplicate exists. Acknowledge it before filing.",
        )
    token = _token(connection)
    preview = _preview(db, report, current_user)

    claimed = db.execute(
        update(BugReport)
        .where(
            BugReport.id == report.id,
            BugReport.github_submitting.is_(False),
            BugReport.github_issue_url.is_(None),
        )
        .values(github_submitting=True)
    ).rowcount
    db.commit()
    db.refresh(report)
    if not claimed:
        if report.github_issue_url:
            return IssueCreated(
                issue_url=report.github_issue_url,
                issue_number=report.github_issue_number,
                created=False,
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This issue is already being filed"
        )

    try:
        issue = client.create_issue(
            token, connection.repository, preview.title, preview.body, preview.labels
        )
    except client.GitHubError as error:
        report.github_submitting = False
        db.commit()
        raise _github_failure(error) from error

    report.github_issue_url = issue.url
    report.github_issue_number = issue.number
    report.github_submitting = False
    report.state = "Submitted"
    db.commit()
    return IssueCreated(issue_url=issue.url, issue_number=issue.number, created=True)
