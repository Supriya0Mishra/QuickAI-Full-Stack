# Build log

How this project is built with coding agents: one entry per PR. For each entry,
note what the agent was asked to do, what it got wrong or what I changed in review,
and how the change was checked.

---

## Phase 0, PR 1: FastAPI skeleton, tooling and CI

**Task:** Start the FastAPI backend next to the Node server, with linting, tests and CI.

**Review notes:**
- The agent first tried to switch the test HTTP client to a package called `httpx2`
  to silence a deprecation warning. The install was blocked as an unfamiliar
  package name that could be a lookalike of `httpx`. Kept `httpx` and filtered the
  warning instead.
- Client lint has 5 existing errors (unused imports), so CI runs the client build
  only for now. Lint is added in PR 9.
- Validation errors return 400 (not FastAPI's default 422) so the existing React
  client keeps working.

**Checked by:** ruff, 5 pytest tests, CI on the PR.

<!-- Add your own notes from reviewing this PR here. -->

**Lesson:** PR #2 was merged before CI finished. CI passed afterwards, but from
now on I wait for green checks (and require them with a branch rule on `main`).

---

## Phase 0, PR 2: Docker Compose with Postgres + pgvector

**Task:** One command to run the API and a local Postgres that is ready for RAG later.

**Decisions:**
- `pgvector/pgvector:pg17` instead of plain Postgres, so Phase 1 (embeddings) needs
  no infrastructure change. Postgres 17 matches what Neon uses.
- The API image installs only production dependencies (`uv sync --no-dev`), pins
  the uv version, runs as a non-root user and has a healthcheck.
- The API waits for the database healthcheck before starting (`depends_on: service_healthy`).
- The pgvector extension is not created yet; that happens in the first Alembic
  migration (PR 3), so it also works on Neon.

**Checked by:** `docker compose up --wait`, `/health`, `CREATE EXTENSION vector`
in the container, and a new Docker job in CI that does the same.

<!-- Add your own notes from reviewing this PR here. -->

---

## Phase 0, PR 3: Database layer (SQLAlchemy + Alembic)

**Task:** Models, the first migration, a readiness check and a script to copy old data.

**Decisions:**
- **Likes as a table, not an array.** `creation_likes` has a primary key on
  `(creation_id, user_id)`, so one user can't like twice, and `ON DELETE CASCADE`
  removes likes with their creation. The old `TEXT[]` allowed duplicates and needed
  read-modify-write in the app.
- **Usage counter in Postgres** (`user_usage`), not Clerk metadata, so PR 5 can
  check and increase it in one atomic `UPDATE`.
- **Constraints in the database**, not only in code: allowed `type` values,
  `free_usage >= 0`. Bad data is rejected even if a bug skips validation.
- **Partial index** on published creations for the community feed.
- **Separate database during the migration.** The old Node server and the new API
  can't share a `creations` table (different shape), so the API gets its own
  database and `app/scripts/import_legacy.py` copies data at switch-over. It keeps
  IDs, splits likes into rows, skips unknown types, resets the id sequence, and is
  safe to run twice.
- **Neon URLs work as-is.** asyncpg doesn't accept `?sslmode=require`, so
  `app/db/urls.py` converts it.
- **Two health checks.** `/health` (liveness) never touches the database, so a slow
  database doesn't make Docker restart a healthy API. `/health/ready` checks it.
- The migration was written by hand; a test and `alembic check` in CI fail if the
  models and migrations ever drift apart.

**Review notes:**
- First version of the partial-index test ran the EXPLAIN query twice by mistake;
  removed the duplicate.
- The Docker image didn't include the migrations, so `docker compose up` would have
  started with no tables. Added them to the image; compose now runs
  `alembic upgrade head` before starting the API.

**Checked by:**
- All 27 tests pass against a real Postgres (16.2 + pgvector 0.6.2, a portable
  install because Docker Desktop wasn't reachable locally; CI uses 17), with
  `REQUIRE_DB=1` so no database test could skip.
- **The tests can fail:** changing a column type without a migration failed the
  drift test (`modify_type`), and removing the id-sequence reset in the import
  script failed with `duplicate key ... pk_creations`. Both pass again after restoring.
- Command line: `alembic upgrade head`, `current`, `check` ("No new upgrade
  operations detected"), downgrade and re-upgrade, using a plain `postgresql://` URL.
- Import CLI on an old-schema database: dry run, real run (3 creations, 3 likes),
  second run inserts 0, and a clear error without `--source`.
- Real server: `/health/ready` returns 200 with the database up and 503 when it's
  down, while `/health` stays 200; the error is logged on the server only.
- Not yet run: the Docker Compose stack itself (CI's Docker job covers it).

<!-- Add your own notes from reviewing this PR here. -->

---

## Phase 0, PR 4: Clerk sign-in in FastAPI

**Task:** Verify Clerk session tokens in the API and expose the signed-in user to routes.

**Decisions:**
- **Verify tokens locally** with PyJWT and Clerk's public keys (JWKS) instead of
  calling Clerk on every request: faster, and no Clerk secret key on the API.
- **Only RS256.** The algorithm is checked before any key is used, so `alg: none`
  and "HS256 signed with the public key" (algorithm confusion) tokens are rejected.
- **Checked claims:** expiry and not-before (5 s leeway for clock skew), issuer
  (our Clerk instance only), `sub` required, and `azp` must be one of our frontends.
- **Issuer derived from the publishable key** (it is base64 of the Clerk domain),
  so the only required setting is the same `pk_test_...` the client uses.
- **Key cache:** keys are fetched once and reused for an hour. A token with an
  unknown key id triggers a refetch (Clerk rotated keys), but at most once per 30 s,
  so junk tokens can't make the API hammer Clerk. If Clerk is down, cached keys
  keep working; with no keys the API answers 503, not 500.
- **Optional networkless mode:** `CLERK_JWT_KEY` (PEM) verifies with no network calls.
- Plan from Clerk Billing's `pla` claim (`u:premium`); org plans don't count as
  user premium.

**Review notes:**
- `httpx` moved from a test-only dependency to a main one (needed to fetch keys).
- To check: the `pla` claim format against a real Clerk token once the app runs
  with real keys (tests use the documented `u:<plan>` format).

**Checked by:**
- 30 auth tests with real RSA keys and a fake Clerk key server: valid, premium,
  missing, garbage, expired, not-yet-valid, wrong issuer, wrong frontend, no user,
  attacker-signed, `alg: none`, HS256 confusion, caching, rotation, junk key ids,
  Clerk outage (with and without cached keys), missing configuration.
- **Sabotage:** removing the issuer check, the azp check, the algorithm check, the
  refetch limit and the outage fallback each made exactly the matching test fail.
- Full suite: 57 tests pass against a real Postgres (`REQUIRE_DB=1`).
- Real server (uvicorn): valid token 200 with plan, no token 401, forged token 401,
  CORS preflight allows the `Authorization` header from the React app.

<!-- Add your own notes from reviewing this PR here. -->

---

## Code review before opening the PR (PR 2–4)

A structured review of the whole branch found 9 issues. All fixed, each with a
regression test:

| # | Issue | Fix |
|---|---|---|
| 1 | `sh -c "... && uvicorn"` left `sh` as PID 1, so `docker compose stop` couldn't stop uvicorn cleanly (10 s wait, then kill) | `exec uvicorn` |
| 2 | During a Clerk outage, every request retried the key fetch, one at a time, each waiting for the 5 s timeout | Fetch attempts (failed ones too) limited to one per 30 s; cached keys used meanwhile |
| 3 | The test suite drops all tables of whatever `TEST_DATABASE_URL` points to | Refuses to run unless the database name ends in `_test` |
| 4 | `CLERK_JWT_KEY` pasted on one line with `\n` (Docker/Coolify style) broke every sign-in | `\n` turned back into newlines when loading settings |
| 5 | One malformed key in Clerk's key list caused a 500 for everyone | Bad keys skipped individually. The first fix caught the wrong exception type; the new test caught that. |
| 6 | Publishable-key parser didn't check the `pk_` prefix | Requires `pk_test_` / `pk_live_` |
| 7 | Missing Clerk config logged an error on every request | Logged once |
| 8 | Invalid `DATABASE_URL` showed up as a 500 on the first request | Rejected at startup with a clear message |
| 9 | Two copies of the in-process HTTP test helper | One `request()` helper in `conftest.py` |

Writing test #5 also exposed a 10th bug: a JWKS response of `{"keys": null}`
crashed with a 500. It is now treated as an outage (503).

**Checked by:** 72 tests pass against a real Postgres (`REQUIRE_DB=1`); sabotaging
the outage fix fails its two new tests; the `_test` guard refuses `quickai`.
