"""Imports existing issues into the shared corpus (FR-16, US-19).

A file is CSV with a header row or JSON holding a list of objects, each
with `id`, `title`, `body` and `url` (criterion 1). A row missing any of
them, or with an unusable value, is reported with the reason and skipped;
the rest of the file still imports (criterion 2). Every imported issue gets
its embedding computed here, at import time, never later during a search
(criterion 3). Importing an `id` that already exists updates that issue in
place, so running the same import twice never duplicates the corpus.
"""

import csv
import io
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.corpus import embedding
from app.models.corpus import CorpusIssue

REQUIRED_FIELDS = ("id", "title", "body", "url")
MAX_ID_LENGTH = 255
# Embedding in batches keeps memory flat for a large file without making a
# small one any slower.
_EMBED_BATCH_SIZE = 64


class SkippedRow(BaseModel):
    """One row that was not imported. `row` counts data rows from 1 in file
    order, not counting a CSV header."""

    row: int
    reason: str


class ImportSummary(BaseModel):
    imported: int
    updated: int
    skipped: list[SkippedRow]


class ImportFileError(ValueError):
    """The file as a whole cannot be read, as opposed to one bad row."""


class _ValidRow(BaseModel):
    external_id: str
    title: str
    body: str
    url: str


def read_rows(path: Path) -> list[Any]:
    """Reads a `.csv` or `.json` file into a list of rows, each normally a
    dict. Anything else, or a file that is not valid CSV or JSON at all, is
    an `ImportFileError`."""
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8-sig")
    if suffix == ".csv":
        return parse_csv(text)
    if suffix == ".json":
        return parse_json(text)
    raise ImportFileError(f"Unsupported file type {suffix or '(none)'}; use .csv or .json")


def parse_csv(text: str) -> list[Any]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ImportFileError("The CSV file is empty")
    return list(reader)


def parse_json(text: str) -> list[Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ImportFileError(f"The JSON file is not valid JSON: {error.msg}") from error
    if not isinstance(data, list):
        raise ImportFileError("The JSON file must contain a list of issues")
    return data


def _validate(row: Any) -> _ValidRow | str:
    """The row cleaned up, or the reason it cannot be imported."""
    if not isinstance(row, dict):
        return "Not an object with id, title, body and url"
    missing = [name for name in REQUIRED_FIELDS if name not in row or row[name] is None]
    if missing:
        return f"Missing {', '.join(missing)}"
    values = {name: str(row[name]).strip() for name in REQUIRED_FIELDS}
    blank = [name for name in REQUIRED_FIELDS if not values[name]]
    if blank:
        return f"Empty {', '.join(blank)}"
    if len(values["id"]) > MAX_ID_LENGTH:
        return f"id is longer than {MAX_ID_LENGTH} characters"
    if not values["url"].startswith(("http://", "https://")):
        return "url must start with http:// or https://"
    return _ValidRow(
        external_id=values["id"], title=values["title"], body=values["body"], url=values["url"]
    )


def corpus_embedding_text(title: str, body: str) -> str:
    """What gets embedded for a corpus issue: its title, then its body."""
    return f"{title}\n{body}"


def import_rows(db: Session, rows: list[Any]) -> ImportSummary:
    """Validates every row, embeds the valid ones, and inserts or updates
    them. Commits once at the end."""
    skipped: list[SkippedRow] = []
    valid: list[_ValidRow] = []
    seen_ids: set[str] = set()

    for position, row in enumerate(rows, start=1):
        result = _validate(row)
        if isinstance(result, str):
            skipped.append(SkippedRow(row=position, reason=result))
            continue
        if result.external_id in seen_ids:
            skipped.append(
                SkippedRow(row=position, reason=f"Duplicate id {result.external_id} in this file")
            )
            continue
        seen_ids.add(result.external_id)
        valid.append(result)

    vectors: list[list[float]] = []
    for start in range(0, len(valid), _EMBED_BATCH_SIZE):
        batch = valid[start : start + _EMBED_BATCH_SIZE]
        vectors.extend(embedding.embed([corpus_embedding_text(r.title, r.body) for r in batch]))

    existing = {
        issue.external_id: issue
        for issue in db.execute(
            select(CorpusIssue).where(CorpusIssue.external_id.in_(seen_ids))
        ).scalars()
    }

    imported = updated = 0
    for row, vector in zip(valid, vectors, strict=True):
        issue = existing.get(row.external_id)
        if issue is None:
            db.add(
                CorpusIssue(
                    external_id=row.external_id,
                    title=row.title,
                    body=row.body,
                    url=row.url,
                    embedding=vector,
                )
            )
            imported += 1
        else:
            issue.title = row.title
            issue.body = row.body
            issue.url = row.url
            issue.embedding = vector
            updated += 1

    db.commit()
    return ImportSummary(imported=imported, updated=updated, skipped=skipped)


def import_file(db: Session, path: Path) -> ImportSummary:
    return import_rows(db, read_rows(path))
