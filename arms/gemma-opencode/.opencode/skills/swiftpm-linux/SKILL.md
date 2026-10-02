---
name: swiftpm-linux
description: Use when creating or editing Package.swift, resolving dependencies, or building and testing a Swift package on Linux. Covers the pinned swift:6.1-jammy Docker toolchain, SwiftPM layout, dependency pins and common build failures.
---

# SwiftPM on Linux

## Toolchain

The host has no Swift installed: run every SwiftPM command inside the pinned
image, with the package directory mounted:

```bash
docker run --rm -v "$PWD":/ws -w /ws -e HOME=/tmp swift:6.1-jammy swift build
docker run --rm -v "$PWD":/ws -w /ws -e HOME=/tmp swift:6.1-jammy swift test
```

The `swift` custom tool wraps exactly these commands; prefer it.

First build downloads dependencies and can take several minutes. Do not
interrupt it and do not use `--disable-sandbox` unless a build error explicitly
requires it.

## Package layout

```
Package.swift
Sources/App/          # Vapor app code, configure/routes/models
Sources/App/entrypoint.swift   # @main, Application.make/execute
Tests/AppTests/       # optional local tests
```

- `// swift-tools-version:5.9` (the compiler runs in Swift 5 language mode; do
  not opt into tools-version 6 or strict concurrency).
- Keep `Package.resolved` in the repo once resolved so builds are reproducible.
- Name the executable target `App`; the grader starts `.build/debug/App`.
- No `.xcodeproj`/`.xcworkspace` on Linux.

## Dependencies

```swift
.package(url: "https://github.com/vapor/vapor.git", from: "4.92.0"),
.package(url: "https://github.com/vapor/fluent.git", from: "4.9.0"),
.package(url: "https://github.com/vapor/fluent-sqlite-driver.git", from: "4.6.0"),
.package(url: "https://github.com/vapor/jwt.git", from: "4.0.0"),
```

Products: `Vapor`, `Fluent`, `FluentSQLiteDriver`, `JWT`.

## Build hygiene

- Fix every compiler error before moving on; warnings are acceptable but read
  them (deprecated APIs often mean a newer idiom exists).
- `swift package describe --type json` lists products/targets when a name is
  unclear.
- After a failed build, read the first error: later ones are usually cascades.
