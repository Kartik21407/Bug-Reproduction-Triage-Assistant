## What this changes

A short description of the change, in plain language.

## Story

Closes #<issue number> (US-XX)

Acceptance criteria covered by this pull request:

1.
2.

## How to check it

Steps a reviewer can follow to see the change working.

1.
2.

## Checklist

- [ ] The branch is named `feat/US-XX-short-description` (or `fix/`, `docs/`, `chore/`)
- [ ] Commits follow Conventional Commits, and each commit is by the person who wrote it
- [ ] Virtual environment active; backend: `ruff check .`, `ruff format --check .`, `pytest` all pass
- [ ] Frontend: `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm run test` all pass
- [ ] Every acceptance criterion above has at least one test
- [ ] Schema changes include an Alembic migration in this pull request
- [ ] `docs/status.md` updated, and `docs/design.md` updated if the data model, API or flow changed
- [ ] No secrets, tokens or `.env` files are included
- [ ] One reviewer assigned, CI green before merge
