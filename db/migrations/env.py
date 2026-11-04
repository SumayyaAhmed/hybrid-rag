"""Alembic entry point: connects to DATABASE_URL and runs the migrations in versions/.

No ORM models (target_metadata = None), so `alembic revision --autogenerate` is not used:
every migration is hand-written SQL via op.execute(). See specs/05-migrations.md.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from rag.config import settings

if context.config.config_file_name is not None:
    fileConfig(context.config.config_file_name)

# Tests can point Alembic at a scratch database via config.attributes["database_url"]; normally it's DATABASE_URL.
# .env has postgresql://…; "+psycopg" tells SQLAlchemy to use psycopg 3 (already installed) instead of psycopg2.
url = context.config.attributes.get("database_url", settings.database_url).replace("postgresql://", "postgresql+psycopg://", 1)


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: print the SQL instead of running it."""
    context.configure(url=url, target_metadata=None, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        # one transaction per migration: a failing file rolls back alone, earlier ones stay applied
        context.configure(connection=connection, target_metadata=None, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
