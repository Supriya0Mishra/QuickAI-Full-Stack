from typing import Any

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

_SYNC_POSTGRES_DRIVERS = {"postgres", "postgresql", "postgresql+psycopg2", "postgresql+psycopg"}


def normalize_database_url(url: str) -> tuple[str, dict[str, Any]]:
    """Turn any Postgres URL into one the async driver (asyncpg) accepts.

    Neon gives URLs like `postgresql://...?sslmode=require&channel_binding=require`.
    asyncpg doesn't understand those query options, so this:
    - switches the driver to `postgresql+asyncpg`
    - moves `sslmode` into asyncpg's `ssl` connect argument
    - drops `channel_binding` (asyncpg negotiates it itself)

    Returns the URL and the connect_args to pass to the engine.
    """
    parsed = make_url(url)
    if parsed.drivername in _SYNC_POSTGRES_DRIVERS:
        parsed = parsed.set(drivername="postgresql+asyncpg")

    query = dict(parsed.query)
    connect_args: dict[str, Any] = {}
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    if sslmode:
        connect_args["ssl"] = sslmode

    parsed = parsed.set(query=query)
    return parsed.render_as_string(hide_password=False), connect_args


def create_engine(url: str, **kwargs: Any) -> AsyncEngine:
    normalized, connect_args = normalize_database_url(url)
    return create_async_engine(normalized, connect_args=connect_args, **kwargs)
