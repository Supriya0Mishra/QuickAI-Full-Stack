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
