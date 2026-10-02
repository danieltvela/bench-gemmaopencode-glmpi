# shelf (reference solution)

Calibration-only implementation of the `task/prompt.md` contract. It is NOT an
arm and must never be seeded into an agent workspace.

```bash
swift run App serve --hostname 0.0.0.0 --port "${PORT:-8080}"
swift build
```

Environment:

- `PORT` (default 8080), host `0.0.0.0`.
- `JWT_SECRET` (default `shelf-dev-secret`), HS256, 3600 s tokens.
- SQLite file `./shelf.sqlite`, migrations run on startup, admin seeded when
  the users table is empty (`admin@shelf.test` / `admin-pass`).
- `X-Test-Date: YYYY-MM-DD` overrides "today" for due dates and fines.

Validate the hidden suite against it:

```bash
task/grade.sh task/reference --run-id ref-calibration --arm reference
```
