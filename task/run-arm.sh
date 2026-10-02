#!/usr/bin/env bash
# Launch one benchmark arm in an isolated workspace outside the repo and run
# the canonical harness command detached.
#
# Usage: task/run-arm.sh <glm|gemma> [--run-id ID] [--force]
#
#   glm   GLM-5.3-Flash + plain pi
#   gemma Gemma-4 + OpenCode pack
#
# The workspace is $BENCH_WS_ROOT/<run-id>-<arm> (default $HOME/bench). Herdr
# is used when available; otherwise the run is detached with setsid+nohup.
# Nothing is graded here; task/grade.sh does that after BOTH arms have finished.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS_ROOT="${BENCH_WS_ROOT:-$HOME/bench}"
RUN_ID="run1"
ARM=""
FORCE=false

usage() {
  cat >&2 <<'EOF'
usage: task/run-arm.sh <glm|gemma> [--run-id ID] [--force]

env:
  BENCH_WS_ROOT         workspace root (default $HOME/bench)
  BENCH_GLM_BASE_URL    OpenAI-compatible base URL of the control model (required for glm)
  BENCH_GLM_MODEL_ID    provider/model id passed to pi (default local/glm-5.3-flash-local)
  BENCH_GEMMA_BASE_URL  OpenAI-compatible base URL of the treatment model (required for gemma)
EOF
  exit 2
}

[ $# -ge 1 ] || usage
ARM="$1"
shift
case "$ARM" in
  glm|gemma) ;;
  *) usage ;;
esac
while [ $# -gt 0 ]; do
  case "$1" in
    --run-id) [ $# -ge 2 ] || usage; RUN_ID="$2"; shift 2 ;;
    --force) FORCE=true; shift ;;
    *) usage ;;
  esac
done
RUN_ID="${RUN_ID//[^A-Za-z0-9._-]/-}"
WS="$WS_ROOT/$RUN_ID-$ARM"
LABEL="bench-$RUN_ID-$ARM"
BENCH_DIR="$WS/.bench"

# --- model endpoint check ---------------------------------------------------
if [ "$ARM" = glm ]; then
  BASE_URL="${BENCH_GLM_BASE_URL:-}"
  if [ -z "$BASE_URL" ]; then
    echo "set BENCH_GLM_BASE_URL to the control model endpoint (e.g. http://host:port/v1)" >&2
    exit 1
  fi
  MODEL_ID="${BENCH_GLM_MODEL_ID:-local/glm-5.3-flash-local}"
  CHECK_ID="${MODEL_ID##*/}"
else
  BASE_URL="${BENCH_GEMMA_BASE_URL:-}"
  if [ -z "$BASE_URL" ]; then
    echo "set BENCH_GEMMA_BASE_URL to the treatment model endpoint (e.g. http://host:port/v1)" >&2
    exit 1
  fi
  MODEL_ID="bench-gemma/gemma4-31b"
  CHECK_ID="gemma4-31b"
fi
MODELS_URL="${BASE_URL%/}/models"
if ! curl -fsS --max-time 5 "$MODELS_URL" | grep -q "\"$CHECK_ID\""; then
  echo "model server for '$ARM' not ready: $MODELS_URL must list $CHECK_ID" >&2
  exit 1
fi

if [ -e "$WS" ] && [ -n "$(ls -A "$WS" 2>/dev/null)" ]; then
  if [ "$FORCE" != true ]; then
    echo "workspace already exists and is not empty: $WS (use --force to overwrite)" >&2
    exit 1
  fi
  rm -rf "$WS"
fi
mkdir -p "$WS" "$BENCH_DIR"

cp "$ROOT/task/prompt.md" "$WS/prompt.md"
if [ "$ARM" = gemma ]; then
  cp -r "$ROOT/arms/gemma-opencode/." "$WS/"
  # Point the copied project config at the configured endpoint.
  jq --arg url "${BASE_URL%/}" \
    '.provider["bench-gemma"].options.baseURL = $url' \
    "$WS/opencode.json" >"$WS/opencode.json.tmp" \
    && mv "$WS/opencode.json.tmp" "$WS/opencode.json"
fi

