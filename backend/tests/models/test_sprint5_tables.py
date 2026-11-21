"""Tests for the Sprint 5 columns and tables (app/models/core.py,
app/models/settings.py): account flags, administrator settings and the
corpus import's progress."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.core import User
from app.models.settings import AppSetting, CorpusSyncState
from tests.conftest import TestingSessionLocal


def test_a_new_account_is_active_and_not_an_administrator():
    with TestingSessionLocal() as db:
        user = User(email="new@example.com", password_hash="x")
        db.add(user)
        db.commit()
        db.refresh(user)

        assert user.is_active is True
        assert user.is_admin is False


def test_a_setting_is_one_row_per_key():
    with TestingSessionLocal() as db:
        db.add(AppSetting(key="duplicate_likely_threshold", value="0.9"))
        db.commit()
        db.add(AppSetting(key="duplicate_likely_threshold", value="0.7"))

        with pytest.raises(IntegrityError):
            db.commit()


def test_an_unknown_sync_status_is_rejected_by_the_database():
    with TestingSessionLocal() as db:
        db.add(CorpusSyncState(repository="acme/app", status="sleeping"))

        with pytest.raises(IntegrityError):
            db.commit()


def test_one_sync_state_per_repository():
    with TestingSessionLocal() as db:
        db.add(CorpusSyncState(repository="acme/app", status="idle"))
        db.commit()
        db.add(CorpusSyncState(repository="acme/app", status="idle"))

        with pytest.raises(IntegrityError):
            db.commit()
