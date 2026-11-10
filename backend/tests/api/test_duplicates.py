"""Tests for GET and POST /api/reports/{id}/duplicates (app/api/duplicates.py
and app/corpus/search.py): US-20, FR-17, NFR-02, ADR-010.

Scores are controlled exactly by giving each text a chosen unit vector, so
a test can say "this issue scores 0.90" rather than depending on how words
happen to hash. No test loads the real embedding model."""

import time

import pytest

from app.corpus import embedding
from app.corpus.importer import import_rows
from app.models.types import EMBEDDING_DIMENSIONS
from tests.conftest import TestingSessionLocal, create_report, register_and_login

REPORT_TEXT = "Saving the settings page shows a blank screen afterwards."
_QUERY = [1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1)


def _vector_scoring(similarity: float) -> list[float]:
    """A unit vector whose cosine similarity with _QUERY is `similarity`."""
    vector = [0.0] * EMBEDDING_DIMENSIONS
    vector[0] = similarity
    vector[1] = (1 - similarity**2) ** 0.5
    return vector


def _use_scores(monkeypatch: pytest.MonkeyPatch, scores: dict[str, float]) -> None:
    """Texts whose first line is a key get the vector scoring that value
    against the report; every other text, including the report itself, gets
    _QUERY."""

    def fake_embed(texts: list[str]) -> list[list[float]]:
        return [
            _vector_scoring(scores[t.split("\n")[0]]) if t.split("\n")[0] in scores else _QUERY
            for t in texts
        ]

    monkeypatch.setattr(embedding, "embed", fake_embed)


def _import_corpus(titles: list[str]) -> None:
    rows = [
        {
            "id": f"acme/app#{n}",
            "title": title,
            "body": f"Body {n}",
            "url": f"https://github.com/acme/app/issues/{n}",
        }
        for n, title in enumerate(titles, start=1)
    ]
    with TestingSessionLocal() as db:
        import_rows(db, rows)


class TestRanking:
    def test_the_top_five_are_shown_most_similar_first(self, client, monkeypatch):
        """US-20 criterion 1: the top five candidates are shown, sorted by
        similarity score."""
        scores = {f"Issue {n}": s for n, s in enumerate([0.70, 0.95, 0.65, 0.85, 0.90, 0.82, 0.75])}
        _use_scores(monkeypatch, scores)
        _import_corpus(list(scores))
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]

        response = client.post(f"/api/reports/{report_id}/duplicates")

        assert response.status_code == 200
        candidates = response.json()["candidates"]
        assert [c["title"] for c in candidates] == [
            "Issue 1",
            "Issue 4",
            "Issue 3",
            "Issue 5",
            "Issue 6",
        ]
        assert [c["rank"] for c in candidates] == [1, 2, 3, 4, 5]
        assert [round(c["score"], 2) for c in candidates] == [0.95, 0.90, 0.85, 0.82, 0.75]

    def test_labels_follow_the_thresholds_and_low_scores_are_hidden(self, client, monkeypatch):
        """US-20 criterion 2: 0.80 or above is "Likely duplicate", 0.60 to
        0.80 "Possible duplicate", and lower scores are hidden."""
        scores = {"Close match": 0.90, "Partial match": 0.70, "Weak match": 0.50}
        _use_scores(monkeypatch, scores)
        _import_corpus(list(scores))
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]

        candidates = client.post(f"/api/reports/{report_id}/duplicates").json()["candidates"]

        assert [(c["title"], c["label"]) for c in candidates] == [
            ("Close match", "Likely duplicate"),
            ("Partial match", "Possible duplicate"),
        ]

    def test_the_wording_never_states_that_a_report_is_a_duplicate(self, client, monkeypatch):
        """US-20 criterion 3 and DR-05: only "Likely" or "Possible"."""
        scores = {"Identical issue": 1.0, "Close match": 0.90, "Partial match": 0.70}
        _use_scores(monkeypatch, scores)
        _import_corpus(list(scores))
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]

        response = client.post(f"/api/reports/{report_id}/duplicates")

        labels = {c["label"] for c in response.json()["candidates"]}
        assert labels <= {"Likely duplicate", "Possible duplicate"}
        assert "is a duplicate" not in response.text.lower()

    def test_a_corpus_candidate_links_to_the_issue_itself(self, client, monkeypatch):
        _use_scores(monkeypatch, {"Close match": 0.90})
        _import_corpus(["Close match"])
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]

        candidate = client.post(f"/api/reports/{report_id}/duplicates").json()["candidates"][0]

        assert candidate["source"] == "corpus"
        assert candidate["url"] == "https://github.com/acme/app/issues/1"

    def test_searching_again_replaces_the_previous_candidates(self, client, monkeypatch):
        _use_scores(monkeypatch, {"Close match": 0.90})
        _import_corpus(["Close match"])
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        client.post(f"/api/reports/{report_id}/duplicates")

        response = client.post(f"/api/reports/{report_id}/duplicates")

        assert len(response.json()["candidates"]) == 1


