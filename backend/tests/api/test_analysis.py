"""Tests for POST /api/reports/{id}/analyze: masking, extraction, question
filtering and persistence chained behind one endpoint (see
app/api/analysis.py).

Every test replaces app.api.analysis.extract with a fake, so the suite
never makes a real Gemini call, the same convention
backend/tests/analysis/test_client.py follows."""

from uuid import UUID

import app.api.analysis as analysis_module
from app.analysis.schema import RawEnvironmentDetail, RawExtractionResult, RawModelField
from app.models.analysis import EnvironmentDetail, ExtractedField
from app.models.analysis import FollowUpQuestion as FollowUpQuestionRow
from app.models.core import BugReport
from tests.conftest import TestingSessionLocal, create_report, register_and_login

REPORT_TEXT = "Login crashes when I enter jane.doe@example.com and click submit."


def _fake_extract_returning(raw: RawExtractionResult):
    def fake(report_text: str) -> RawExtractionResult:
        return raw

    return fake


class TestAnalyzeReport:
    def test_analyzing_a_report_returns_masked_items_extraction_and_questions(
        self, client, monkeypatch
    ):
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        monkeypatch.setattr(
            analysis_module,
            "extract",
            _fake_extract_returning(
                RawExtractionResult(
                    actual_behaviour=RawModelField(
                        value="the application crashes",
                        source_quote="crashes",
                        confidence=0.8,
                        reason="Stated directly",
                    )
                )
            ),
        )

        response = client.post(f"/api/reports/{report_id}/analyze")

        assert response.status_code == 200
        body = response.json()
        assert "masked_items" in body
        assert "extraction" in body
        assert "questions" in body
        assert body["extraction"]["actual_behaviour"]["label"] == "Explicit"
        assert body["steps_flagged_for_review"] is False

    def test_more_than_seven_steps_are_flagged_for_review_and_none_are_dropped(
        self, client, monkeypatch
    ):
        """US-09 criterion 5."""
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        monkeypatch.setattr(
            analysis_module,
            "extract",
            _fake_extract_returning(
                RawExtractionResult(
                    steps=[
                        RawModelField(
                            value=f"Step {i}", source_quote="x", confidence=0.9, reason="x"
                        )
                        for i in range(10)
                    ]
                )
            ),
        )

        response = client.post(f"/api/reports/{report_id}/analyze")

        body = response.json()
        assert body["steps_flagged_for_review"] is True
        assert len(body["extraction"]["steps"]) == 10

    def test_the_email_in_the_report_is_masked_before_extraction_sees_it(self, client, monkeypatch):
        """FR-29: only the masked copy is ever sent onward."""
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]

        seen_by_model: list[str] = []

        def fake_extract(report_text: str) -> RawExtractionResult:
            seen_by_model.append(report_text)
            return RawExtractionResult()

        monkeypatch.setattr(analysis_module, "extract", fake_extract)

        response = client.post(f"/api/reports/{report_id}/analyze")

        assert response.status_code == 200
        assert "jane.doe@example.com" not in seen_by_model[0]
        body = response.json()
        assert any(item["type"] == "email" for item in body["masked_items"])

    def test_the_logs_field_is_sent_to_the_model_too(self, client, monkeypatch):
        """US-11 criterion 2: stack-trace lines from the log field are
        extracted, not just the description."""
        register_and_login(client)
        report_id = create_report(
            client, REPORT_TEXT, logs="Traceback (most recent call last):\nKeyError: 'session'"
        ).json()["id"]

        seen_by_model: list[str] = []

        def fake_extract(report_text: str) -> RawExtractionResult:
            seen_by_model.append(report_text)
            return RawExtractionResult()

        monkeypatch.setattr(analysis_module, "extract", fake_extract)

        response = client.post(f"/api/reports/{report_id}/analyze")

        assert response.status_code == 200
        assert "KeyError: 'session'" in seen_by_model[0]

    def test_a_secret_in_the_logs_field_is_masked_too(self, client, monkeypatch):
        register_and_login(client)
        report_id = create_report(
            client, REPORT_TEXT, logs="auth failed for jane.doe@example.com"
        ).json()["id"]

        seen_by_model: list[str] = []

        def fake_extract(report_text: str) -> RawExtractionResult:
            seen_by_model.append(report_text)
            return RawExtractionResult()

        monkeypatch.setattr(analysis_module, "extract", fake_extract)

        response = client.post(f"/api/reports/{report_id}/analyze")

        assert response.status_code == 200
        assert "jane.doe@example.com" not in seen_by_model[0]
        assert any(item["type"] == "email" for item in response.json()["masked_items"])

    def test_missing_essential_fields_produce_fallback_questions(self, client, monkeypatch):
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        monkeypatch.setattr(
            analysis_module, "extract", _fake_extract_returning(RawExtractionResult())
        )

        response = client.post(f"/api/reports/{report_id}/analyze")

        assert response.status_code == 200
        questions = response.json()["questions"]
        fields = {q["field"] for q in questions}
        assert "expected_behaviour" in fields
        assert len(questions) <= 6

    def test_analyzing_an_unknown_report_id_returns_404(self, client):
        register_and_login(client)

        response = client.post("/api/reports/00000000-0000-0000-0000-000000000000/analyze")

        assert response.status_code == 404

    def test_analyzing_another_users_report_returns_404(self, client, monkeypatch):
        """NFR-15, matching every other report endpoint."""
        monkeypatch.setattr(
            analysis_module, "extract", _fake_extract_returning(RawExtractionResult())
        )
        register_and_login(client, "owner@example.com")
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        client.post("/api/auth/logout")
        register_and_login(client, "someone-else@example.com")

        response = client.post(f"/api/reports/{report_id}/analyze")

        assert response.status_code == 404

    def test_analyzing_without_a_session_returns_401(self, client):
        response = client.post("/api/reports/00000000-0000-0000-0000-000000000000/analyze")

        assert response.status_code == 401


