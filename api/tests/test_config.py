import pytest
from pydantic import ValidationError

from app.core.config import Settings
from tests.conftest import is_test_database


def test_invalid_database_url_fails_at_startup():
    # Review fix: a mistyped DATABASE_URL used to surface as a 500 on the first request.
    with pytest.raises(ValidationError, match="DATABASE_URL is not a valid database URL"):
        Settings(database_url="postgresql//missing-colon")


def test_neon_style_database_url_is_accepted():
    settings = Settings(database_url="postgresql://u:p@ep-x.neon.tech/db?sslmode=require")

    assert settings.database_url.startswith("postgresql://")


def test_authorized_parties_default_to_cors_origins():
    settings = Settings(cors_origins="http://a.test, http://b.test", clerk_authorized_parties="")

    assert settings.authorized_party_list == ["http://a.test", "http://b.test"]


@pytest.mark.parametrize(
    ("url", "allowed"),
    [
        ("postgresql+asyncpg://u@localhost/quickai_test", True),
        ("postgresql+asyncpg://u@localhost/quickai", False),
        ("postgresql://u:p@ep-x.neon.tech/neondb", False),
        ("postgresql+asyncpg://u@localhost/test_quickai", False),
    ],
)
def test_tests_only_run_against_a_test_database(url, allowed):
    # Review fix: the test suite drops all tables, so it must never touch a real database.
    assert is_test_database(url) is allowed
