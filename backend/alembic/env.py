"""Alembic entry point. Wires the SQLAlchemy metadata and DATABASE_URL into
migrations, so `alembic revision --autogenerate` can diff the models against
the real database and every migration runs against the same URL the
application uses."""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.config import get_settings
from app.db import Base

# Imported so every module's tables register on Base.metadata before
# autogenerate diffs against it.
from app.models import analysis, core  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# The URL is read from settings (the environment), never written into
# alembic.ini, so no credential is ever committed.
config.set_main_option("sqlalchemy.url", get_settings().database_url)


def run_migrations_offline() -> None:
    """Runs migrations without a live database connection, emitting SQL to
    stdout. Used for `alembic upgrade head --sql`."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Runs migrations against a live database connection. The normal path."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
