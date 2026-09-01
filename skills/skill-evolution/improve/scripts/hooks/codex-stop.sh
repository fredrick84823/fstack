#!/usr/bin/env bash
# Codex Stop hook adapter.
# Codex passes hook JSON as argv in common desktop/CLI setups; stdin is a fallback.

set -euo pipefail

payload="${1:-}"
if [ -z "$payload" ]; then
  payload="$(cat)"
fi
[ -z "$payload" ] && exit 0

if [ "${IMPROVE_HOOK_DEBUG:-0}" = "1" ]; then
  {
    printf '[%s] codex-stop payload keys: ' "$(date -Iseconds)"
    echo "$payload" | jq -cr 'if type == "object" then keys else type end' 2>/dev/null || printf 'non-json'
    printf '\n'
  } >> /tmp/improve-hook-debug.log
fi

message="$(
  echo "$payload" | jq -r '
    def textish:
      if type == "string" then .
      elif type == "array" then map(textish) | join("\n")
      elif type == "object" then (.text? // .content? // .message? // .output? // empty | textish)
      else empty end;

    [
      .last_assistant_message?,
      .assistant_message?,
      .assistant_output?,
      .assistant_response?,
      .response?,
      .output?,
      .message?,
      .last_message?,
      (.transcript?[-1]?.content?),
      (.messages?[]? | select(((.role? // .type? // "") | tostring) | test("assistant|model")) | (.content? // .text? // .message? // .output?))
    ]
    | map(textish)
    | map(select(. != ""))
    | last // empty
  ' 2>/dev/null || true
)"
[ -z "$message" ] && exit 0

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
printf '%s' "$message" | "$script_dir/capture-signal-core.sh"
