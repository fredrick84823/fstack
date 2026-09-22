#!/usr/bin/env bash
# Usage: run_case.sh <case> <skill|baseline>
# Launch it detached (nohup/disown) — a long run outlives the caller's shell.
# Runs one eval variant against a private copy of the case fixture.
set -euo pipefail

W="$(cd "$(dirname "$0")/.." && pwd)"
CASE="$1"; VARIANT="$2"
FIXTURE="$W/fixtures/$(cat "$W/cases/$CASE/fixture")"
RUN="$W/runs/${CASE}-${VARIANT}-$(date +%Y%m%d-%H%M%S)"
REPO="$RUN/repo"

mkdir -p "$RUN"
cp -R "$FIXTURE" "$REPO"

PROMPT="$(cat "$W/cases/$CASE/prompt.txt")"
if [ "$VARIANT" = "baseline" ]; then
  PROMPT="${PROMPT#/closed-loop }"
fi
printf '%s' "$PROMPT" > "$RUN/prompt.txt"

if [ ! -d "$REPO/.git" ]; then
  git -C "$REPO" init -q
  git -C "$REPO" add -A
  git -C "$REPO" -c user.name=fixture -c user.email=fixture@example.com \
    commit -q -m "fixture baseline"
fi

BASE_SHA="$(git -C "$REPO" rev-parse HEAD)"
echo "$BASE_SHA" > "$RUN/base-sha.txt"

START=$(python3 -c 'import time;print(int(time.time()*1000))')
set +e
( cd "$REPO" && claude -p "$PROMPT" \
    --output-format stream-json --verbose --forward-subagent-text \
    --permission-mode acceptEdits --allowedTools Bash \
  ) > "$RUN/transcript.jsonl" 2> "$RUN/stderr.txt" < /dev/null
EXIT=$?
set -e
END=$(python3 -c 'import time;print(int(time.time()*1000))')

python3 -c "
import json;json.dump({'case':'$CASE','variant':'$VARIANT','exit':$EXIT,
'start_ms':$START,'end_ms':$END,'duration_ms':$END-$START,'base_sha':'$BASE_SHA'},
open('$RUN/eval_metadata.json','w'),indent=2)"

git -C "$REPO" status --porcelain > "$RUN/repo-status.txt" || true
git -C "$REPO" log --oneline --all > "$RUN/git-log.txt" || true
git -C "$REPO" diff "$BASE_SHA" > "$RUN/final.patch" || true
python3 "$W/bin/parse_trace.py" "$RUN/transcript.jsonl" > "$RUN/trace-summary.json" || true
python3 -c "
import json;t=json.load(open('$RUN/trace-summary.json'))
open('$RUN/final-report.md','w').write((t.get('result') or {}).get('result') or '')" || true

echo "$RUN"