class TestPerformance:
    def test_search_over_100_stored_issues_returns_in_under_2_seconds(self, client):
        """US-20 criterion 4 and NFR-02: duplicate search over 100 stored
        issues returns results in under 2 seconds. Measured here with the
        stand-in model and the SQLite scoring path; measured again live
        against PostgreSQL and the real model (docs/status.md)."""
        _import_corpus([f"Issue number {n} about the settings page" for n in range(100)])
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]

        started = time.perf_counter()
        response = client.post(f"/api/reports/{report_id}/duplicates")
        elapsed = time.perf_counter() - started

        assert response.status_code == 200
        assert response.json()["compared_count"] == 100
        assert elapsed < 2.0


class TestOwnReports:
    def test_the_users_own_earlier_report_is_a_candidate(self, client, monkeypatch):
        """ADR-010: the comparison set is the corpus plus the user's own
        past reports."""
        _use_scores(monkeypatch, {"An earlier report about the same blank screen.": 0.92})
        register_and_login(client)
        earlier_id = create_report(client, "An earlier report about the same blank screen.").json()[
            "id"
        ]
        client.post(f"/api/reports/{earlier_id}/duplicates")
        report_id = create_report(client, REPORT_TEXT).json()["id"]

        candidates = client.post(f"/api/reports/{report_id}/duplicates").json()["candidates"]

        assert len(candidates) == 1
        assert candidates[0]["source"] == "report"
        assert candidates[0]["id"] == earlier_id
        assert candidates[0]["url"] == f"/reports/{earlier_id}"

    def test_another_users_report_is_never_a_candidate(self, client):
        """NFR-15: another user's report is invisible, even as a candidate.
        Same text as the other user's report, so it would score 1.0."""
        register_and_login(client, "owner@example.com")
        theirs = create_report(client, REPORT_TEXT).json()["id"]
        client.post(f"/api/reports/{theirs}/duplicates")
        client.post("/api/auth/logout")
        register_and_login(client, "other@example.com")
        mine = create_report(client, REPORT_TEXT).json()["id"]

        response = client.post(f"/api/reports/{mine}/duplicates")

        assert response.json()["candidates"] == []
        assert response.json()["compared_count"] == 0

    def test_the_report_is_never_its_own_candidate(self, client):
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        client.post(f"/api/reports/{report_id}/duplicates")

        response = client.post(f"/api/reports/{report_id}/duplicates")

        assert response.json()["candidates"] == []


class TestReadAndAccess:
    def test_a_report_never_searched_reads_back_empty_not_as_an_error(self, client):
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]

        response = client.get(f"/api/reports/{report_id}/duplicates")

        assert response.status_code == 200
        assert response.json() == {"searched": False, "compared_count": 0, "candidates": []}

    def test_the_stored_candidates_read_back_in_order(self, client, monkeypatch):
        scores = {"Close match": 0.90, "Partial match": 0.70}
        _use_scores(monkeypatch, scores)
        _import_corpus(list(scores))
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        searched = client.post(f"/api/reports/{report_id}/duplicates").json()

        response = client.get(f"/api/reports/{report_id}/duplicates")

        assert response.json() == searched
        assert response.json()["searched"] is True

    def test_another_users_report_returns_404(self, client):
        """NFR-15."""
        register_and_login(client, "owner@example.com")
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        client.post("/api/auth/logout")
        register_and_login(client, "other@example.com")

        assert client.get(f"/api/reports/{report_id}/duplicates").status_code == 404
        assert client.post(f"/api/reports/{report_id}/duplicates").status_code == 404

    def test_not_signed_in_returns_401(self, client):
        response = client.post("/api/reports/00000000-0000-0000-0000-000000000000/duplicates")

        assert response.status_code == 401

    def test_an_unavailable_model_is_a_503_and_keeps_the_previous_candidates(
        self, client, monkeypatch
    ):
        """A failed model download is said plainly, never a bare 500, and
        nothing already stored is lost."""
        _use_scores(monkeypatch, {"Close match": 0.90})
        _import_corpus(["Close match"])
        register_and_login(client)
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        client.post(f"/api/reports/{report_id}/duplicates")

        def unavailable(texts: list[str]) -> list[list[float]]:
            raise embedding.EmbeddingUnavailableError("download failed")

        monkeypatch.setattr(embedding, "embed", unavailable)

        response = client.post(f"/api/reports/{report_id}/duplicates")

        assert response.status_code == 503
        assert response.json()["detail"] == (
            "Duplicate search is unavailable right now. Try again later."
        )
        stored = client.get(f"/api/reports/{report_id}/duplicates").json()
        assert [c["title"] for c in stored["candidates"]] == ["Close match"]

    def test_deleting_a_report_removes_it_from_others_candidates(self, client, monkeypatch):
        """US-07 criterion 2: deleting a report removes everything linked to
        it, including where it was listed as someone's candidate."""
        _use_scores(monkeypatch, {"An earlier report about the same blank screen.": 0.92})
        register_and_login(client)
        earlier_id = create_report(client, "An earlier report about the same blank screen.").json()[
            "id"
        ]
        client.post(f"/api/reports/{earlier_id}/duplicates")
        report_id = create_report(client, REPORT_TEXT).json()["id"]
        client.post(f"/api/reports/{report_id}/duplicates")

        client.delete(f"/api/reports/{earlier_id}")

        assert client.get(f"/api/reports/{report_id}/duplicates").json()["candidates"] == []
