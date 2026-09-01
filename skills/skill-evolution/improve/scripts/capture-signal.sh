#!/usr/bin/env bash
# capture-signal.sh - Backward-compatible Claude Code Stop hook adapter.
# Install: add to settings.json hooks.Stop

set -euo pipefail

input=$(cat)
message=$(echo "$input" | jq -r '.last_assistant_message // empty' 2>/dev/null || true)
[ -z "$message" ] && exit 0

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
printf '%s' "$message" | "$script_dir/capture-signal-core.sh"
