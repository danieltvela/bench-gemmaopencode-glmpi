# Swift / Vapor on Linux (harness pack)

You develop and maintain a Vapor web service in Swift on Linux. There is no
Xcode, no macOS, and no simulator: the deliverable is a SwiftPM package.

## Harness assets (use them)

- Skills: `swiftpm-linux` (toolchain, package layout, builds),
  `vapor-service` (entrypoint, routes, DTOs, errors, JWT) and
  `fluent-sqlite` (models, migrations, queries). Load the relevant one before
  writing that kind of code.
- Tool `swift`: runs any SwiftPM command in the pinned `swift:6.1-jammy` image
  with the current directory mounted at `/ws`. Prefer it over ad-hoc docker.
- Commands: `/verify` (build + test) and `/smoke` (boot the server and check
  `/health` over HTTP). Run `/verify` before declaring any step finished.

## Layout and tooling

- Single SwiftPM package: `Package.swift` at the root, executable target that
  boots Vapor (conventionally `Sources/App` for app code + `Sources/Run` or an
  `@main` entrypoint) and a test target under `Tests/`.
- Never create `.xcodeproj` or `.xcworkspace`. All builds and tests go through
  SwiftPM, via the `swift` tool or the pinned image:
  `docker run --rm -v "$PWD":/ws -w /ws -e HOME=/tmp swift:6.1-jammy swift test`
  (this is the toolchain the grader uses; do not use `latest`).
- Select the Vapor version in `Package.swift`; do not depend on unreleased
  branches. Commit `Package.resolved` so builds are reproducible.

## Vapor conventions

- Bootstrap: `var env = try Environment.detect()`, `try
  LoggingSystem.bootstrap(from: &env)`, `let app = try await
  Application.make(env)`, then `try await configure(app)`, `try await
  app.execute()`, `try await app.asyncShutdown()`.
- Register routes in `routes(_ app: Application)` (`routes.swift`), grouped
  under versioned path collections when sensible.
- Request/response bodies and query params: Codable structs conforming to
  `Content`. No dictionaries as payloads.
- Errors: `throw Abort(.status, reason: ...)`. Bad input maps to 4xx, not 500.
- async/await everywhere; avoid completion handlers and
  EventLoopFuture in new code.
- Configure from environment variables (host, port, etc.), not hardcoded
  values. Bind with `app.http.server.configuration.hostname/port` or
  `--hostname/--port`.
- Log through `app.logger`; never `print`.
- Ship a short README in the package root with exact build/run/test commands.

## Quality bar (verify before finishing)

- `swift build` completes with no errors; mention any warnings.
- `swift test` passes. Use Vapor's test helpers (`app.testable(...)` with
  VaporTesting or XCTVapor) to exercise routes through the app, not by
  starting a real network server.
- The server actually boots: run `/smoke` (or start the binary and request
  `/health`) before declaring the task done.
- No force unwraps (`!`) or `try!` outside tests; no stubbed/fake
  implementations of required functionality.
