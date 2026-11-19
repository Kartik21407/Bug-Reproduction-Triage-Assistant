"""Tests for keeping corrections through re-analysis (ADR-011), editing and
resetting the generated report (US-24), Markdown export (US-25, US-14
criterion 6) and the Reviewed and Exported states (DR-10). analyze always
uses a fake extract; no real model call."""

import app.api.analysis as analysis_module
from app.analysis.schema import (
    RawEnvironmentDetail,
    RawExtractionResult,
    RawFollowUpQuestion,
    RawModelField,
)
from tests.conftest import create_report, register_and_login

REPORT_TEXT = "Login crashes when I enter a wrong password and click submit on Chrome."


def _field(value: str, quote: str) -> RawModelField:
    return RawModelField(value=value, source_quote=quote, confidence=0.9, reason="Stated")


def _fake_extract(title: str = "Login crash on a wrong password"):
    raw = RawExtractionResult(
        title=_field(title, "Login crashes"),
        actual_behaviour=_field("The login page crashes", "Login crashes"),
        steps=[_field("Enter a wrong password", "wrong password")],
        environment=[RawEnvironmentDetail(name="browser", value="Chrome", source_quote="Chrome")],
        proposed_questions=[
            RawFollowUpQuestion(field="frequency", question="How often?", reason="Not stated")
        ],
    )
    return lambda text: raw


def _analysed(client, monkeypatch, **kwargs) -> str:
    register_and_login(client)
    report_id = create_report(client, REPORT_TEXT).json()["id"]
    monkeypatch.setattr(analysis_module, "extract", _fake_extract(**kwargs))
    client.post(f"/api/reports/{report_id}/analyze")
    return report_id


def _sections(body) -> dict[str, dict]:
    return {section["key"]: section for section in body["sections"]}


class TestCorrectionsSurviveReanalysis:
    """ADR-011, as the team decided: keep the corrections."""

    def test_an_answer_survives_reanalysis(self, client, monkeypatch):
        report_id = _analysed(client, monkeypatch)
        questions = client.get(f"/api/reports/{report_id}/analysis").json()["questions"]
        frequency = next(q for q in questions if q["field"] == "frequency")
        client.post(
            f"/api/reports/{report_id}/questions/{frequency['id']}/answer",
            json={"answer": "Every time"},
        )

        client.post(f"/api/reports/{report_id}/analyze")

        analysis = client.get(f"/api/reports/{report_id}/analysis").json()
        assert analysis["extraction"]["frequency"]["value"] == "Every time"
        frequency_questions = [q for q in analysis["questions"] if q["field"] == "frequency"]
        assert [q["answer"] for q in frequency_questions] == ["Every time"]
        assert "frequency" in analysis["corrected_fields"]

    def test_an_environment_correction_and_a_removal_survive_reanalysis(self, client, monkeypatch):
        report_id = _analysed(client, monkeypatch)
        client.post(
            f"/api/reports/{report_id}/environment",
            json={"corrections": [{"name": "os", "value": "Windows 11"}], "removals": ["browser"]},
        )

        client.post(f"/api/reports/{report_id}/analyze")

        environment = client.get(f"/api/reports/{report_id}/analysis").json()["extraction"][
            "environment"
        ]
        assert [(d["name"], d["value"]) for d in environment] == [("os", "Windows 11")]

    def test_an_edited_title_survives_reanalysis_while_untouched_fields_refresh(
        self, client, monkeypatch
    ):
        report_id = _analysed(client, monkeypatch)
        client.patch(f"/api/reports/{report_id}/report", json={"field": "title", "text": "Mine"})
        monkeypatch.setattr(analysis_module, "extract", _fake_extract(title="A newer suggestion"))

        result = client.post(f"/api/reports/{report_id}/analyze").json()

        assert result["extraction"]["title"]["value"] == "Mine"
        assert client.get(f"/api/reports/{report_id}").json()["title"] == "Mine"