class TestAnalyzePersistence:
    """FR-27, FR-33, FR-07, FR-32: the analyze endpoint writes its result
    into extracted_fields, environment_details and follow_up_questions,
    and moves the report to Analysed."""

    def test_scalar_fields_and_a_step_are_persisted(self, client, monkeypatch):
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        monkeypatch.setattr(
            analysis_module,
            "extract",
            _fake_extract_returning(
                RawExtractionResult(
                    title=RawModelField(
                        value="Login crashes",
                        source_quote="Login crashes",
                        confidence=0.9,
                        reason="Stated directly",
                    ),
                    steps=[
                        RawModelField(
                            value="Click submit",
                            source_quote="click submit",
                            confidence=0.9,
                            reason="Stated directly",
                        )
                    ],
                )
            ),
        )

        response = client.post(f"/api/reports/{report_id}/analyze")
        assert response.status_code == 200

        with TestingSessionLocal() as db:
            fields = db.query(ExtractedField).filter_by(report_id=UUID(report_id)).all()
            by_name = {f.field_name: f for f in fields if f.position is None}
            assert by_name["title"].value == "Login crashes"
            steps = [f for f in fields if f.field_name == "steps"]
            assert len(steps) == 1
            assert steps[0].position == 0
            assert steps[0].value == "Click submit"

    def test_environment_details_are_persisted(self, client, monkeypatch):
        from app.analysis.schema import RawEnvironmentDetail

        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        monkeypatch.setattr(
            analysis_module,
            "extract",
            _fake_extract_returning(
                RawExtractionResult(
                    environment=[
                        RawEnvironmentDetail(name="browser", value="Chrome", source_quote="chrome")
                    ]
                )
            ),
        )

        response = client.post(f"/api/reports/{report_id}/analyze")
        assert response.status_code == 200

        with TestingSessionLocal() as db:
            details = db.query(EnvironmentDetail).filter_by(report_id=UUID(report_id)).all()
            assert len(details) == 1
            assert details[0].name == "browser"
            assert details[0].value == "Chrome"

    def test_follow_up_questions_are_persisted(self, client, monkeypatch):
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        monkeypatch.setattr(
            analysis_module, "extract", _fake_extract_returning(RawExtractionResult())
        )

        response = client.post(f"/api/reports/{report_id}/analyze")
        assert response.status_code == 200

        with TestingSessionLocal() as db:
            questions = db.query(FollowUpQuestionRow).filter_by(report_id=UUID(report_id)).all()
            assert len(questions) >= 1
            assert all(q.answer is None for q in questions)

    def test_the_report_moves_to_analysed(self, client, monkeypatch):
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        monkeypatch.setattr(
            analysis_module, "extract", _fake_extract_returning(RawExtractionResult())
        )

        response = client.post(f"/api/reports/{report_id}/analyze")
        assert response.status_code == 200

        with TestingSessionLocal() as db:
            report = db.get(BugReport, UUID(report_id))
            assert report.state == "Analysed"

    def test_the_report_title_is_set_from_the_extraction(self, client, monkeypatch):
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        monkeypatch.setattr(
            analysis_module,
            "extract",
            _fake_extract_returning(
                RawExtractionResult(
                    title=RawModelField(
                        value="Login crashes on submit",
                        source_quote="Login crashes",
                        confidence=0.9,
                        reason="Condensed from the report",
                    )
                )
            ),
        )

        client.post(f"/api/reports/{report_id}/analyze")

        with TestingSessionLocal() as db:
            report = db.get(BugReport, UUID(report_id))
            assert report.title == "Login crashes on submit"

    def test_re_analyzing_replaces_rather_than_accumulates_rows(self, client, monkeypatch):
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        monkeypatch.setattr(
            analysis_module,
            "extract",
            _fake_extract_returning(
                RawExtractionResult(
                    steps=[
                        RawModelField(
                            value="Click submit",
                            source_quote="click submit",
                            confidence=0.9,
                            reason="Stated directly",
                        )
                    ]
                )
            ),
        )
        client.post(f"/api/reports/{report_id}/analyze")

        monkeypatch.setattr(
            analysis_module, "extract", _fake_extract_returning(RawExtractionResult())
        )
        response = client.post(f"/api/reports/{report_id}/analyze")
        assert response.status_code == 200

        with TestingSessionLocal() as db:
            steps = (
                db.query(ExtractedField)
                .filter_by(report_id=UUID(report_id), field_name="steps")
                .all()
            )
            assert steps == []

    def test_deleting_a_report_removes_its_persisted_analysis(self, client, monkeypatch):
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        monkeypatch.setattr(
            analysis_module,
            "extract",
            _fake_extract_returning(
                RawExtractionResult(
                    title=RawModelField(value="x", source_quote="x", confidence=0.5, reason="x")
                )
            ),
        )
        client.post(f"/api/reports/{report_id}/analyze")

        response = client.delete(f"/api/reports/{report_id}")
        assert response.status_code == 204

        with TestingSessionLocal() as db:
            assert db.query(ExtractedField).filter_by(report_id=UUID(report_id)).count() == 0
            assert db.query(FollowUpQuestionRow).filter_by(report_id=UUID(report_id)).count() == 0


