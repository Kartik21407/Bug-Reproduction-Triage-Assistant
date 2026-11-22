"""The two duplicate thresholds in force (US-20 criterion 2, US-31).

An administrator can change them while the server runs; the values are
stored in `app_settings`. Without a stored value, the environment's
default from `app/config.py` applies. A change affects searches run after
it; candidates already stored keep the label they were given.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.settings import AppSetting

LIKELY_KEY = "duplicate_likely_threshold"
POSSIBLE_KEY = "duplicate_possible_threshold"


class ThresholdError(ValueError):
    """A pair of thresholds that cannot be used, with a message for the
    person who entered them."""


@dataclass(frozen=True)
class Thresholds:
    likely: float
    possible: float


def defaults() -> Thresholds:
    settings = get_settings()
    return Thresholds(
        likely=settings.duplicate_likely_threshold,
        possible=settings.duplicate_possible_threshold,
    )


def current_thresholds(db: Session) -> Thresholds:
    """Stored values where an administrator set them, defaults otherwise."""
    base = defaults()
    likely = db.get(AppSetting, LIKELY_KEY)
    possible = db.get(AppSetting, POSSIBLE_KEY)
    return Thresholds(
        likely=float(likely.value) if likely else base.likely,
        possible=float(possible.value) if possible else base.possible,
    )


def validate(likely: float, possible: float) -> None:
    """US-31 criterion 1: two numbers between 0 and 1. The possible
    threshold must also be below the likely one, or no candidate could ever
    be labelled Possible."""
    for name, value in (("likely", likely), ("possible", possible)):
        if not 0 <= value <= 1:
            raise ThresholdError(f"The {name} threshold must be between 0 and 1.")
    if possible >= likely:
        raise ThresholdError("The possible threshold must be lower than the likely threshold.")


def set_thresholds(
    db: Session, likely: float, possible: float, user_id: uuid.UUID | None
) -> Thresholds:
    """Validates and stores both values together, so the pair is never
    half-changed. Commits."""
    validate(likely, possible)
    for key, value in ((LIKELY_KEY, likely), (POSSIBLE_KEY, possible)):
        row = db.get(AppSetting, key)
        if row is None:
            db.add(AppSetting(key=key, value=repr(value), updated_by_id=user_id))
        else:
            row.value = repr(value)
            row.updated_by_id = user_id
    db.commit()
    return Thresholds(likely=likely, possible=possible)


def reset_thresholds(db: Session) -> Thresholds:
    """Removes the stored values, so the environment's defaults apply again.
    Commits."""
    for key in (LIKELY_KEY, POSSIBLE_KEY):
        row = db.get(AppSetting, key)
        if row is not None:
            db.delete(row)
    db.commit()
    return defaults()
