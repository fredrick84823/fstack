#!/usr/bin/env bash
# capture-signal.sh - Backward-compatible Claude Code Stop hook adapter.
# Install: add to settings.json hooks.Stop

set -euo pipefail

input=$(cat)
message=$(echo "$input" | jq -r '.last_assistant_message // empty' 2>/dev/null || true)
[ -z "$message" ] && exit 0

# The lifecycle helpers live with the skill, not here: signal_state.py is the sole
# lock owner, and a second copy under hooks/ would be a second owner.
plugin_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
core="$plugin_root/skills/skill-evolution/improve/scripts/capture-signal-core.sh"
[ -x "$core" ] || { echo "Error: missing executable capture core: $core" >&2; exit 1; }

printf '%s' "$message" | "$core"
