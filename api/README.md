# QuickAI API (FastAPI)

The new Python backend. It replaces the Node server in `../server` route by route.

## Run with Docker (API + Postgres)

Requires Docker Desktop. From the repo root:

```bash
docker compose up --build
```

- API: http://localhost:8000/health and http://localhost:8000/docs
- Postgres 17 with pgvector: `localhost:5432`, user/password/database `quickai`
  (local development only)

Stop with `Ctrl+C`. To also delete the local database: `docker compose down --volumes`.

If port 5432 or 8000 is already in use, set `DB_PORT` or `API_PORT`, e.g.
`DB_PORT=5433 docker compose up`.

## Run without Docker

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd api
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/health and http://localhost:8000/docs.

## Database

`DATABASE_URL` sets the database (default: the docker compose Postgres). A Neon
URL can be pasted as-is; `?sslmode=require` is handled automatically.

```bash
uv run alembic upgrade head                        # apply migrations
uv run alembic revision --autogenerate -m "add x"  # new migration after changing models
uv run alembic check                               # fails if models and migrations differ
```

Tables:

| Table | Purpose |
|---|---|
| `creations` | Generated content (article, blog titles, image, resume review) |
| `creation_likes` | One row per like; replaces the old `likes TEXT[]` column |
| `user_usage` | Free-plan usage per user; replaces the counter in Clerk metadata |

`GET /health` checks the process is up. `GET /health/ready` also checks the database.

### Moving data from the old Node server's database

The new API uses its own database during the migration (the old server's
`creations` table has a different shape). When switching over, copy the data:

```bash
uv run alembic upgrade head
uv run python -m app.scripts.import_legacy --source "<old DATABASE_URL>" --dry-run
uv run python -m app.scripts.import_legacy --source "<old DATABASE_URL>"
```

It keeps IDs, turns each `likes` array into rows, skips unknown types, and is
safe to run more than once.

## Sign-in (Clerk)

The React app sends `Authorization: Bearer <token>` (from Clerk's `getToken()`).
The API verifies the token itself; no Clerk secret key is needed.

| Variable | Required | Value |
|---|---|---|
| `CLERK_PUBLISHABLE_KEY` | yes | Same `pk_test_...` key as the client. The API derives Clerk's issuer and public-key URL from it. |
| `CLERK_JWT_KEY` | no | Clerk Dashboard → API Keys → JWT public key (PEM). If set, tokens are verified without calling Clerk. |
| `CLERK_AUTHORIZED_PARTIES` | no | Allowed frontend URLs, comma-separated. Defaults to `CORS_ORIGINS`. |

Put them in `api/.env` (git-ignored; docker compose loads it too).

What is checked: RS256 signature with Clerk's public keys (cached, refreshed on key
rotation), expiry, issuer, and the frontend (`azp`). Tokens with any other algorithm
are rejected. If Clerk can't be reached, previously fetched keys keep working;
with no keys at all the API returns 503.

Protected routes use the `get_current_user` dependency:

```python
from app.core.auth import CurrentUser, get_current_user


@router.get("/something")
async def something(
    user: Annotated[CurrentUser, Depends(get_current_user)],
): ...  # user.user_id, user.plan, user.is_premium
```

The premium plan comes from Clerk Billing's `pla` claim (`"u:premium"`).
`GET /api/user/me` returns the signed-in user and plan, useful for checking setup.

## Checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Database tests need Postgres. Start it with `docker compose up -d db` (from the
repo root); they create and use a separate `quickai_test` database. Without
Postgres they are skipped locally. In CI they are required (`REQUIRE_DB=1`).

## Layout

```
app/
  main.py               app factory (create_app)
  core/config.py        settings from environment variables
  core/auth.py          Clerk token verification, get_current_user
  core/errors.py        error handlers, same response shape as the Node server
  db/                   engine, sessions, URL handling (Neon-compatible)
  models/               SQLAlchemy models
  routes/               API routes
  scripts/              one-off scripts (legacy data import)
migrations/             Alembic migrations
tests/
```