class TestReadAnalysis:
    """GET /api/reports/{id}/analysis (US-13): reads back what `analyze`
    persisted, plus the completeness score."""

    def test_reading_back_a_never_analyzed_report_is_all_missing_not_an_error(self, client):
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]

        response = client.get(f"/api/reports/{report_id}/analysis")

        assert response.status_code == 200
        body = response.json()
        assert body["extraction"]["title"]["label"] == "Missing"
        assert body["extraction"]["steps"] == []
        assert body["completeness"]["verified_count"] == 0
        assert body["completeness"]["total"] == 5

    def test_reading_back_after_analyze_returns_the_same_extraction(self, client, monkeypatch):
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        monkeypatch.setattr(
            analysis_module,
            "extract",
            _fake_extract_returning(
                RawExtractionResult(
                    expected_behaviour=RawModelField(
                        value="an error message",
                        source_quote="jane.doe",
                        confidence=0.6,
                        reason="x",
                    ),
                    steps=[
                        RawModelField(
                            value="Click submit",
                            source_quote="click submit",
                            confidence=0.9,
                            reason="x",
                        ),
                        RawModelField(
                            value="Enter the email",
                            source_quote="enter",
                            confidence=0.5,
                            reason="x",
                        ),
                    ],
                )
            ),
        )
        analyze_response = client.post(f"/api/reports/{report_id}/analyze")

        response = client.get(f"/api/reports/{report_id}/analysis")

        assert response.status_code == 200
        body = response.json()
        assert body["extraction"] == analyze_response.json()["extraction"]
        assert body["questions"] == analyze_response.json()["questions"]

    def test_step_order_is_preserved_on_read_back(self, client, monkeypatch):
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        monkeypatch.setattr(
            analysis_module,
            "extract",
            _fake_extract_returning(
                RawExtractionResult(
                    steps=[
                        RawModelField(
                            value="First step",
                            source_quote="click submit",
                            confidence=0.9,
                            reason="x",
                        ),
                        RawModelField(
                            value="Second step", source_quote="enter", confidence=0.9, reason="x"
                        ),
                    ]
                )
            ),
        )
        client.post(f"/api/reports/{report_id}/analyze")

        response = client.get(f"/api/reports/{report_id}/analysis")

        steps = response.json()["extraction"]["steps"]
        assert [s["value"] for s in steps] == ["First step", "Second step"]

    def test_completeness_score_reflects_what_was_persisted(self, client, monkeypatch):
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        monkeypatch.setattr(
            analysis_module,
            "extract",
            _fake_extract_returning(
                RawExtractionResult(
                    expected_behaviour=RawModelField(
                        value="an error message",
                        source_quote="jane.doe@example.com",
                        confidence=0.9,
                        reason="x",
                    )
                )
            ),
        )
        client.post(f"/api/reports/{report_id}/analyze")

        response = client.get(f"/api/reports/{report_id}/analysis")

        completeness = response.json()["completeness"]
        assert "expected_behaviour" not in completeness["missing_fields"]

    def test_reading_an_unknown_report_id_returns_404(self, client):
        register_and_login(client)

        response = client.get("/api/reports/00000000-0000-0000-0000-000000000000/analysis")

        assert response.status_code == 404

    def test_reading_another_users_analysis_returns_404(self, client):
        register_and_login(client, "owner@example.com")
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        client.post("/api/auth/logout")
        register_and_login(client, "someone-else@example.com")

        response = client.get(f"/api/reports/{report_id}/analysis")

        assert response.status_code == 404

    def test_reading_without_a_session_returns_401(self, client):
        response = client.get("/api/reports/00000000-0000-0000-0000-000000000000/analysis")

        assert response.status_code == 401


