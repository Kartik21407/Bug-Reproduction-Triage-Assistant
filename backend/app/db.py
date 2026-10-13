"""SQLAlchemy engine, session factory and declarative Base. Owns the
per-request session lifecycle."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Declarative base for every SQLAlchemy model in app/models/."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding one session per request, always closed
    afterwards. Tests override this to point at a throwaway database."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
