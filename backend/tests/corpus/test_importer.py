"""Tests for importing existing issues into the shared corpus
(app/corpus/importer.py, US-19, FR-16). The embedding model is the
conftest stand-in, never the real one."""

import json

import pytest
from sqlalchemy import select

from app.corpus import embedding
from app.corpus.importer import ImportFileError, import_file, import_rows, read_rows
from app.models.corpus import CorpusIssue
from app.models.types import EMBEDDING_DIMENSIONS
from tests.conftest import TestingSessionLocal


def _issue(issue_id: str = "acme/app#1", **overrides: str) -> dict[str, str]:
    row = {
        "id": issue_id,
        "title": "Login page crashes on a wrong password",
        "body": "Entering a wrong password closes the application.",
        "url": f"https://github.com/acme/app/issues/{issue_id.split('#')[-1]}",
    }
    row.update(overrides)
    return row


def _stored() -> list[CorpusIssue]:
    with TestingSessionLocal() as db:
        return list(db.execute(select(CorpusIssue).order_by(CorpusIssue.external_id)).scalars())


class TestAcceptedFormats:
    def test_a_json_file_is_imported(self, tmp_path):
        """US-19 criterion 1: JSON files with id, title, body and url are
        accepted."""
        path = tmp_path / "issues.json"
        path.write_text(json.dumps([_issue("acme/app#1"), _issue("acme/app#2")]), encoding="utf-8")

        with TestingSessionLocal() as db:
            summary = import_file(db, path)

        assert summary.imported == 2
        assert summary.skipped == []
        assert [issue.external_id for issue in _stored()] == ["acme/app#1", "acme/app#2"]

    def test_a_csv_file_is_imported(self, tmp_path):
        """US-19 criterion 1: CSV files with id, title, body and url are
        accepted."""
        path = tmp_path / "issues.csv"
        path.write_text(
            "id,title,body,url\n"
            "7,Search is slow,Takes 30 seconds,https://example.com/issues/7\n"
            '8,"Typo, footer","The footer says ""Copyrigth""",https://example.com/issues/8\n',
            encoding="utf-8",
        )

        with TestingSessionLocal() as db:
            summary = import_file(db, path)

        assert summary.imported == 2
        stored = {issue.external_id: issue for issue in _stored()}
        assert stored["8"].title == "Typo, footer"
        assert stored["8"].body == 'The footer says "Copyrigth"'

    def test_another_file_type_is_refused_as_a_whole(self, tmp_path):
        path = tmp_path / "issues.txt"
        path.write_text("id,title", encoding="utf-8")

        with pytest.raises(ImportFileError):
            read_rows(path)

    def test_json_that_is_not_a_list_is_refused_as_a_whole(self, tmp_path):
        path = tmp_path / "issues.json"
        path.write_text(json.dumps({"issues": []}), encoding="utf-8")

        with pytest.raises(ImportFileError):
            read_rows(path)

    def test_invalid_json_is_refused_as_a_whole(self, tmp_path):
        path = tmp_path / "issues.json"
        path.write_text("[{not json", encoding="utf-8")

        with pytest.raises(ImportFileError):
            read_rows(path)


class TestInvalidRows:
    @pytest.mark.parametrize(
        ("row", "reason"),
        [
            ({"title": "t", "body": "b", "url": "https://x.io/1"}, "Missing id"),
            ({"id": "1", "title": "t", "url": "https://x.io/1"}, "Missing body"),
            (_issue(title="   "), "Empty title"),
            (_issue(url="github.com/acme/app/issues/1"), "url must start with http:// or https://"),
            ("just a string", "Not an object with id, title, body and url"),
        ],
    )
    def test_an_invalid_row_is_reported_with_its_reason_and_skipped(self, row, reason):
        """US-19 criterion 2: invalid rows are reported and skipped."""
        with TestingSessionLocal() as db:
            summary = import_rows(db, [row])

        assert summary.imported == 0
        assert len(summary.skipped) == 1
        assert summary.skipped[0].row == 1
        assert summary.skipped[0].reason == reason

    def test_valid_rows_still_import_around_an_invalid_one(self):
        """US-19 criterion 2: one bad row does not fail the whole file."""
        rows = [_issue("acme/app#1"), _issue("acme/app#2", url="not a url"), _issue("acme/app#3")]

        with TestingSessionLocal() as db:
            summary = import_rows(db, rows)

        assert summary.imported == 2
        assert [(s.row, s.reason) for s in summary.skipped] == [
            (2, "url must start with http:// or https://")
        ]
        assert [issue.external_id for issue in _stored()] == ["acme/app#1", "acme/app#3"]

    def test_a_repeated_id_in_one_file_is_skipped(self):
        with TestingSessionLocal() as db:
            summary = import_rows(db, [_issue("acme/app#1"), _issue("acme/app#1")])

        assert summary.imported == 1
        assert summary.skipped[0].reason == "Duplicate id acme/app#1 in this file"

    def test_an_id_longer_than_the_column_is_skipped(self):
        with TestingSessionLocal() as db:
            summary = import_rows(db, [_issue("x" * 256)])

        assert summary.imported == 0
        assert summary.skipped[0].reason == "id is longer than 255 characters"


class TestEmbeddingsAtImport:
    def test_every_imported_issue_has_its_embedding_computed(self):
        """US-19 criterion 3: similarity representations are computed at
        import time."""
        with TestingSessionLocal() as db:
            import_rows(db, [_issue("acme/app#1"), _issue("acme/app#2")])

        for issue in _stored():
            assert len(issue.embedding) == EMBEDDING_DIMENSIONS
            assert any(component != 0 for component in issue.embedding)

    def test_an_unavailable_model_writes_nothing(self, monkeypatch):
        """Embedding happens before any row is written, so a failed model
        download never leaves a half-imported corpus."""

        def unavailable(texts: list[str]) -> list[list[float]]:
            raise embedding.EmbeddingUnavailableError("download failed")

        monkeypatch.setattr(embedding, "embed", unavailable)

        with TestingSessionLocal() as db, pytest.raises(embedding.EmbeddingUnavailableError):
            import_rows(db, [_issue("acme/app#1")])

        assert _stored() == []

    def test_re_importing_an_id_updates_it_instead_of_adding_a_copy(self):
        with TestingSessionLocal() as db:
            import_rows(db, [_issue("acme/app#1")])
        with TestingSessionLocal() as db:
            summary = import_rows(db, [_issue("acme/app#1", title="Renamed issue")])

        assert summary.imported == 0
        assert summary.updated == 1
        stored = _stored()
        assert len(stored) == 1
        assert stored[0].title == "Renamed issue"