MASK_REPORT_TEXT = (
    "Login crashes when I enter jane.doe@example.com and password: hunter2, then click submit."
)


class TestPreviewMasking:
    """POST /api/reports/{id}/mask (US-32 criteria 1 and 4)."""

    def test_detected_items_are_listed_with_their_type(self, client):
        register_and_login(client)
        report_id = create_report(client, MASK_REPORT_TEXT).json()["id"]

        response = client.post(f"/api/reports/{report_id}/mask")

        assert response.status_code == 200
        types = {item["type"] for item in response.json()["items"]}
        assert "email" in types
        assert "password" in types

    def test_nothing_detected_still_returns_200_with_an_empty_list(self, client):
        register_and_login(client)
        report_id = create_report(
            client, REPORT_TEXT.replace("jane.doe@example.com", "nobody")
        ).json()["id"]

        response = client.post(f"/api/reports/{report_id}/mask")

        assert response.status_code == 200
        assert response.json()["items"] == []

    def test_analysis_is_not_run_by_a_mask_preview(self, client, monkeypatch):
        calls = []
        monkeypatch.setattr(analysis_module, "extract", lambda text: calls.append(text))
        register_and_login(client)
        report_id = create_report(client, MASK_REPORT_TEXT).json()["id"]

        client.post(f"/api/reports/{report_id}/mask")

        assert calls == []


