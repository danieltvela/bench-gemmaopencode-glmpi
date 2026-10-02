# bench-gemmaopencode-glmpi

A/B benchmark of two complete agent stacks on one task: build a Vapor web service
in Swift on Linux (no Xcode).

Question: can a domain-optimized OpenCode harness (instructions + config) with a
weaker model (Gemma-4) match or beat a stronger coding model (GLM-5.3-Flash) on a
plain pi harness with no project instructions?

## Arms

| | A: harness-optimized | B: plain control |
|---|---|---|
| Model | Gemma-4 31B (locally served) | GLM-5.3-Flash (locally served) |
| Harness | OpenCode 1.18.34 | pi 1.0.0 |
| Instructions | `arms/gemma-opencode/AGENTS.md` + `opencode.json` + skills/commands/tool | none; enforced with `--no-context-files --no-skills --no-session` |
| Task prompt | `task/prompt.md` | `task/prompt.md` (identical) |

The arms differ in model AND harness by design. Do not align them.

## Task and scoring

- Both arms get the same frozen prompt: `task/prompt.md` (Vapor 4 "shelf"
  library lending REST API with a fixed HTTP contract).
- Hidden tests are authored and frozen from that contract BEFORE any scored
  run, never from a finished solution, and stay hidden for the whole
  experiment. Grade both arms after both runs have finished.
- Evaluation is black-box only: the hidden acceptance tests from
  `task/hidden_tests/` run against the SERVER PROCESS over HTTP. The graders
  never look at the code; the tests are copied into a workspace only at
  grading time, never before.
- Primary metric: hidden-test pass rate. Secondary: build success, wall time,
  tokens.
- N repetitions per arm; report mean and spread. Every run records date, run id,
  arm, model, harness version (`opencode --version` / `pi --version`), commit,
  build result, hidden-test result, wall time.

## Layout

```
task/
  prompt.md         frozen task prompt
  hidden_tests/     50 external black-box tests (Python stdlib, phases A+B)
  reference/        calibration solution; NEVER seeded or scored
  grade.sh          docker-pinned grader (build + server + phases + results)
  run-arm.sh        launcher: seed workspace + detached harness run (Herdr)
  suite-hash.sh     canonical hash of prompt.md + hidden test sources
arms/
  gemma-opencode/   treatment seed: AGENTS.md + opencode.json + .opencode pack
  glm-pi/           control arm: intentionally without instructions
runs/               grade workspaces, server logs and test reports (gitignored)
results/            results/<run-id>-<arm>.json + runs.csv
```

Only `task/prompt.md` is ever copied into an arm workspace; `task/hidden_tests/`
and `task/reference/` never are. The root `AGENTS.md` is documentation for
maintaining this benchmark and must never enter an arm workspace either.

## Environment

- Linux only: no Xcode, no macOS, no `.xcodeproj`. Everything is SwiftPM
  (`Package.swift`) plus `swift build` / `swift run`.
- Grading and the deliverable build run in pinned Docker images
  (`swift:6.1-jammy` for build/server, `python:3.12-slim` for the HTTP tests)
  so both arms are graded identically.
- Each arm needs a locally served OpenAI-compatible endpoint for its model.
  Both are usually GPU-heavy and cannot share the machine, so run the arms
  sequentially. Endpoints are NOT committed; configure them with environment
  variables:
  - `BENCH_GLM_BASE_URL` — base URL of the control model, including `/v1`
    (e.g. `http://host:port/v1`).
  - `BENCH_GLM_MODEL_ID` — provider/model id to pass to pi; defaults to
    `local/glm-5.3-flash-local` and must match the provider alias in your local
    pi configuration.
  - `BENCH_GEMMA_BASE_URL` — base URL of the treatment model; the launcher
    patches it into the copied `opencode.json` at seed time.
  - `BENCH_WS_ROOT` — workspace root (default `$HOME/bench`).
- Harness config lives outside the repo: `~/.config/opencode/opencode.json`
  (global) and `~/.pi/agent/models.json` (pi providers).
- Output budget: reasoning turns can exceed a 16k default output cap. Both arms
  are configured with a 65536-token output budget; without it the first turn
  can end on `stopReason: length` and the workspace stays empty.

## Running an arm

Runs are launched with `task/run-arm.sh` into isolated workspaces **outside**
this repo (`$BENCH_WS_ROOT/<runid>-<arm>`, default `~/bench/...`): the agent
tree stays away from `task/hidden_tests/` and `task/reference/`, and from the
root `AGENTS.md`/`opencode.json` that would otherwise leak into the workspace.
Herdr is used when available (`bench-<runid>-<arm>` workspace, no focus steal);
otherwise the run is detached with `setsid`+`nohup`.

Start the arm's model server first, then launch:

