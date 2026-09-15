#!/usr/bin/env bash
# capture-signal-core.sh - Capture <<GAP>> markers from assistant text.
# Input (stdin): plain assistant message text.
# Format: <<GAP skill-name: description>>

set -euo pipefail

message="$(cat)"
[ -z "$message" ] && exit 0

# Check for any markers before doing file I/O.
echo "$message" | grep -q '<<GAP ' || exit 0

agents_skills_home="${AGENTS_SKILLS_HOME:-$HOME/.agents/skills}"

# Determine queue path. Project-level .agents queues take priority when present.
if [ -f "$(pwd)/.agents/skills/improve/signal-queue.md" ]; then
  queue="$(pwd)/.agents/skills/improve/signal-queue.md"
else
  queue="$agents_skills_home/improve/signal-queue.md"
  mkdir -p "$(dirname "$queue")"
  touch "$queue"
fi

ts="$(date -Iseconds)"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
state_script="$script_dir/signal_state.py"
memory_dir="$(dirname "$queue")/memory"

# Extract and append each <<GAP skill-name: description>> marker.
echo "$message" | grep -oE '<<GAP [^>]+>>' | while IFS= read -r marker; do
  content="${marker#<<GAP }"
  content="${content%>>}"
  skill="${content%%: *}"
  gap="${content#*: }"
  type="S2"

  [ "$skill" = "$content" ] && skill="unknown"
  [ -z "$gap" ] && continue

  if [ -x "$state_script" ]; then
    "$state_script" capture \
      --queue "$queue" \
      --memory-dir "$memory_dir" \
      --timestamp "$ts" \
      --target-skill "$skill" \
      --type "$type" \
      --source "agent auto-detected" \
      --gap "$gap" >/dev/null
  else
    echo "Error: missing executable lifecycle helper: $state_script" >&2
    exit 1
  fi
done
