"""SQLAlchemy model for a user's GitHub connection (`docs/design.md` section
6.4, US-26): the encrypted token and the chosen repository.

The token is stored only as ciphertext from `app.security.encrypt_secret`
and is never returned by any endpoint (US-26 criterion 3).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.core import User


class GitHubConnection(Base):
    """One per user."""

    __tablename__ = "github_connections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    encrypted_token: Mapped[str] = mapped_column(Text, nullable=False)
    # The GitHub account the token belongs to, shown so the person can tell
    # which account is connected without the token ever being shown.
    login: Mapped[str] = mapped_column(String(100), nullable=False)
    # owner/name. Null until the person picks one.
    repository: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="github_connection")
