#!/usr/bin/env bash
# Black-box grader for the shelf benchmark (Linux + Docker only).
#
# Usage: task/grade.sh <workspace> [--run-id ID] [--arm NAME]
#
# Grades a finished agent workspace:
#   1. clean copy (no .build, no *.sqlite*, no .git)
#   2. swift build in $SWIFT_IMAGE
#   3. start server, run phase A hidden tests over HTTP
#   4. restart on the same SQLite file with custom PORT/JWT_SECRET, run phase B
#   5. write results/<run-id>-<arm>.json and append results/runs.csv
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HIDDEN="$ROOT/task/hidden_tests"
SWIFT_IMAGE="${SWIFT_IMAGE:-swift:6.1-jammy}"
PYTHON_IMAGE="${PYTHON_IMAGE:-python:3.12-slim}"
PORT_A="${PORT_A:-18080}"
PORT_B="${PORT_B:-18081}"
RESTART_SECRET="${RESTART_SECRET:-bench-restart-secret}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-180}"
RESULTS_DIR="$ROOT/results"

usage() {
  cat >&2 <<'EOF'
usage: task/grade.sh <workspace> [--run-id ID] [--arm NAME]

env: SWIFT_IMAGE, PYTHON_IMAGE, PORT_A, PORT_B, RESTART_SECRET, HEALTH_TIMEOUT
EOF
  exit 2
}

