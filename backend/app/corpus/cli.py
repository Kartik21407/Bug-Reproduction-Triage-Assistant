"""Command line for whoever operates the server to manage the shared corpus.

Importing is an operator task, not something any signed-in user can do
(ADR-010, ADR-025), so it is a command rather than an endpoint:

    python -m app.corpus.cli fetch-github OWNER/NAME --label bug --limit 300 --out issues.json
    python -m app.corpus.cli import issues.json

Inside Docker Compose, prefix either with `docker compose exec backend`.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from app.corpus.github import GitHubFetchError, fetch_issues

if TYPE_CHECKING:
    from app.corpus.importer import SkippedRow


def _fetch_github(args: argparse.Namespace) -> int:
    try:
        rows = fetch_issues(args.repository, args.label, args.limit, args.token)
    except GitHubFetchError as error:
        print(f"Fetch failed: {error}", file=sys.stderr)
        return 1
    Path(args.out).write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(rows)} issues from {args.repository} to {args.out}")
    return 0


def _import(args: argparse.Namespace) -> int:
    # Imported here rather than at the top so `fetch-github`, which never
    # touches the database, works without a database configured.
    from app.corpus.embedding import EmbeddingUnavailableError
    from app.corpus.importer import ImportFileError, import_file
    from app.db import SessionLocal

    with SessionLocal() as db:
        try:
            summary = import_file(db, Path(args.path))
        except (ImportFileError, EmbeddingUnavailableError, OSError) as error:
            print(f"Import failed: {error}", file=sys.stderr)
            return 1
    print(format_summary(summary.imported, summary.updated, summary.skipped))
    return 0


def format_summary(imported: int, updated: int, skipped: "list[SkippedRow]") -> str:
    lines = [f"Imported {imported} new, updated {updated}, skipped {len(skipped)}."]
    lines += [f"  Row {row.row}: {row.reason}" for row in skipped]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.corpus.cli")
    commands = parser.add_subparsers(dest="command", required=True)

    fetch = commands.add_parser("fetch-github", help="Write public GitHub issues to a JSON file")
    fetch.add_argument("repository", help="owner/name, for example nextcloud/server")
    fetch.add_argument("--label", default="bug", help="only issues with this label")
    fetch.add_argument("--limit", type=int, default=300)
    fetch.add_argument("--out", required=True, help="the JSON file to write")
    fetch.add_argument("--token", default=None, help="optional GitHub token, for rate limits")
    fetch.set_defaults(handler=_fetch_github)

    load = commands.add_parser("import", help="Import a CSV or JSON file into the corpus")
    load.add_argument("path")
    load.set_defaults(handler=_import)

    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
