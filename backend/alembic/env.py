from logging.config import fileConfig

from alembic import context

from app.config import get_settings
from app.db.base import Base
from app.db import models  # noqa: F401  (registers tables on Base.metadata)
from app.db.session import build_engine

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    return config.get_main_option("sqlalchemy.url") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=_database_url(), target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _database_url()
    engine = build_engine(url)
    is_sqlite = url.startswith("sqlite")
    with engine.connect() as connection:
        if is_sqlite:
            # SQLite can't ALTER most things, so batch mode copies a table, drops
            # the original and renames the copy. With foreign keys enforced, that
            # DROP would cascade-delete every child row (dropping `users` would
            # wipe all posts and votes). Alembic's documented fix: switch
            # enforcement off while migrating (the PRAGMA only works outside a
            # transaction) and check integrity afterwards.
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()  # close SQLAlchemy's auto-begun transaction before Alembic opens its own
        # Batch mode lets future ALTERs work on SQLite; it is a no-op cost on PostgreSQL.
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
        if is_sqlite:
            problems = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()
            if problems:
                raise RuntimeError(f"foreign key violations after migration: {problems[:5]}")
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
