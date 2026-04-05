from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Import your Base and models
import sys
from os.path import dirname, abspath
import os
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()

sys.path.append(dirname(dirname(abspath(__file__))))

from backend.database import Base
from backend.models import *  


config = context.config

DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5433')
DB_NAME = os.getenv('DB_NAME', 'ppt_db')

if not DB_PASSWORD:
    raise ValueError("DB_PASSWORD not found in environment variables!")

DATABASE_URL = f"postgresql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

print('Ritu',DATABASE_URL)
DATABASE_URL = DATABASE_URL.replace('%', '%%')
print('Ritu DATABASE_URL',DATABASE_URL)

print("=" * 60)
print("🔍 DEBUG: Tables Alembic can see:")
print(f"   {list(Base.metadata.tables.keys())}")
print("=" * 60)

config.set_main_option('sqlalchemy.url', DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def include_object(object, name, type_, reflected, compare_to):
    """
    Should we include this object in autogenerate?
    Return False to exclude it.
    """
    # Ignore LangGraph checkpoint tables
    if type_ == "table" and name in [
        'checkpoint_migrations',
        'checkpoint_blobs',
        'checkpoint_writes', 
        'checkpoints'
    ]:
        return False
    
    # Ignore indexes on checkpoint tables
    if type_ == "index" and name and any(
        checkpoint_table in name 
        for checkpoint_table in ['checkpoint', 'checkpoints']
    ):
        return False
    
    # Include everything else
    return True

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            include_object=include_object
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()


