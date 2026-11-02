"""Shared test fixtures.

Database tests use a real Postgres, never SQLite, so constraints, partial indexes
and pgvector behave exactly as in production.

- TEST_DATABASE_URL: where to test (default: the docker compose Postgres,
  database `quickai_test`, which is created automatically).
- REQUIRE_DB=1: fail instead of skip when the database is unreachable (set in CI).

The tests drop and recreate every table, so the database name must end in
`_test`; anything else is refused.
"""

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.pool import NullPool

from app.db.urls import create_engine

API_DIR = Path(__file__).resolve().parent.parent
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://quickai:quickai@localhost:5432/quickai_test",
)
REQUIRE_DB = os.environ.get("REQUIRE_DB") == "1"
TABLES = ("creation_likes", "creations", "user_usage")


def is_test_database(url: str) -> bool:
    return (make_url(url).database or "").endswith("_test")


async def request(app, method: str, path: str, **kwargs) -> httpx.Response:
    """Call the app in-process (same event loop as the test)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def alembic_config(url: str = TEST_DATABASE_URL) -> Config:
    config = Config(str(API_DIR / "alembic.ini"))
    config.attributes["database_url"] = url
    return config


async def run_alembic(func, *args) -> None:
    # Alembic's env.py calls asyncio.run(), so run it in its own thread.
    await asyncio.to_thread(func, alembic_config(), *args)


async def _create_test_database() -> None:
    """Create the test database if it doesn't exist yet."""
    url = make_url(TEST_DATABASE_URL)
    admin = create_engine(
        url.set(database="postgres").render_as_string(hide_password=False),
        poolclass=NullPool,
        isolation_level="AUTOCOMMIT",
    )
    try:
        async with admin.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": url.database},
            )
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        await admin.dispose()


@pytest.fixture(scope="session")
async def migrated_db() -> str:
    """A test database with every migration applied. Returns its URL."""
    if not is_test_database(TEST_DATABASE_URL):
        # Never risk dropping a real database because of a copy-pasted URL.
        pytest.fail("TEST_DATABASE_URL must point to a database whose name ends in '_test'")
    try:
        await asyncio.wait_for(_create_test_database(), timeout=10)
    except Exception as exc:
        message = f"Postgres not reachable at TEST_DATABASE_URL ({type(exc).__name__}: {exc})"
        if REQUIRE_DB:
            pytest.fail(message)
        pytest.skip(message + ". Start it with: docker compose up -d db")

    # Start from an empty schema every run, then apply all migrations.
    await run_alembic(command.downgrade, "base")
    await run_alembic(command.upgrade, "head")
    return TEST_DATABASE_URL


@pytest.fixture(scope="session")
async def engine(migrated_db: str) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(migrated_db)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session for one test. All tables are emptied afterwards."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
