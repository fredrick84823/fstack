#!/usr/bin/env bash
# capture-signal.sh - Capture <<GAP>> markers from agent output
# Install: add to settings.json hooks.Stop
# Format: <<GAP skill-name: description>>

set -euo pipefail

input=$(cat)
message=$(echo "$input" | jq -r '.last_assistant_message // empty' 2>/dev/null || true)
[ -z "$message" ] && exit 0

# Check for any markers before doing file I/O
echo "$message" | grep -q '<<GAP ' || exit 0

# Determine queue path (project-level takes priority)
if [ -f "$(pwd)/.claude/skills/improve/signal-queue.md" ]; then
  queue="$(pwd)/.claude/skills/improve/signal-queue.md"
else
  queue="$HOME/.claude/skills/improve/signal-queue.md"
  mkdir -p "$(dirname "$queue")"
  touch "$queue"
fi

ts=$(date -Iseconds)

# Extract and append each <<GAP skill-name: description>> marker
echo "$message" | grep -oE '<<GAP [^>]+>>' | while IFS= read -r marker; do
  content="${marker#<<GAP }"
  content="${content%>>}"
  skill="${content%%: *}"
  gap="${content#*: }"
  type="S2"

  [ "$skill" = "$content" ] && skill="unknown"  # no ': ' found
  [ -z "$gap" ] && continue

  {
    echo ""
    echo "## [$ts] $skill"
    echo ""
    echo "- **type**: $type"
    echo "- **source**: agent auto-detected"
    echo "- **gap**: $gap"
    echo "- **status**: pending"
  } >> "$queue"
done
