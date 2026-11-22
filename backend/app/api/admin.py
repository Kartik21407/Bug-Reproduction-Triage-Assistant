"""Administrator endpoints: deactivating and reactivating accounts (US-03),
the duplicate thresholds (US-31), and the automatic corpus import (US-28).

Every route requires an administrator (`AdminUser`, a 403 otherwise). Who
is an administrator is decided only by the operator command
`python -m app.admin`, never through these routes.
"""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.corpus import sync, thresholds
from app.deps import AdminUser, DbSession
from app.models.core import BugReport, User
from app.models.settings import AppSetting
from app.schemas.admin import (
    AdminUserRead,
    CorpusSyncRead,
    CorpusSyncStateRead,
    CorpusSyncUpdate,
    ThresholdsRead,
    ThresholdsUpdate,
    UserActiveUpdate,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _user_read(db: Session, user: User) -> AdminUserRead:
    reports = db.execute(
        select(func.count()).select_from(BugReport).where(BugReport.user_id == user.id)
    ).scalar_one()
    return AdminUserRead(
        id=user.id,
        email=user.email,
        is_admin=user.is_admin,
        is_active=user.is_active,
        report_count=reports,
        created_at=user.created_at,
    )


@router.get("/users", response_model=list[AdminUserRead])
def list_users(_admin: AdminUser, db: DbSession) -> list[AdminUserRead]:
    """Every account, oldest first, with how many reports it owns. The
    reports themselves stay private to their owner (NFR-15)."""
    users = db.execute(select(User).order_by(User.created_at, User.email)).scalars()
    return [_user_read(db, user) for user in users]


@router.patch("/users/{user_id}", response_model=AdminUserRead)
def set_user_active(
    user_id: UUID, body: UserActiveUpdate, admin: AdminUser, db: DbSession
) -> AdminUserRead:
    """Deactivates or reactivates an account. A deactivated user cannot
    sign in, and any session they have ends at once (US-03 criterion 1);
    nothing they own is deleted or changed (criterion 2). An administrator
    cannot deactivate their own account, so the last one cannot lock
    everyone out."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == admin.id and not body.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot deactivate your own account.",
        )
    user.is_active = body.is_active
    db.commit()
    db.refresh(user)
    return _user_read(db, user)


def _thresholds_read(db: Session) -> ThresholdsRead:
    current = thresholds.current_thresholds(db)
    base = thresholds.defaults()
    customised = any(
        db.get(AppSetting, key) is not None
        for key in (thresholds.LIKELY_KEY, thresholds.POSSIBLE_KEY)
    )
    return ThresholdsRead(
        likely=current.likely,
        possible=current.possible,
        default_likely=base.likely,
        default_possible=base.possible,
        customised=customised,
    )


@router.get("/settings/duplicate-thresholds", response_model=ThresholdsRead)
def read_thresholds(_admin: AdminUser, db: DbSession) -> ThresholdsRead:
    return _thresholds_read(db)


@router.put("/settings/duplicate-thresholds", response_model=ThresholdsRead)
def update_thresholds(body: ThresholdsUpdate, admin: AdminUser, db: DbSession) -> ThresholdsRead:
    """Sets both thresholds (US-31 criterion 1): each between 0 and 1, the
    possible one below the likely one, or a 422 saying which rule failed.
    Searches run afterwards use the new values; no restart and no code
    change."""
    try:
        thresholds.set_thresholds(db, body.likely, body.possible, admin.id)
    except thresholds.ThresholdError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    return _thresholds_read(db)


@router.delete("/settings/duplicate-thresholds", response_model=ThresholdsRead)
def reset_thresholds(_admin: AdminUser, db: DbSession) -> ThresholdsRead:
    """Goes back to the environment's defaults."""
    thresholds.reset_thresholds(db)
    return _thresholds_read(db)


def _sync_read(db: Session) -> CorpusSyncRead:
    repository = sync.configured_repository(db)
    state = sync.read_state(db, repository) if repository else None
    return CorpusSyncRead(
        repository=repository,
        interval_minutes=get_settings().corpus_sync_interval_minutes,
        running=sync.is_running(),
        state=CorpusSyncStateRead.model_validate(state) if state else None,
    )


@router.get("/corpus-sync", response_model=CorpusSyncRead)
def read_corpus_sync(_admin: AdminUser, db: DbSession) -> CorpusSyncRead:
    return _sync_read(db)


@router.put("/corpus-sync", response_model=CorpusSyncRead)
def update_corpus_sync(body: CorpusSyncUpdate, admin: AdminUser, db: DbSession) -> CorpusSyncRead:
    """Chooses the repository whose open issues are imported automatically
    (US-28), or switches the automatic import off with an empty value."""
    try:
        sync.set_repository(db, body.repository, admin.id)
    except sync.RepositoryError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    return _sync_read(db)


def _run_in_background(session: Session, repository: str) -> None:
    try:
        sync.run_sync(session, repository, get_settings().corpus_sync_token or None)
    except sync.SyncBusyError:
        pass
    finally:
        session.close()


@router.post("/corpus-sync/run", status_code=status.HTTP_202_ACCEPTED)
def run_corpus_sync(_admin: AdminUser, db: DbSession, background: BackgroundTasks) -> Response:
    """Starts an import now, without waiting for the schedule. It runs after
    this response, in its own session; the admin page polls
    `GET /admin/corpus-sync` for progress."""
    repository = sync.configured_repository(db)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Choose a repository to import from first."
        )
    if sync.is_running():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="An import is already running."
        )
    background.add_task(_run_in_background, Session(bind=db.get_bind()), repository)
    return Response(status_code=status.HTTP_202_ACCEPTED)
