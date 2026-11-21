import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

import app.models  # noqa: F401
from app.db.base import Base
from tests.conftest import run_alembic

pytestmark = pytest.mark.db


async def test_migration_creates_all_tables_and_pgvector(engine):
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
        vector = await conn.scalar(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))

    assert {"creations", "creation_likes", "user_usage", "alembic_version"} <= tables
    assert vector == 1


async def test_models_match_the_migration(engine):
    """If someone changes a model but forgets a migration, this fails."""

    def diff(sync_conn):
        context = MigrationContext.configure(sync_conn, opts={"compare_type": True})
        return compare_metadata(context, Base.metadata)

    async with engine.connect() as conn:
        differences = await conn.run_sync(diff)

    assert differences == []


async def test_migrations_can_be_rolled_back_and_reapplied(engine):
    await run_alembic(command.downgrade, "base")
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
    assert "creations" not in tables

    await run_alembic(command.upgrade, "head")
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
    assert "creations" in tables