# --- run metadata -----------------------------------------------------------
if [ "$ARM" = gemma ]; then
  opencode --version 2>&1 | head -n1 > "$BENCH_DIR/harness_version" || true
else
  pi --version 2>&1 | head -n1 > "$BENCH_DIR/harness_version" || true
fi
"$ROOT/task/suite-hash.sh" > "$BENCH_DIR/suite_sha256"
if [ "$ARM" = gemma ]; then
  (cd "$ROOT" && find arms/gemma-opencode -type f -print0 | sort -z | xargs -0 sha256sum) \
    | sha256sum | cut -d' ' -f1 > "$BENCH_DIR/treatment_sha256"
fi
(cd "$ROOT" && git rev-parse HEAD 2>/dev/null || echo no-git) > "$BENCH_DIR/commit"
date -u +%FT%TZ > "$BENCH_DIR/created_at"

# --- generated runner (canonical commands verbatim) -------------------------
if [ "$ARM" = glm ]; then
  cat > "$BENCH_DIR/run.sh" <<EOF
#!/usr/bin/env bash
set -uo pipefail
cd "$WS"
date -u +%FT%TZ > "$BENCH_DIR/started_at"
pi -p --no-session --no-context-files --no-skills \\
  --model "$MODEL_ID" "\$(cat prompt.md)" 2>&1 | tee "$BENCH_DIR/agent.log"
status=\${PIPESTATUS[0]}
echo "\$status" > "$BENCH_DIR/exit_code"
date -u +%FT%TZ > "$BENCH_DIR/finished_at"
echo "BENCH_DONE exit=\$status"
EOF
else
  cat > "$BENCH_DIR/run.sh" <<EOF
#!/usr/bin/env bash
set -uo pipefail
cd "$ROOT"
date -u +%FT%TZ > "$BENCH_DIR/started_at"
opencode run --dir "$WS" --agent build --auto --model "$MODEL_ID" "\$(cat task/prompt.md)" 2>&1 | tee "$BENCH_DIR/agent.log"
status=\${PIPESTATUS[0]}
echo "\$status" > "$BENCH_DIR/exit_code"
date -u +%FT%TZ > "$BENCH_DIR/finished_at"
echo "BENCH_DONE exit=\$status"
EOF
fi
chmod +x "$BENCH_DIR/run.sh"

# --- launch -----------------------------------------------------------------
MODE="nohup"
if [ "${HERDR_ENV:-}" = "1" ] && herdr status >/dev/null 2>&1; then
  CREATE_JSON="$(herdr workspace create --cwd "$WS" --no-focus --label "$LABEL" 2>/dev/null || true)"
  WORKSPACE_ID="$(printf '%s' "$CREATE_JSON" | jq -r '.result.workspace.workspace_id // .result.workspace.id // empty' 2>/dev/null || true)"
  PANE_ID="$(printf '%s' "$CREATE_JSON" | jq -r '.result.root_pane.pane_id // .result.root_pane.id // empty' 2>/dev/null || true)"
  if [ -n "$WORKSPACE_ID" ] && [ -n "$PANE_ID" ]; then
    printf '%s\n' "$CREATE_JSON" > "$BENCH_DIR/herdr_create.json"
    printf '%s\n' "$WORKSPACE_ID" > "$BENCH_DIR/workspace_id"
    printf '%s\n' "$PANE_ID" > "$BENCH_DIR/pane_id"
    herdr pane rename "$PANE_ID" "$LABEL" >/dev/null 2>&1 || true
    herdr pane run "$PANE_ID" "bash $BENCH_DIR/run.sh" >/dev/null
    MODE="herdr"
  fi
fi
if [ "$MODE" = "nohup" ]; then
  setsid nohup bash "$BENCH_DIR/run.sh" >/dev/null 2>&1 < /dev/null &
  echo "$!" > "$BENCH_DIR/pid"
fi
printf '%s\n' "$MODE" > "$BENCH_DIR/mode"

echo "arm=$ARM run_id=$RUN_ID workspace=$WS mode=$MODE"
if [ "$MODE" = "herdr" ]; then
  echo "follow: herdr pane read $(cat "$BENCH_DIR/pane_id") --source recent-unwrapped --lines 80"
else
  echo "follow: tail -f $BENCH_DIR/agent.log"
fi
