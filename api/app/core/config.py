from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    """App settings, read from environment variables or api/.env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "QuickAI API"
    environment: str = "development"
    # Comma-separated list, e.g. "http://localhost:5173,https://app.example.com"
    cors_origins: str = "http://localhost:5173"
    # Default matches docker-compose.yml. Neon URLs can be pasted as-is.
    database_url: str = "postgresql+asyncpg://quickai:quickai@localhost:5432/quickai"

    # Clerk (sign-in). Same publishable key as the client (pk_test_... / pk_live_...).
    # The API derives Clerk's issuer and public-key URL from it.
    clerk_publishable_key: str = ""
    # Optional: Clerk's PEM public key (Dashboard -> API Keys -> JWT public key).
    # If set, tokens are verified without calling Clerk at all.
    clerk_jwt_key: str = ""
    # Which frontends may use tokens (the token's `azp` claim).
    # Comma-separated; defaults to cors_origins.
    clerk_authorized_parties: str = ""

    @field_validator("database_url")
    @classmethod
    def _check_database_url(cls, value: str) -> str:
        # Fail at startup with a clear message instead of on the first request.
        try:
            make_url(value)
        except ArgumentError:
            raise ValueError("DATABASE_URL is not a valid database URL") from None
        return value

    @field_validator("clerk_jwt_key")
    @classmethod
    def _unescape_pem(cls, value: str) -> str:
        # Hosting dashboards and Docker env files often store the PEM on one line
        # with literal "\n"; turn those back into real newlines.
        return value.strip().strip('"').replace("\\n", "\n")

    @property
    def cors_origin_list(self) -> list[str]:
        return _split(self.cors_origins)

    @property
    def authorized_party_list(self) -> list[str]:
        return _split(self.clerk_authorized_parties) or self.cors_origin_list


@lru_cache
def get_settings() -> Settings:
    return Settings()
