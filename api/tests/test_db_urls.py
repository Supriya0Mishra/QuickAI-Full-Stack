from app.db.urls import normalize_database_url


def test_neon_url_is_converted_for_asyncpg():
    url, connect_args = normalize_database_url(
        "postgresql://user:pass@ep-cool-1.neon.tech/neondb?sslmode=require&channel_binding=require"
    )

    assert url == "postgresql+asyncpg://user:pass@ep-cool-1.neon.tech/neondb"
    assert connect_args == {"ssl": "require"}


def test_short_postgres_scheme_is_converted():
    url, connect_args = normalize_database_url("postgres://user:pass@localhost:5432/db")

    assert url == "postgresql+asyncpg://user:pass@localhost:5432/db"
    assert connect_args == {}


def test_asyncpg_url_is_left_alone():
    original = "postgresql+asyncpg://quickai:quickai@db:5432/quickai"

    url, connect_args = normalize_database_url(original)

    assert url == original
    assert connect_args == {}


def test_password_with_special_characters_survives():
    url, _ = normalize_database_url("postgresql://user:p%40ss%2Fword@host/db")

    assert url == "postgresql+asyncpg://user:p%40ss%2Fword@host/db"
