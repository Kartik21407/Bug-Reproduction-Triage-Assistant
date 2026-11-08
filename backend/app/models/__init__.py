"""Importing this package registers every model module's tables on
Base.metadata, and resolves the forward-referenced relationships between
core.py and the other modules. Anything that needs the full schema
(Alembic, Base.metadata.create_all in tests) should import this package,
rather than importing only some of the submodules."""

from app.models import analysis, core, corpus, triage  # noqa: F401
