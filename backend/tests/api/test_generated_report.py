"""Tests for GET /api/reports/{id}/report (app/api/generated_report.py):
the template assembled from stored analysis, triage and candidates
(US-23, FR-19). analyze always uses a fake extract; no real model call."""

import time

import app.api.analysis as analysis_module
from app.analysis.schema import RawExtractionResult, RawModelField
from app.corpus.importer import import_rows
from tests.conftest import TestingSessionLocal, create_report, register_and_login

REPORT_TEXT = "Login crashes sometimes when I enter a wrong password and click login."


def _field(value: str, quote: str) -> RawModelField:
    return RawModelField(value=value, source_quote=quote, confidence=0.9, reason="Stated")


def _sections(response) -> dict[str, dict]:
    return {section["heading"]: section for section in response.json()["sections"]}


def test_the_report_is_assembled_from_analysis_triage_and_duplicates(client, monkeypatch):
    """US-23 criteria 1 and 3 end to end."""
    monkeypatch.setattr(
        analysis_module,
        "extract",
        lambda text: RawExtractionResult(
            actual_behaviour=_field("the login page crashes", "Login crashes"),
            expected_behaviour=_field("an error message", "wrong password"),
        ),
    )
    with TestingSessionLocal() as db:
        import_rows(
            db,
            [
                {
                    "id": "acme/app#7",
                    "title": "Login crashes sometimes on a wrong password",
                    "body": REPORT_TEXT,
                    "url": "https://github.com/acme/app/issues/7",
                }
            ],
        )
    register_and_login(client)
    report_id = create_report(client, REPORT_TEXT).json()["id"]
    client.post(f"/api/reports/{report_id}/analyze")
    client.post(f"/api/reports/{report_id}/duplicates")

    response = client.get(f"/api/reports/{report_id}/report")

    assert response.status_code == 200
    sections = _sections(response)
    assert list(sections)[0] == "Title"
    assert list(sections)[-1] == "Additional Information"
    assert sections["Actual"]["lines"][0]["text"] == "the login page crashes"
    assert sections["Severity"]["lines"][0]["text"] == "High"
    assert sections["Category"]["lines"][0]["text"] == "Authentication"
    assert sections["Reproducibility"]["lines"][0]["text"] == "Sometimes"
    duplicate = sections["Possible Duplicates"]["lines"][0]
    assert duplicate["url"] == "https://github.com/acme/app/issues/7"


def test_what_is_missing_reads_not_provided(client):
    """US-23 criterion 2."""
    register_and_login(client)
    report_id = create_report(client, REPORT_TEXT).json()["id"]

    sections = _sections(client.get(f"/api/reports/{report_id}/report"))

    for heading in ("Title", "Summary", "Steps to Reproduce", "Environment", "Possible Duplicates"):
        assert sections[heading]["lines"][0]["text"] == "Not provided"
        assert sections[heading]["provided"] is False


def test_assembling_the_report_is_fast(client):
    """NFR-19: triage and report assembly together complete in under 1
    second. No search and no model call happen here."""
    register_and_login(client)
    report_id = create_report(client, REPORT_TEXT).json()["id"]

    started = time.perf_counter()
    response = client.get(f"/api/reports/{report_id}/report")
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    assert elapsed < 1.0


def test_another_users_report_returns_404(client):
    """NFR-15."""
    register_and_login(client, "owner@example.com")
    report_id = create_report(client, REPORT_TEXT).json()["id"]
    client.post("/api/auth/logout")
    register_and_login(client, "other@example.com")

    assert client.get(f"/api/reports/{report_id}/report").status_code == 404


def test_not_signed_in_returns_401(client):
    response = client.get("/api/reports/00000000-0000-0000-0000-000000000000/report")

    assert response.status_code == 401
