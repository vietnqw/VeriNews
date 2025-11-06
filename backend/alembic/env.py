"""
Alembic Environment Configuration

Handles database migrations with support for:
- Offline (SQL generation) mode
- Online (direct database) mode
- Integration with application settings and logging
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from app.core.logging import setup_logging
from app.config.settings import settings
from app.models.base import Base


# This is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Setup application logging
setup_logging(
    log_level=settings.LOG_LEVEL,
    log_file=settings.LOG_FILE,
    log_rotation=settings.LOG_ROTATION,
    log_retention=settings.LOG_RETENTION,
    log_compression=settings.LOG_COMPRESSION,
    environment=settings.ENVIRONMENT,
)

# Override sqlalchemy.url from alembic.ini with our settings
config.set_main_option("sqlalchemy.url", settings.POSTGRES_URL_SYNC)

# Add your model's MetaData object here for 'autogenerate' support
# Import all models here so they are registered with Base.metadata
# from app.models.user import User  # Example
target_metadata = Base.metadata

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
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
