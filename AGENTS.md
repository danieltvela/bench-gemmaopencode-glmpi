# Working in this repository

This repo is a measurement instrument: it compares two complete agent stacks
(model + harness + instructions) on one Swift/Vapor-on-Linux task. Consistency
beats features. Never "improve" an arm or the task mid-experiment.

## Non-negotiables

- The arms differ in model AND harness by design (A: Gemma-4 + OpenCode with
  instructions; B: GLM-5.3-Flash + plain pi). Do not align them.
- Arm B is the plain control. Its workspace must contain no AGENTS.md, no
  skills, no project config, and the canonical invocation enforces it:
  `pi -p --no-session --no-context-files --no-skills --model <provider>/<model> "$(cat prompt.md)"`.
- The only per-arm instruction file is `arms/gemma-opencode/AGENTS.md` (the
  treatment). `arms/glm-pi/NOTES.md` is documentation for humans; never seed it
  into a workspace.
- This root AGENTS.md never enters an arm workspace. Workspaces live OUTSIDE
  the repo under `$BENCH_WS_ROOT` (default `$HOME/bench`, created by
  `task/run-arm.sh`) with `task/prompt.md` plus arm seed files only.
  `task/hidden_tests/` and `task/reference/` never enter a workspace; the
  external location also keeps them away from the agent tree.
- `task/run-arm.sh <glm|gemma> --run-id <id>` is the only launcher: it
  validates the configured model endpoint, seeds the workspace, records
  versions/hashes, and runs the canonical command detached (Herdr when
  available). Model endpoints come from `BENCH_GLM_BASE_URL` /
  `BENCH_GEMMA_BASE_URL` / `BENCH_GLM_MODEL_ID` (see README); never edit the
  canonical command line the launcher generates. Archive finished workspaces
  to `runs/<runid>-<arm>/` and grade both arms only after both have finished.
- `task/prompt.md` and `task/hidden_tests/` are authored and frozen BEFORE the
  first scored run of a run id, and stay hidden for the whole experiment.
  Write tests from the HTTP contract in `task/prompt.md`, never from a
  finished solution, and grade both arms after both runs have finished.
  Changes require a new run id and re-running the calibration.
- `task/reference/` is the calibration solution: before scoring any arm,
  `task/grade.sh task/reference --run-id ref-calibration --arm reference` must
  report 50/50 (phases A+B). Never score the reference as an arm.
- Every run records: date, run id, arm, model, harness version
  (`opencode --version` / `pi --version`), commit, build result, hidden-test
  result, wall time. `task/grade.sh` writes this to `results/`.

## Environment facts

- Linux only, no Xcode and no host Swift toolchain: the deliverable is a
  SwiftPM package (never `.xcodeproj`) and grading runs `swift build` + the
  server + an EXTERNAL black-box hidden test suite (`task/hidden_tests/`)
  against the HTTP contract, in pinned Docker images (`swift:6.1-jammy`,
  `python:3.12-slim`). Graders never read the workspace code; hidden tests run
  over HTTP in two phases (default env, then restart on the same SQLite file
  with custom `PORT`/`JWT_SECRET`).
- Each arm needs its own locally served OpenAI-compatible model endpoint and
  the two servers usually cannot run at the same time; run the arms
  sequentially. Endpoints and provider ids are configuration, never committed.
- Harness config lives outside the repo: `~/.config/opencode/opencode.json`
  (global) and `~/.pi/agent/models.json` (pi providers). The treatment arm
  overrides provider/model via the project `opencode.json` copied into its
  workspace.

## Canonical commands

Full protocol is in README ("Running an arm"). Short form:

```bash
# Configure endpoints, start the arm's model server (see README), then:
task/run-arm.sh glm   --run-id run1    # GLM-5.3-Flash + plain pi
task/run-arm.sh gemma --run-id run1    # Gemma-4 + OpenCode pack

# Grading (after BOTH arms have run; black-box, two phases)
task/grade.sh runs/<runid>-gemma --run-id <runid> --arm gemma
task/grade.sh runs/<runid>-glm   --run-id <runid> --arm glm
```

Inside the generated `.bench/run.sh` the canonical commands are:

```bash
# Arm A (Gemma + OpenCode, workspace seeded with the arms/gemma-opencode pack)
opencode run --dir "$WS" --agent build --auto --model bench-gemma/gemma4-31b "$(cat task/prompt.md)"

# Arm B (GLM + plain pi, workspace seeded with prompt.md only)
pi -p --no-session --no-context-files --no-skills \
  --model "$BENCH_GLM_MODEL_ID" "$(cat prompt.md)"
```

Docs and commit messages in English.