class TestAnalyzeWithMaskingAdjustments:
    """POST /api/reports/{id}/analyze with restore_values and
    manual_mask_values (US-32 criteria 2, 3 and 5)."""

    def test_a_restored_value_is_not_masked_and_reaches_the_model(self, client, monkeypatch):
        seen = []

        def fake_extract(text):
            seen.append(text)
            return RawExtractionResult()

        monkeypatch.setattr(analysis_module, "extract", fake_extract)
        register_and_login(client)
        report_id = create_report(client, MASK_REPORT_TEXT).json()["id"]

        response = client.post(
            f"/api/reports/{report_id}/analyze",
            json={"restore_values": ["jane.doe@example.com"]},
        )

        assert response.status_code == 200
        assert "jane.doe@example.com" in seen[0]
        assert not any(
            item["original_text"] == "jane.doe@example.com"
            for item in response.json()["masked_items"]
        )

    def test_every_occurrence_of_a_manually_masked_value_is_masked(self, client, monkeypatch):
        seen = []

        def fake_extract(text):
            seen.append(text)
            return RawExtractionResult()

        monkeypatch.setattr(analysis_module, "extract", fake_extract)
        register_and_login(client)
        report_id = create_report(
            client, "The bug id INTERNAL-42 appeared twice: INTERNAL-42 and INTERNAL-42 again here."
        ).json()["id"]

        response = client.post(
            f"/api/reports/{report_id}/analyze",
            json={"manual_mask_values": ["INTERNAL-42"]},
        )

        assert response.status_code == 200
        assert "INTERNAL-42" not in seen[0]

    def test_no_body_behaves_exactly_as_before(self, client, monkeypatch):
        monkeypatch.setattr(
            analysis_module, "extract", _fake_extract_returning(RawExtractionResult())
        )
        register_and_login(client)
        report_id = create_report(client, MASK_REPORT_TEXT).json()["id"]

        response = client.post(f"/api/reports/{report_id}/analyze")

        assert response.status_code == 200


