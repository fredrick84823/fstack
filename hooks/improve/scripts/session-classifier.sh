#!/usr/bin/env bash
# session-classifier.sh - Claude Code SessionEnd hook adapter.
# Install: add to settings.json hooks.SessionEnd

set -euo pipefail

# Same reason as capture-signal.sh: signal_state.py is the sole lock owner, so the
# classifier stays next to it and this file only points at it.
plugin_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
hook="$plugin_root/skills/skill-evolution/improve/scripts/hooks/claude-session-end.sh"
[ -x "$hook" ] || { echo "Error: missing executable session-end hook: $hook" >&2; exit 1; }

exec "$hook" "$@"
