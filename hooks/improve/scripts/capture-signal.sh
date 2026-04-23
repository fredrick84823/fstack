#!/usr/bin/env bash
# capture-signal.sh - Capture <<IMPROVE_SIGNAL>> markers from agent output
# Install: add to settings.json hooks.Stop
# Format: <<IMPROVE_SIGNAL skill="name" type="S1|S2|S3" gap="description">>

set -euo pipefail

input=$(cat)
message=$(echo "$input" | jq -r '.last_assistant_message // empty' 2>/dev/null || true)
[ -z "$message" ] && exit 0

# Check for any markers before doing file I/O
echo "$message" | grep -q '<<IMPROVE_SIGNAL' || exit 0

# Determine queue path (project-level takes priority)
if [ -f "$(pwd)/.claude/skills/improve/signal-queue.md" ]; then
  queue="$(pwd)/.claude/skills/improve/signal-queue.md"
else
  queue="$HOME/.claude/skills/improve/signal-queue.md"
  mkdir -p "$(dirname "$queue")"
  touch "$queue"
fi

ts=$(date -Iseconds)

# Extract and append each <<IMPROVE_SIGNAL ...>> marker (BSD-compatible sed)
echo "$message" | grep -o '<<IMPROVE_SIGNAL[^>]*>>' | while IFS= read -r marker; do
  skill=$(echo "$marker" | sed 's/.*skill="\([^"]*\)".*/\1/')
  type=$(echo "$marker"  | sed 's/.*type="\([^"]*\)".*/\1/')
  gap=$(echo "$marker"   | sed 's/.*gap="\([^"]*\)".*/\1/')

  # sed returns the original string unchanged if no match — detect that
  [ "$skill" = "$marker" ] && skill="unknown"
  [ "$type"  = "$marker" ] && type="S2"
  [ "$gap"   = "$marker" ] && gap=""

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
