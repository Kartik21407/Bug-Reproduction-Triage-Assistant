"""Shared pytest fixtures: a throwaway SQLite database, a FastAPI test client
wired to it, and helpers for registering and logging in users.

Tests run against SQLite rather than PostgreSQL so the suite needs no
external service. CI and production always run PostgreSQL. See ADR-013 in
docs/adr.md."""

import os
from collections.abc import Generator

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-not-used-anywhere-else")
os.environ.setdefault("SESSION_EXPIRE_MINUTES", "60")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db import Base, get_db
from app.main import app

get_settings.cache_clear()

# StaticPool keeps the single in-memory connection alive for the life of the
# engine, so every session in a test sees the same database.
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture(autouse=True)
def _fresh_database() -> Generator[None, None, None]:
    """Creates every table before a test and drops them afterwards, so each
    test starts from a clean database and none depends on another having
    run first."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _override_get_db() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """A test client wired to the throwaway database."""
    with TestClient(app) as test_client:
        yield test_client


VALID_PASSWORD = "correct-horse-battery-staple"


def register_user(
    client: TestClient, email: str = "tester@example.com", password: str = VALID_PASSWORD
):
    """Registers a user and returns the response."""
    return client.post("/api/auth/register", json={"email": email, "password": password})


def login_user(
    client: TestClient, email: str = "tester@example.com", password: str = VALID_PASSWORD
):
    """Logs in a user and returns the response. The session cookie is set on
    the client automatically by httpx's cookie jar."""
    return client.post("/api/auth/login", json={"email": email, "password": password})


def register_and_login(
    client: TestClient, email: str = "tester@example.com", password: str = VALID_PASSWORD
):
    """Registers and logs in a user in one step, leaving the client
    authenticated for subsequent requests."""
    register_user(client, email, password)
    return login_user(client, email, password)


# 27 characters, comfortably inside the 20 to 10,000 bound (US-04
# criterion 1), reused wherever a test needs valid report text but is not
# testing the boundary itself.
VALID_REPORT_TEXT = "App crashes when I click X."


def create_report(
    client: TestClient, original_text: str = VALID_REPORT_TEXT, logs: str | None = None
):
    """Creates a report as whichever user the client is currently logged in
    as, and returns the response."""
    body: dict[str, str] = {"original_text": original_text}
    if logs is not None:
        body["logs"] = logs
    return client.post("/api/reports", json=body)
