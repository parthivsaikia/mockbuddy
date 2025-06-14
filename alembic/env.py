# alembic/env.py

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Import Base from your database setup
from app.db.database import Base 

# Crucial Step: Import the module(s) where ALL your SQLAlchemy models are defined.
# This ensures they are registered with Base.metadata before target_metadata is set.
# Assuming all your models (User, Interviewer, AvailabilitySlot, ScheduledInterview,
# TestCase, DSAEvaluation, CoreEvaluation, RefreshToken) are in app.models.db_models
from app.models import db_models  # <<<<<<< ENSURE THIS LINE IS PRESENT AND CORRECT

# Set the target_metadata for Alembic's autogenerate support
target_metadata = Base.metadata

# this is the Alembic Config object...
config = context.config

# Interpret the config file for Python logging...
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# other values from the config...
# ... etc.

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    # Ensure sqlalchemy.url is correctly fetched from alembic.ini or config object
    db_url = config.get_main_option("sqlalchemy.url")
    if not db_url:
        from app.config import settings
        db_url = settings.DATABASE_URL
    if not db_url: # Final fallback if using settings object directly
        from app.config import settings
        db_url = settings.DATABASE_URL

    context.configure(
        url=db_url, # Use the resolved URL
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Include type comparison for enums, etc., if needed
        compare_type=True 
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Ensure sqlalchemy.url is correctly configured for engine_from_config
    # The default config.get_section should pick up sqlalchemy.url from alembic.ini
    alembic_config_section = config.get_section(config.config_ini_section, {})
    # If sqlalchemy.url is not in alembic.ini's main section, try to get it from settings
    if 'sqlalchemy.url' not in alembic_config_section:
        from app.config import settings
        alembic_config_section['sqlalchemy.url'] = settings.DATABASE_URL


    connectable = engine_from_config(
        alembic_config_section, # Use the section that contains sqlalchemy.url
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            # Include type comparison for enums, etc.
            compare_type=True 
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()