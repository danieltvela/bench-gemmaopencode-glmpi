# Hidden acceptance suite (shelf)

External, black-box tests for the Vapor `shelf` service. They only talk HTTP to
a running server; they never import, build, or read the application code.

- **Frozen before the first scored run.** Changes require a new run id.
- **Never seeded into agent workspaces.** Only `task/prompt.md` enters a
  workspace; this directory is copied in at grading time at most.
- Python 3 standard library only (`unittest` + `urllib`): no pip, no network
  dependencies.

## Phases

| Phase | Server environment | Contents |
|---|---|---|
| A | default (`JWT_SECRET` unset, `PORT` from the canonical command) | health, auth, JWT, books, loans, fines, users/stats, errors |
| B | restart on the same SQLite file with custom `PORT` and `JWT_SECRET=bench-restart-secret` | persistence, state across restarts, old tokens rejected, env handling |

Phase A also writes `state.json` (path in `SHELF_STATE`) with the fixtures that
phase B verifies.

## Running manually

```bash
# server must already be listening
SHELF_BASE_URL=http://127.0.0.1:8080 \
SHELF_STATE=/tmp/shelf-state.json \
python3 runner.py --phase A --report /tmp/phase-a.json
```

Or use `task/grade.sh <workspace>`, which orchestrates copy/build/start/phases.

## Layout

- `shelf.py` - HTTP client plus assertion helpers (`expect_error`, date and JWT
  helpers, password-leak checks).
- `data.py` - unique factories (emails, ISBNs, titles) and common flows.
- `state.py` - JSON bridge between phases.
- `runner.py` - selects tests by class attribute `PHASE` and writes the report.
- `test_*.py` - one module per contract area.

## Ambiguity policy

Assertions are strict where `task/prompt.md` fixes status and error code.
Behavior the contract does not specify (duplicate ISBN, malformed UUIDs,
`page`/`per` bounds, precedence between `loan_limit` and `no_copies`, extra
fields) is deliberately not asserted or is accepted tolerantly.
