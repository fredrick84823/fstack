#!/usr/bin/env bash
# Usage: run_wave.sh <case>   — launches both variants detached, prints log paths.
set -euo pipefail
W="$(cd "$(dirname "$0")/.." && pwd)"
CASE="$1"
for V in skill baseline; do
  LOG="$W/runs/.launch-${CASE}-${V}.log"
  nohup "$W/bin/run_case.sh" "$CASE" "$V" > "$LOG" 2>&1 &
  disown
  echo "$V -> $LOG"
done
