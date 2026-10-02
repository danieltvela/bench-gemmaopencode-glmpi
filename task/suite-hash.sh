#!/usr/bin/env bash
# Hash of the frozen evaluation inputs: task/prompt.md + hidden test sources.
# Recorded in results/runs.csv so any drift after a scored run is detectable.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
find task/prompt.md task/hidden_tests -maxdepth 1 -type f \
  \( -name 'prompt.md' -o -name '*.py' \) -print0 \
  | sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1