class TestEditing:
    def test_every_field_of_the_report_is_editable(self, client, monkeypatch):
        """US-24 criterion 1: all fields are editable. Severity, priority,
        category and reproducibility through the triage endpoint, the rest
        here; Possible Duplicates through each candidate's decision."""
        report_id = _analysed(client, monkeypatch)
        edits = [
            {"field": "title", "text": "Edited title"},
            {"field": "summary", "text": "Edited summary"},
            {"field": "expected_behaviour", "text": "An error message"},
            {"field": "actual_behaviour", "text": "It closes"},
            {"field": "frequency", "text": "Every time"},
            {"field": "steps", "items": ["Open the page", "Click Login"]},
            {"field": "error_messages", "items": ["TypeError: x is undefined"]},
            {"field": "environment", "environment": [{"name": "Browser", "value": "Firefox"}]},
            {"field": "additional_information", "text": "Started after the update"},
        ]

        for edit in edits:
            assert client.patch(f"/api/reports/{report_id}/report", json=edit).status_code == 200
        client.patch(f"/api/reports/{report_id}/triage", json={"field": "severity", "value": "Low"})

        sections = _sections(client.get(f"/api/reports/{report_id}/report").json())
        assert sections["title"]["lines"][0]["text"] == "Edited title"
        assert sections["summary"]["lines"][0]["text"] == "Edited summary"
        assert [line["text"] for line in sections["steps"]["lines"]] == [
            "Open the page",
            "Click Login",
        ]
        assert sections["environment"]["lines"][0]["text"] == "browser: Firefox"
        assert sections["error_details"]["lines"][0]["text"] == "TypeError: x is undefined"
        assert [line["text"] for line in sections["additional"]["lines"]] == [
            "Frequency: Every time",
            "Started after the update",
        ]
        assert sections["severity"]["lines"][0]["text"] == "Low"
        editable = [s for s in sections.values() if s["key"] != "duplicates"]
        assert all(s["fields"] for s in editable)
        assert all(
            s["edited"]
            for s in editable
            if s["key"] not in ("priority", "category", "reproducibility")
        )

    def test_saving_persists_the_change(self, client, monkeypatch):
        """US-24 criterion 2."""
        report_id = _analysed(client, monkeypatch)

        client.patch(f"/api/reports/{report_id}/report", json={"field": "summary", "text": "Kept"})

        reread = client.get(f"/api/reports/{report_id}/report").json()
        assert _sections(reread)["summary"]["lines"][0]["text"] == "Kept"
        assert reread["values"]["summary"] == "Kept"

    def test_reset_to_suggested_restores_the_system_version(self, client, monkeypatch):
        """US-24 criterion 3."""
        report_id = _analysed(client, monkeypatch)
        client.patch(f"/api/reports/{report_id}/report", json={"field": "title", "text": "Mine"})
        client.patch(
            f"/api/reports/{report_id}/report", json={"field": "steps", "items": ["Only mine"]}
        )

        client.delete(f"/api/reports/{report_id}/report/fields/title")
        response = client.delete(f"/api/reports/{report_id}/report/fields/steps")

        sections = _sections(response.json())
        assert sections["title"]["lines"][0]["text"] == "Login crash on a wrong password"
        assert sections["title"]["edited"] is False
        assert sections["steps"]["lines"][0]["text"] == "Enter a wrong password"
        assert client.get(f"/api/reports/{report_id}").json()["title"] == (
            "Login crash on a wrong password"
        )

    def test_clearing_a_field_shows_not_provided(self, client, monkeypatch):
        report_id = _analysed(client, monkeypatch)

        response = client.patch(
            f"/api/reports/{report_id}/report", json={"field": "actual_behaviour", "text": ""}
        )

        assert _sections(response.json())["actual"]["lines"][0]["text"] == "Not provided"

    def test_an_edit_refreshes_triage(self, client, monkeypatch):
        """Triage reads Explicit values, and an edit is one."""
        report_id = _analysed(client, monkeypatch)

        client.patch(
            f"/api/reports/{report_id}/report",
            json={"field": "frequency", "text": "It happens sometimes"},
        )

        triage = client.get(f"/api/reports/{report_id}/triage").json()
        assert triage["reproducibility"]["value"] == "Sometimes"

    def test_the_wrong_shape_for_a_field_is_rejected(self, client, monkeypatch):
        report_id = _analysed(client, monkeypatch)

        for body in (
            {"field": "steps", "text": "one step"},
            {"field": "title", "items": ["a"]},
            {"field": "environment", "text": "Chrome"},
            {"field": "title", "text": "x" * 201},
            {"field": "severity", "text": "High"},
        ):
            response = client.patch(f"/api/reports/{report_id}/report", json=body)
            assert response.status_code == 422, body

    def test_another_users_report_cannot_be_edited(self, client, monkeypatch):
        """NFR-15."""
        report_id = _analysed(client, monkeypatch)
        client.post("/api/auth/logout")
        register_and_login(client, "other@example.com")

        edit = client.patch(
            f"/api/reports/{report_id}/report", json={"field": "title", "text": "x"}
        )
        reset = client.delete(f"/api/reports/{report_id}/report/fields/title")

        assert edit.status_code == 404
        assert reset.status_code == 404


class TestMarkdownExport:
    def test_the_report_is_returned_as_markdown(self, client, monkeypatch):
        """US-25: the Markdown that one click copies."""
        report_id = _analysed(client, monkeypatch)

        body = client.get(f"/api/reports/{report_id}/markdown").json()

        markdown = body["markdown"]
        assert markdown.startswith("## Title\n\nLogin crash on a wrong password")
        assert "## Steps to Reproduce\n\n1. Enter a wrong password" in markdown
        assert "## Error Details\n\n*Not provided*" in markdown

    def test_skipped_questions_give_a_warning_but_do_not_block_export(self, client, monkeypatch):
        """US-14 criterion 6: questions can be skipped; the report can still
        be exported with a warning."""
        report_id = _analysed(client, monkeypatch)

        body = client.get(f"/api/reports/{report_id}/markdown").json()
        exported = client.post(f"/api/reports/{report_id}/export")

        assert "2 follow-up questions were not answered" in body["warnings"]
        assert "Still missing: expected behaviour, frequency" in body["warnings"]
        assert exported.status_code == 200
        assert exported.json()["state"] == "Exported"

    def test_a_draft_report_cannot_be_exported_or_reviewed(self, client):
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]

        assert client.post(f"/api/reports/{report_id}/export").status_code == 409
        assert client.post(f"/api/reports/{report_id}/review").status_code == 409


class TestLifecycle:
    def test_marking_reviewed_then_exporting(self, client, monkeypatch):
        """DR-10: Analysed, then Reviewed, then Exported."""
        report_id = _analysed(client, monkeypatch)

        reviewed = client.post(f"/api/reports/{report_id}/review").json()
        exported = client.post(f"/api/reports/{report_id}/export").json()

        assert reviewed["state"] == "Reviewed"
        assert exported["state"] == "Exported"

    def test_the_state_never_moves_backward(self, client, monkeypatch):
        report_id = _analysed(client, monkeypatch)
        client.post(f"/api/reports/{report_id}/export")

        response = client.post(f"/api/reports/{report_id}/review")

        assert response.json()["state"] == "Exported"
