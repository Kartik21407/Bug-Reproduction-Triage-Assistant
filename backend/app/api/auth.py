"""Routes for registration, login, logout and the current user (US-01)."""

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.config import get_settings
from app.deps import CurrentUser, DbSession
from app.models.core import User
from app.schemas.core import UserCreate, UserLogin, UserRead
from app.security import create_session_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.session_expire_minutes * 60,
        path="/",
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(body: UserCreate, db: DbSession) -> User:
    """Creates an account. A registered email returns 409 "Account already
    exists" (US-01 criterion 2). The password is stored only as a salted
    argon2 hash (US-01 criterion 4)."""
    email = body.email.lower()

    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account already exists")

    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=UserRead)
def login(body: UserLogin, response: Response, db: DbSession) -> User:
    """Signs in and sets the session cookie. A wrong email and a wrong
    password return the same generic message, so neither field is revealed
    as the one that was wrong (US-01 criterion 3)."""
    email = body.email.lower()
    generic_error = "Invalid email or password"

    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=generic_error)

    token = create_session_token(user.id)
    _set_session_cookie(response, token)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, _current_user: CurrentUser) -> None:
    """Clears the session cookie, ending the session (US-01 criterion 5)."""
    settings = get_settings()
    response.delete_cookie(key=settings.session_cookie_name, path="/")


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: CurrentUser) -> User:
    """Returns the signed-in user."""
    return current_user