```bash
export BENCH_GLM_BASE_URL="http://host:port/v1"
export BENCH_GLM_MODEL_ID="local/glm-5.3-flash-local"
export BENCH_GEMMA_BASE_URL="http://host:port/v1"

# Arm B: GLM-5.3-Flash + plain pi (control model server running)
task/run-arm.sh glm --run-id run1

# Arm A: Gemma-4 + OpenCode pack (after stopping B's server and starting the
# treatment model server; also re-export BENCH_GEMMA_BASE_URL if it changed)
task/run-arm.sh gemma --run-id run1
```

Each run writes `.bench/` in its workspace: `run.sh` (the exact canonical
command), `agent.log`, `started_at`, `finished_at`, `exit_code`,
`harness_version`, `suite_sha256`, `treatment_sha256` (arm A), `commit` and the
Herdr IDs. The run is complete when `finished_at` exists and the log/pane shows
`BENCH_DONE exit=N`; then archive the workspace:

```bash
cp -a "$BENCH_WS_ROOT/run1-glm" runs/run1-glm
```

Monitor a Herdr run with `herdr pane read <pane_id> --source recent-unwrapped
--lines 80` (pane ID in `.bench/pane_id`) or `tail -f .../agent.log`.

Grading (identical for both arms, black-box against the running server; grade
after BOTH runs have finished):

```bash
task/grade.sh runs/<runid>-gemma --run-id <runid> --arm gemma
task/grade.sh runs/<runid>-glm   --run-id <runid> --arm glm
```

`task/grade.sh` copies the workspace to `runs/<run-id>-<arm>.grade/` (no
`.build`, no `*.sqlite*`, no `.git`), builds with `swift:6.1-jammy`, starts the
server, runs phase A, restarts on the same SQLite file with a custom `PORT` and
`JWT_SECRET`, runs phase B, and writes `results/<run-id>-<arm>.json` plus a row
in `results/runs.csv` (pass rate and the hash of the frozen prompt+suite,
reproducible with `task/suite-hash.sh`).
Grading a stub that does not serve must fail (`status=startup_failed`), and
`task/reference/` must always score 50/50 — re-run the calibration before
scoring an arm if the suite changed.

## Results

| date | run id | arm | model | harness | build | hidden tests | wall | notes |
|---|---|---|---|---|---|---|---|---|
| 2026-10-02 | run1 | glm | GLM-5.3-Flash | pi 1.0.0 (plain) | ok | **47/50 (94%)** | 23m00s | B: omitted `returnedOn:null`; 401 on invalid book body |
| 2026-10-02 | run1 | gemma | Gemma-4 31B | OpenCode 1.18.34 + pack | ok | **38/50 (76%)** | 11m46s | A: JWT/auth errors mapped to 500; `/stats` 404; omitted `returnedOn:null` |

Both arms built and booted. Full per-test reports: `results/run1-glm.json`,
`results/run1-gemma.json`. The raw workspaces are archived (locally,
gitignored) under `runs/run1-glm/` and `runs/run1-gemma/`.

Reading of run1: the stronger model on the plain harness wins on correctness
(94% vs 76%), while the harness pack let the weaker model finish faster
(11m46s vs 23m00s). A's losses cluster on error handling: framework/JWT errors
escaping as `internal_error`/500 instead of the contract codes, plus a missing
`/stats` route behaviour. Both arms missed the explicit `returnedOn: null`
encoding that Swift's synthesized Codable omits — the pack's `vapor-service`
skill warns about it, but the treatment model still failed it.

## Status / TODO

- Task spec (Vapor 4 "shelf" REST API) is frozen in `task/prompt.md`.
- Hidden suite (`task/hidden_tests/`, 50 tests incl. restart/persistence) and
  `task/grade.sh` are implemented and frozen; calibration against
  `task/reference/` is green (50/50, see `results/ref-calibration-reference.json`).
- Pinned images: `swift:6.1-jammy`, `python:3.12-slim`.
- Arm A treatment pack is in `arms/gemma-opencode/`: AGENTS.md + opencode.json
  + `.opencode/skills/{swiftpm-linux,vapor-service,fluent-sqlite}` +
  `.opencode/commands/{verify,smoke}` + `.opencode/tools/swift.ts`. Freeze and
  record `treatment_sha256` before launching A.
- Gemma reasoning format verified before run1: the reasoning parser leaves
  `reasoning` empty and delivers text through `content`, so no `interleaved`
  field was needed in the arm model entry.
- Runs so far: `run1` complete (B 47/50, A 38/50; see Results). A first control
  attempt was invalidated by the 16k output cap and was re-run after raising the
  budget to 65536.
- For reference, arm A's treatment hash at run1 time was
  `6802dd39d18cfdd711017b85687a80762d3b2577bf426780a6a9deae9f417a59`. The
  template has since been sanitized for publication, so the hash of the
  current `arms/gemma-opencode/` differs; recompute it before the next run.
