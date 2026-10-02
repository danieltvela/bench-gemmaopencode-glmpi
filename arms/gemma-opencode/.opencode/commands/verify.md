---
description: Build and test the package in the pinned swift:6.1-jammy toolchain
agent: build
---

Verify the package end to end before doing anything else:

1. Build with the `swift` tool: `args: ["build"]`.
2. Test with the `swift` tool: `args: ["test"]` (if the package has a test
   target).
3. Fix every compiler error and re-run until build and tests pass.

Report exactly what passed, or the first unresolved error with its file and
line. Do not claim success without a clean build.

$ARGUMENTS
