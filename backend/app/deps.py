"""FastAPI dependencies shared by the routers: database session and current
authenticated user."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models.core import User
from app.security import decode_session_token

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(request: Request, db: DbSession) -> User:
    """Returns the signed-in user for this request, read from the session
    cookie. Raises 401 when there is no cookie, the token is invalid or
    expired, or the user it names no longer exists. Never builds a user from
    an unverified token."""
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user_id = decode_session_token(token)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
