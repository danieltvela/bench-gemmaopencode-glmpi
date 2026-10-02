---
description: Boot the built server in the pinned container and check /health
agent: build
---

Smoke-test the service the way an external client will use it:

1. Build first with the `swift` tool: `args: ["build"]`.
2. Start the binary detached in the pinned image, e.g.:

   ```bash
   docker run -d --name shelf-smoke --network host \
     -v "$PWD":/ws -w /ws -e HOME=/tmp -e PORT=18090 \
     swift:6.1-jammy .build/debug/App serve --hostname 0.0.0.0 --port 18090
   ```

3. Wait for the port and request `curl -s http://127.0.0.1:18090/health`.
4. Show the response, then `docker rm -f shelf-smoke`.

Never leave a container running. If boot fails, read
`docker logs shelf-smoke` before removing it.

$ARGUMENTS
