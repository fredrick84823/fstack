#!/usr/bin/env bash
# capture-skill-candidate.sh - Capture <<SKILL_CANDIDATE>> markers from agent output
# Register in settings.json hooks.Stop to run automatically after each agent turn.
#
# Input (stdin): Claude Code Stop hook JSON
# Output: appends captured candidates to candidate-queue.md

set -euo pipefail

input=$(cat)
message=$(echo "$input" | jq -r '.last_assistant_message // empty' 2>/dev/null || true)
[ -z "$message" ] && exit 0

# Determine queue path (project-level takes priority)
if [ -f "$(pwd)/.claude/skills/improve/candidate-queue.md" ]; then
  queue="$(pwd)/.claude/skills/improve/candidate-queue.md"
else
  queue="$HOME/.claude/skills/improve/candidate-queue.md"
  mkdir -p "$(dirname "$queue")"
  touch "$queue"
fi

# Extract <<SKILL_CANDIDATE ... >> blocks
# Supports both single-line and multi-line markers
extracted=$(echo "$message" | awk '
  /<<SKILL_CANDIDATE/ { inside=1; block=$0; next }
  inside && />>/ { block=block"\n"$0; print block; inside=0; block=""; next }
  inside { block=block"\n"$0 }
')

[ -z "$extracted" ] && exit 0

ts=$(date -Iseconds)
session_id=$(echo "$input" | jq -r '.session_id // "unknown"' 2>/dev/null || echo "unknown")

# Parse and append each candidate
echo "$extracted" | while IFS= read -r line; do
  # Skip the outer markers, keep the content
  clean=$(echo "$line" | sed 's/<<SKILL_CANDIDATE[[:space:]]*//' | sed 's/>>//g')
  name=$(echo "$clean" | grep -oP '(?<=name:\s)[\w-]+' | head -1 || echo "unnamed-$(date +%s)")

  {
    echo ""
    echo "## [$ts] $name"
    echo ""
    echo "$clean" | grep -v '^<<' | grep -v '^>>'
    echo "- **status**: pending"
    echo "- **hit_count**: 1"
    echo "- **first_seen**: $ts"
    echo "- **last_seen**: $ts"
    echo "- **sources**: session/$session_id"
  } >> "$queue"
done
