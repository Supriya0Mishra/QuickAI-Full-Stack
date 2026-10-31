# QuickAI API (FastAPI)

The new Python backend. It replaces the Node server in `../server` route by route.

## Run locally

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd api
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/health and http://localhost:8000/docs.

## Checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

## Layout

```
app/
  main.py          app factory (create_app)
  core/config.py   settings from environment variables
  core/errors.py   error handlers, same response shape as the Node server
  routes/          API routes
tests/
```
