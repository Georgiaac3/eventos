"""Alembic environment. The database URL comes from the app config (.env.local or real env vars):
MIGRATIONS_DATABASE_URL if set, else DATABASE_URL. On Supabase, migrate through the direct
connection or the session pooler (port 5432), not the transaction pooler the app uses (6543).
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from backend import config as app_config
from backend.db import metadata, sqlalchemy_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata


def database_url() -> str:
    url = app_config.env("MIGRATIONS_DATABASE_URL") or app_config.DATABASE_URL
    if not url:
        raise RuntimeError("Set DATABASE_URL (or MIGRATIONS_DATABASE_URL) to run migrations.")
    return sqlalchemy_url(url)


def include_object(obj, name, type_, reflected, compare_to):
    # Only manage tables we define; ignore anything else living in the public schema.
    if type_ == "table" and reflected and compare_to is None:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(url=database_url(), target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"}, include_object=include_object, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(database_url(), poolclass=pool.NullPool, connect_args={"prepare_threshold": None})
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, include_object=include_object,
                          compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