[ $# -ge 1 ] || usage
WS="$1"
shift
RUN_ID=""
ARM=""
while [ $# -gt 0 ]; do
  case "$1" in
    --run-id) [ $# -ge 2 ] || usage; RUN_ID="$2"; shift 2 ;;
    --arm) [ $# -ge 2 ] || usage; ARM="$2"; shift 2 ;;
    *) usage ;;
  esac
done
[ -d "$WS" ] || { echo "workspace not found: $WS" >&2; exit 2; }
WS="$(cd "$WS" && pwd)"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
ARM="${ARM:-$(basename "$WS")}"
RUN_ID="${RUN_ID//[^A-Za-z0-9._-]/-}"
ARM="${ARM//[^A-Za-z0-9._-]/-}"
GRADE_DIR="$ROOT/runs/${RUN_ID}-${ARM}.grade"
LOG_DIR="$GRADE_DIR/.grade-logs"
CNAME="shelf-grade-$$"
DOCKER_USER="$(id -u):$(id -g)"
START_TS="$(date -u +%FT%TZ)"
EXE=""
BUILD_OK=false

cleanup() { docker rm -f "$CNAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

mkdir -p "$RESULTS_DIR"

SUITE_SHA256="$("$ROOT/task/suite-hash.sh")"

write_stub() { # phase note
  local phase="$1" note="$2" lower
  lower="$(printf '%s' "$phase" | tr 'A-Z' 'a-z')"
  printf '{"phase":"%s","base_url":"","total":0,"passed":0,"failed":0,"errors":0,"skipped":0,"duration_s":0,"cases":[],"note":"%s"}' \
    "$phase" "$note" >"$LOG_DIR/phase_$lower.json"
}

finalize() { # status
  local status="$1" pa="$LOG_DIR/phase_a.json" pb="$LOG_DIR/phase_b.json"
  local total passed failed errors pass_rate pa_p pa_t pb_p pb_t
  total="$(jq -s '[.[].total] | add' "$pa" "$pb")"
  passed="$(jq -s '[.[].passed] | add' "$pa" "$pb")"
  failed="$(jq -s '[.[].failed] | add' "$pa" "$pb")"
  errors="$(jq -s '[.[].errors] | add' "$pa" "$pb")"
  pass_rate="$(awk -v p="$passed" -v t="$total" 'BEGIN { if (t == 0) print 0; else printf "%.4f", p / t }')"
  jq -n \
    --arg run_id "$RUN_ID" --arg arm "$ARM" --arg date "$START_TS" \
    --arg swift_image "$SWIFT_IMAGE" --arg python_image "$PYTHON_IMAGE" \
    --arg suite_sha256 "$SUITE_SHA256" --arg exe "$EXE" --arg status "$status" \
    --argjson build_ok "$([ "$BUILD_OK" = true ] && echo true || echo false)" \
    --slurpfile phase_a "$pa" --slurpfile phase_b "$pb" \
    --argjson total "$total" --argjson passed "$passed" --argjson failed "$failed" \
    --argjson errors "$errors" --argjson pass_rate "$pass_rate" \
    '{run_id: $run_id, arm: $arm, date: $date, status: $status,
      swift_image: $swift_image, python_image: $python_image,
      suite_sha256: $suite_sha256, executable: $exe, build_ok: $build_ok,
      phase_a: $phase_a[0], phase_b: $phase_b[0],
      total: $total, passed: $passed, failed: $failed, errors: $errors,
      pass_rate: $pass_rate}' >"$RESULTS_DIR/$RUN_ID-$ARM.json"

  if [ ! -f "$RESULTS_DIR/runs.csv" ]; then
    echo "date,run_id,arm,status,build,exe,phase_a_passed,phase_a_total,phase_b_passed,phase_b_total,passed,total,pass_rate,suite_sha256" >"$RESULTS_DIR/runs.csv"
  fi
  pa_p="$(jq -r '.passed' "$pa")"; pa_t="$(jq -r '.total' "$pa")"
  pb_p="$(jq -r '.passed' "$pb")"; pb_t="$(jq -r '.total' "$pb")"
  echo "$START_TS,$RUN_ID,$ARM,$status,$BUILD_OK,${EXE:-none},$pa_p,$pa_t,$pb_p,$pb_t,$passed,$total,$pass_rate,$SUITE_SHA256" >>"$RESULTS_DIR/runs.csv"

  echo
  echo "== grade $RUN_ID / $ARM: status=$status pass=$passed/$total (rate $pass_rate) build=$BUILD_OK exe=${EXE:-none}"
  jq -r '.phase_a | "   phase A: \(.passed)/\(.total) passed, \(.failed) failed, \(.errors) errors\(if .note then " (" + .note + ")" else "" end)"' "$RESULTS_DIR/$RUN_ID-$ARM.json"
  jq -r '.phase_b | "   phase B: \(.passed)/\(.total) passed, \(.failed) failed, \(.errors) errors\(if .note then " (" + .note + ")" else "" end)"' "$RESULTS_DIR/$RUN_ID-$ARM.json"
  echo "   report: $RESULTS_DIR/$RUN_ID-$ARM.json"
  [ "$status" = "pass" ]
}

start_server() { # port secret mode(flag|env)
  local port="$1" secret="$2" mode="$3" cmd
  local args=(run -d --name "$CNAME" --network host --user "$DOCKER_USER" -e HOME=/tmp -v "$GRADE_DIR":/ws -w /ws -e PORT="$port")
  if [ -n "$secret" ]; then args+=(-e JWT_SECRET="$secret"); fi
  if [ "$mode" = "env" ]; then
    cmd="exec .build/debug/$EXE serve --hostname 0.0.0.0"
  else
    cmd="exec .build/debug/$EXE serve --hostname 0.0.0.0 --port $port"
  fi
  docker "${args[@]}" "$SWIFT_IMAGE" sh -lc "$cmd" >"$LOG_DIR/server-$mode-$port.cid" 2>&1
}

wait_health() {
  local port="$1" deadline=$((SECONDS + HEALTH_TIMEOUT))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if curl -fsS --max-time 5 "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
      return 0
    fi
    if ! docker ps --format '{{.Names}}' | grep -qx "$CNAME"; then
      return 1
    fi
    sleep 2
  done
  return 1
}

run_phase() { # phase port
  local phase="$1" port="$2" lower
  lower="$(printf '%s' "$phase" | tr 'A-Z' 'a-z')"
  docker run --rm --network host --user "$DOCKER_USER" -e HOME=/tmp \
    -v "$HIDDEN":/tests:ro -v "$LOG_DIR":/out \
    -e SHELF_BASE_URL="http://127.0.0.1:$port" \
    -e SHELF_STATE=/out/state.json \
    "$PYTHON_IMAGE" python3 /tests/runner.py \
    --phase "$phase" --report "/out/phase_$lower.json" \
    >"$LOG_DIR/phase_$lower.log" 2>&1 || true
  [ -s "$LOG_DIR/phase_$lower.json" ]
}

# --- clean copy -------------------------------------------------------------
rm -rf "$GRADE_DIR"
mkdir -p "$GRADE_DIR"
if command -v rsync >/dev/null 2>&1; then
  rsync -a --exclude '.build/' --exclude '*.sqlite' --exclude '*.sqlite-*' \
    --exclude '.git/' --exclude '.grade-logs/' "$WS"/ "$GRADE_DIR"/
else
  cp -a "$WS"/. "$GRADE_DIR"/
  rm -rf "$GRADE_DIR/.build" "$GRADE_DIR/.git" "$GRADE_DIR/.grade-logs"
  find "$GRADE_DIR" -maxdepth 1 -name 'shelf.sqlite*' -delete
fi
mkdir -p "$LOG_DIR"

# --- build ------------------------------------------------------------------
if docker run --rm --user "$DOCKER_USER" -e HOME=/tmp -v "$GRADE_DIR":/ws -w /ws "$SWIFT_IMAGE" swift build \
  >"$LOG_DIR/build.log" 2>&1; then
  BUILD_OK=true
fi

write_stub A not_run
write_stub B not_run

if [ "$BUILD_OK" != true ]; then
  echo "build failed; see $LOG_DIR/build.log" >&2
  finalize build_failed || true
  exit 1
fi

# --- discover executable product -------------------------------------------
if docker run --rm --user "$DOCKER_USER" -e HOME=/tmp -v "$GRADE_DIR":/ws -w /ws "$SWIFT_IMAGE" \
  swift package describe --type json >"$LOG_DIR/describe.json" 2>"$LOG_DIR/describe.err"; then
  EXE="$(jq -r '(.products // [])[] | select(.type | has("executable")) | .name' \
    "$LOG_DIR/describe.json" 2>/dev/null | head -n1 || true)"
fi
if [ -z "$EXE" ] && [ -x "$GRADE_DIR/.build/debug/App" ]; then
  EXE="App"
fi
if [ -z "$EXE" ]; then
  echo "no executable product found" >&2
  rm -f "$LOG_DIR/phase_a.json"
  write_stub A no_executable
  finalize no_executable || true
  exit 1
fi

# --- phase A ----------------------------------------------------------------
start_server "$PORT_A" "" flag
if wait_health "$PORT_A"; then
  run_phase A "$PORT_A" || { rm -f "$LOG_DIR/phase_a.json"; write_stub A runner_failed; }
else
  docker logs "$CNAME" >"$LOG_DIR/server-a.log" 2>&1 || true
  rm -f "$LOG_DIR/phase_a.json"
  write_stub A startup_failed
fi
docker rm -f "$CNAME" >/dev/null 2>&1 || true

# --- phase B (restart with custom PORT and JWT_SECRET) ----------------------
a_total="$(jq -r '.total' "$LOG_DIR/phase_a.json")"
if [ "$a_total" -gt 0 ]; then
  start_server "$PORT_B" "$RESTART_SECRET" env
  if wait_health "$PORT_B"; then
    run_phase B "$PORT_B" || { rm -f "$LOG_DIR/phase_b.json"; write_stub B runner_failed; }
  else
    docker logs "$CNAME" >"$LOG_DIR/server-b.log" 2>&1 || true
    rm -f "$LOG_DIR/phase_b.json"
    write_stub B startup_failed
  fi
  docker rm -f "$CNAME" >/dev/null 2>&1 || true
fi

# --- results ----------------------------------------------------------------
rm -rf "$GRADE_DIR/.build" "$GRADE_DIR/.swiftpm" 2>/dev/null || true

b_total="$(jq -r '.total' "$LOG_DIR/phase_b.json")"
problems="$(jq -s '[.[].failed + .[].errors] | add' "$LOG_DIR/phase_a.json" "$LOG_DIR/phase_b.json")"
if [ "$problems" -eq 0 ] && [ "$a_total" -gt 0 ] && [ "$b_total" -gt 0 ]; then
  finalize pass
else
  finalize fail || true
  exit 1
fi