class TestAnswerQuestion:
    """POST /api/reports/{id}/questions/{question_id}/answer (US-14
    criterion 5)."""

    def _analyze_all_missing(self, client, monkeypatch, report_id):
        monkeypatch.setattr(
            analysis_module, "extract", _fake_extract_returning(RawExtractionResult())
        )
        return client.post(f"/api/reports/{report_id}/analyze").json()

    def test_the_analyze_response_carries_each_questions_persisted_id(self, client, monkeypatch):
        """The frontend answers a question by id; that id has to come back
        from analyze itself, not only from a later GET."""
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        analyzed = self._analyze_all_missing(client, monkeypatch, report_id)

        assert len(analyzed["questions"]) > 0
        for question in analyzed["questions"]:
            assert question["id"]

        question_id = analyzed["questions"][0]["id"]
        response = client.post(
            f"/api/reports/{report_id}/questions/{question_id}/answer",
            json={"answer": "x"},
        )
        assert response.status_code == 200

    def test_answering_a_scalar_question_sets_the_field_to_explicit(self, client, monkeypatch):
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        self._analyze_all_missing(client, monkeypatch, report_id)
        with TestingSessionLocal() as db:
            report = db.get(BugReport, UUID(report_id))
            question = next(q for q in report.follow_up_questions if q.field_name == "frequency")
            question_id = question.id

        response = client.post(
            f"/api/reports/{report_id}/questions/{question_id}/answer",
            json={"answer": "Every time"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["extraction"]["frequency"]["value"] == "Every time"
        assert body["extraction"]["frequency"]["label"] == "Explicit"

    def test_the_completeness_score_updates_immediately(self, client, monkeypatch):
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        analyzed = self._analyze_all_missing(client, monkeypatch, report_id)
        before = analyzed["extraction"]
        assert before["frequency"]["label"] == "Missing"
        with TestingSessionLocal() as db:
            report = db.get(BugReport, UUID(report_id))
            question_id = next(
                q for q in report.follow_up_questions if q.field_name == "frequency"
            ).id

        response = client.post(
            f"/api/reports/{report_id}/questions/{question_id}/answer",
            json={"answer": "Every time"},
        )

        assert response.json()["completeness"]["verified_count"] == 1

    def test_answering_a_steps_question_appends_a_new_step(self, client, monkeypatch):
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        self._analyze_all_missing(client, monkeypatch, report_id)
        with TestingSessionLocal() as db:
            report = db.get(BugReport, UUID(report_id))
            question_id = next(q for q in report.follow_up_questions if q.field_name == "steps").id

        response = client.post(
            f"/api/reports/{report_id}/questions/{question_id}/answer",
            json={"answer": "Open the settings page"},
        )

        steps = response.json()["extraction"]["steps"]
        assert len(steps) == 1
        assert steps[0]["value"] == "Open the settings page"

    def test_answering_an_unknown_question_id_returns_404(self, client, monkeypatch):
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        self._analyze_all_missing(client, monkeypatch, report_id)

        response = client.post(
            f"/api/reports/{report_id}/questions/00000000-0000-0000-0000-000000000000/answer",
            json={"answer": "x"},
        )

        assert response.status_code == 404


class TestReviewEnvironment:
    """POST /api/reports/{id}/environment (US-33)."""

    def test_a_correction_updates_an_existing_detail(self, client, monkeypatch):
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        monkeypatch.setattr(
            analysis_module,
            "extract",
            _fake_extract_returning(
                RawExtractionResult(
                    environment=[
                        RawEnvironmentDetail(name="browser", value="Chrome", source_quote="x")
                    ]
                )
            ),
        )
        client.post(f"/api/reports/{report_id}/analyze")

        response = client.post(
            f"/api/reports/{report_id}/environment",
            json={"corrections": [{"name": "browser", "value": "Firefox"}]},
        )

        assert response.status_code == 200
        env = response.json()["extraction"]["environment"]
        assert any(e["name"] == "browser" and e["value"] == "Firefox" for e in env)

    def test_a_correction_with_a_differently_cased_alias_updates_the_same_detail(
        self, client, monkeypatch
    ):
        """US-10 criterion 3: normalisation applies to corrections too, not
        only to what the model extracts, so "Chrome browser" typed by hand
        matches the existing "browser" row rather than duplicating it."""
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        monkeypatch.setattr(
            analysis_module,
            "extract",
            _fake_extract_returning(
                RawExtractionResult(
                    environment=[
                        RawEnvironmentDetail(name="browser", value="Chrome", source_quote="x")
                    ]
                )
            ),
        )
        client.post(f"/api/reports/{report_id}/analyze")

        response = client.post(
            f"/api/reports/{report_id}/environment",
            json={"corrections": [{"name": "Chrome browser", "value": "Firefox"}]},
        )

        env = response.json()["extraction"]["environment"]
        assert len(env) == 1
        assert env[0]["name"] == "browser"
        assert env[0]["value"] == "Firefox"

    def test_a_removal_deletes_the_detail(self, client, monkeypatch):
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        monkeypatch.setattr(
            analysis_module,
            "extract",
            _fake_extract_returning(
                RawExtractionResult(
                    environment=[
                        RawEnvironmentDetail(name="browser", value="Chrome", source_quote="x")
                    ]
                )
            ),
        )
        client.post(f"/api/reports/{report_id}/analyze")

        response = client.post(
            f"/api/reports/{report_id}/environment", json={"removals": ["browser"]}
        )

        assert response.json()["extraction"]["environment"] == []

    def test_a_new_detail_can_be_added_by_correction(self, client, monkeypatch):
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        monkeypatch.setattr(
            analysis_module, "extract", _fake_extract_returning(RawExtractionResult())
        )
        client.post(f"/api/reports/{report_id}/analyze")

        response = client.post(
            f"/api/reports/{report_id}/environment",
            json={"corrections": [{"name": "device", "value": "iPhone 15"}]},
        )

        env = response.json()["extraction"]["environment"]
        assert any(e["name"] == "device" and e["value"] == "iPhone 15" for e in env)

    def test_additional_details_are_extracted_and_verified_not_stored_raw(
        self, client, monkeypatch
    ):
        """US-33 criterion 4."""
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]

        def fake_extract(text):
            if "postgresql" in text.lower():
                return RawExtractionResult(
                    environment=[
                        RawEnvironmentDetail(
                            name="database",
                            value="PostgreSQL 14",
                            source_quote="postgresql 14",
                        )
                    ]
                )
            return RawExtractionResult()

        monkeypatch.setattr(analysis_module, "extract", fake_extract)
        client.post(f"/api/reports/{report_id}/analyze")

        response = client.post(
            f"/api/reports/{report_id}/environment",
            json={"additional_details": "I was also running postgresql 14"},
        )

        env = response.json()["extraction"]["environment"]
        assert any(e["name"] == "database" and e["label"] == "Explicit" for e in env)

    def test_reviewing_environment_for_an_unknown_report_returns_404(self, client):
        register_and_login(client)

        response = client.post(
            "/api/reports/00000000-0000-0000-0000-000000000000/environment", json={}
        )

        assert response.status_code == 404
