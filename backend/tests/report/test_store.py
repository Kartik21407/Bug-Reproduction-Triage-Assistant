"""Tests for how fields are stored and corrected (app/report/store.py,
ADR-011, ADR-027): a person's version always wins, re-analysis replaces
only the model's rows, and reset brings the suggestion back. Works on
in-memory rows, so no database is needed."""

from app.analysis.schema import EnvironmentDetail, ExtractedField, ExtractionResult, Label
from app.models.core import BugReport
from app.report import store


def _field(value: str | None, label: Label = Label.EXPLICIT) -> ExtractedField:
    if value is None:
        return ExtractedField(value=None, source_quote=None, label=Label.MISSING)
    return ExtractedField(value=value, source_quote=value, label=label)


def _model_result(**overrides: object) -> ExtractionResult:
    fields: dict[str, object] = {
        "title": _field("Login crashes"),
        "summary": _field("The login page crashes", Label.INFERRED),
        "expected_behaviour": _field("An error message"),
        "actual_behaviour": _field("The app closes"),
        "frequency": _field(None),
        "steps": [_field("Open login"), _field("Enter a wrong password")],
        "environment": [
            EnvironmentDetail(
                name="browser", value="Chrome", source_quote="chrome", label="Explicit"
            ),
            EnvironmentDetail(name="os", value="Windows", source_quote="windows", label="Explicit"),
        ],
        "error_messages": [],
    }
    fields.update(overrides)
    return ExtractionResult(**fields)


def _analysed_report(**overrides: object) -> BugReport:
    report = BugReport(original_text="x" * 20)
    store.replace_model_result(report, _model_result(**overrides))
    return report


class TestReading:
    def test_the_model_result_reads_back_as_stored(self):
        report = _analysed_report()

        extraction = store.read_extraction(report)

        assert extraction.title.value == "Login crashes"
        assert extraction.summary.label == Label.INFERRED
        assert [s.value for s in extraction.steps] == ["Open login", "Enter a wrong password"]
        assert [d.name for d in extraction.environment] == ["browser", "os"]
        assert store.edited_fields(report) == set()

    def test_a_persons_scalar_wins_over_the_models(self):
        report = _analysed_report()

        store.set_scalar(report, "title", "Wrong password closes the app")

        assert store.read_extraction(report).title.value == "Wrong password closes the app"
        assert store.read_extraction(report).title.label == Label.EXPLICIT
        assert report.title == "Wrong password closes the app"
        assert store.edited_fields(report) == {"title"}

    def test_clearing_a_field_reads_as_missing(self):
        report = _analysed_report()

        store.set_scalar(report, "summary", "   ")

        assert store.read_extraction(report).summary.label == Label.MISSING

    def test_a_persons_list_replaces_the_models_list_as_a_whole(self):
        report = _analysed_report()

        store.set_list(report, "steps", ["Go to /login", "", "Type a wrong password", "Submit"])

        steps = [s.value for s in store.read_extraction(report).steps]
        assert steps == ["Go to /login", "Type a wrong password", "Submit"]

    def test_an_empty_list_a_person_saved_stays_empty(self):
        report = _analysed_report()

        store.set_list(report, "steps", [])

        assert store.read_extraction(report).steps == []
        assert "steps" in store.edited_fields(report)

    def test_appending_keeps_everything_the_person_already_saw(self):
        report = _analysed_report()

        store.append_to_list(report, "steps", "Click Login")

        steps = [s.value for s in store.read_extraction(report).steps]
        assert steps == ["Open login", "Enter a wrong password", "Click Login"]


class TestEnvironment:
    def test_a_correction_replaces_the_model_detail_in_place(self):
        report = _analysed_report()

        store.set_environment_detail(report, "browser", "Firefox 131")

        details = [(d.name, d.value) for d in store.read_extraction(report).environment]
        assert details == [("browser", "Firefox 131"), ("os", "Windows")]

    def test_a_removed_detail_is_hidden(self):
        report = _analysed_report()

        store.remove_environment_detail(report, "os")

        assert [d.name for d in store.read_extraction(report).environment] == ["browser"]

    def test_a_detail_the_person_added_is_listed_after_the_models(self):
        report = _analysed_report()

        store.set_environment_detail(report, "device", "Pixel 8")

        assert [d.name for d in store.read_extraction(report).environment] == [
            "browser",
            "os",
            "device",
        ]

    def test_setting_the_whole_list_removes_what_is_left_out(self):
        report = _analysed_report()

        store.set_environment(report, [("browser", "Edge"), ("device", "Laptop")])

        details = [(d.name, d.value) for d in store.read_extraction(report).environment]
        assert details == [("browser", "Edge"), ("device", "Laptop")]


class TestReanalysis:
    """ADR-011: re-analysis keeps what a person changed and refreshes the
    rest."""

    def test_corrections_survive_and_untouched_fields_refresh(self):
        report = _analysed_report()
        store.set_scalar(report, "title", "My own title")
        store.set_list(report, "steps", ["My step"])
        store.set_environment_detail(report, "browser", "Firefox")
        store.remove_environment_detail(report, "os")

        store.replace_model_result(
            report,
            _model_result(
                title=_field("A new suggested title"),
                summary=_field("A new summary"),
                steps=[_field("New step one")],
                environment=[
                    EnvironmentDetail(
                        name="browser", value="Safari", source_quote="safari", label="Explicit"
                    ),
                    EnvironmentDetail(
                        name="os", value="macOS", source_quote="macos", label="Explicit"
                    ),
                ],
            ),
        )

        extraction = store.read_extraction(report)
        assert extraction.title.value == "My own title"
        assert extraction.summary.value == "A new summary"
        assert [s.value for s in extraction.steps] == ["My step"]
        assert [(d.name, d.value) for d in extraction.environment] == [("browser", "Firefox")]

    def test_reset_after_reanalysis_shows_the_latest_suggestion(self):
        """US-24 criterion 3: "Reset to suggested" restores the system
        version, the current one."""
        report = _analysed_report()
        store.set_scalar(report, "title", "My own title")
        store.replace_model_result(report, _model_result(title=_field("Newest suggestion")))

        store.reset_field(report, "title")

        assert store.read_extraction(report).title.value == "Newest suggestion"
        assert report.title == "Newest suggestion"
        assert store.edited_fields(report) == set()

    def test_resetting_the_environment_brings_back_every_model_detail(self):
        report = _analysed_report()
        store.set_environment(report, [("device", "Laptop")])

        store.reset_field(report, "environment")

        assert [d.name for d in store.read_extraction(report).environment] == ["browser", "os"]


class TestNote:
    def test_the_note_is_only_ever_a_persons(self):
        report = _analysed_report()
        assert store.read_note(report) is None

        store.set_scalar(report, store.NOTE_FIELD, "Started after the 2.3 release")

        assert store.read_note(report) == "Started after the 2.3 release"
        assert store.NOTE_FIELD in store.edited_fields(report)
