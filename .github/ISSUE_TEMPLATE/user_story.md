---
name: User story
about: One issue per user story from the product backlog
title: "US-XX: "
labels: []
assignees: []
---

## Front of the card

As a <role>, I want <goal>, so that <benefit>.

## Conditions of satisfaction

Copy these verbatim from Section 6 of the requirements report. Do not
paraphrase them; they are what the story is accepted against.

1.
2.
3.

## Details

| Field | Value |
| --- | --- |
| Story ID | US-XX |
| EPIC | E<n> <name> |
| Story points | |
| MoSCoW priority | Must / Should / Could |
| Requirements covered | FR-XX, NFR-XX, DR-XX |
| Sprint | |
| Owner | |

## Definition of done

- [ ] Acceptance criteria met, each one covered by at least one test
- [ ] Backend tests pass (`ruff check`, `ruff format --check`, `pytest`)
- [ ] Frontend tests pass (`npm run lint`, `npm run format:check`, `npm run test`)
- [ ] Documentation updated: `docs/status.md`, plus `docs/design.md`,
      `docs/adr.md`, `docs/glossary.md` or `docs/conventions.md` if affected
- [ ] Database change, if any, has an Alembic migration in the same change
- [ ] Reviewed and approved by one other member, CI green
