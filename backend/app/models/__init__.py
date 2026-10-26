"""Importing this package registers every model module's tables on
Base.metadata, and resolves the forward-referenced relationships between
core.py and analysis.py. Anything that needs the full schema (Alembic,
Base.metadata.create_all in tests) should import this package, or import
both submodules itself, rather than importing only one."""

from app.models import analysis, core  # noqa: F401
