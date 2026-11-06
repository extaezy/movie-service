import asyncio
from logging.config import fileConfig

from alembic import context
from app.db.models import SCHEMA, Base
from app.db.settings import DatabaseSettings, connection_options
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata
database_settings = DatabaseSettings()
database_url, connect_args = connection_options(database_settings)


def include_name(name, type_, parent_names):
    if type_ == "schema":
        return name == SCHEMA
    if type_ == "table":
        return parent_names.get("schema_name") == SCHEMA
    return True


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
        version_table_schema=SCHEMA,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.execute(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"')
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    acquired = connection.execute(
        text("SELECT pg_try_advisory_lock(81183, 1)")
    ).scalar_one()
    connection.commit()
    if not acquired:
        raise RuntimeError(
            "Another Movie Service migration is running. Retry after it finishes."
        )
    try:
        connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
            version_table_schema=SCHEMA,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    finally:
        connection.rollback()
        connection.execute(text("SELECT pg_advisory_unlock(81183, 1)"))
        connection.commit()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    connectable = create_async_engine(
        database_url,
        connect_args=connect_args,
        poolclass=pool.NullPool,
        hide_parameters=True,
    )

    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
