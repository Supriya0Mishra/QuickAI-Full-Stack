# Project rules for coding agents

These rules apply to any coding agent (Claude Code, Cursor, Codex) working in this repo.

## Layout

- `client/` – React + Vite frontend.
- `api/` – FastAPI backend (Python 3.12, uv). **New backend; all new backend work goes here.**
- `server/` – Old Node/Express backend. Being replaced route by route; do not add features here.

## Migration rule

The FastAPI backend must keep the same routes and response shape as `server/`
until the client is switched over:

- Success: `{"success": true, ...}`
- Error: `{"success": false, "message": "..."}` with a real HTTP status code
  (400 validation, 401/403 auth, 404 not found, 413 file too large, 500 unexpected).
- Never send internal error details (stack traces, API errors) to the client.

## Working rules

- Keep each change small and focused on one task. Don't refactor unrelated code.
- Validate all input with Pydantic models; never trust values from the client.
- Add or update tests for every behavior change.
- Before finishing, run the checks below and make sure they pass.
- Never commit secrets. Real values go in `.env` files, which are git-ignored.
- Commit messages: Conventional Commits (`feat:`, `fix:`, `chore:`, `test:`, `docs:`).
  Show the message to the developer before committing.

## Checks

```bash
# API
cd api
uv run ruff check .
uv run ruff format --check .
uv run pytest

# Old server
cd server && npm test

# Client
cd client && npm run build
```
