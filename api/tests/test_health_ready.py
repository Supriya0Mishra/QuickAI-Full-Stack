from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import NullPool

from app.db.session import get_session
from app.db.urls import create_engine
from app.main import create_app
from tests.conftest import request


def app_using_database(url: str):
    """The real app, but with its database sessions pointed at `url`."""
    app = create_app()

    async def override() -> AsyncIterator[AsyncSession]:
        engine = create_engine(url, poolclass=NullPool)
        try:
            async with AsyncSession(engine) as session:
                yield session
        finally:
            await engine.dispose()

    app.dependency_overrides[get_session] = override
    return app


@pytest.mark.db
async def test_ready_when_database_is_reachable(migrated_db):
    response = await request(app_using_database(migrated_db), "GET", "/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_not_ready_when_database_is_down():
    # Port 1 on localhost: nothing listens there, so the connection is refused.
    app = app_using_database("postgresql+asyncpg://user:pass@127.0.0.1:1/missing")

    response = await request(app, "GET", "/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unreachable"}
    assert "pass" not in response.text


async def test_liveness_does_not_need_the_database():
    app = app_using_database("postgresql+asyncpg://user:pass@127.0.0.1:1/missing")

    response = await request(app, "GET", "/health")

    assert response.status_code == 200
