#!/usr/bin/env bash
# SessionStart hook: notify Claude about pending improve signals on session start
# Install: add to settings.json hooks.SessionStart

input=$(cat)  # consume stdin (required for hooks)

# Support both user-level and project-level queues
if [ -f "$(pwd)/.claude/skills/improve/signal-queue.md" ]; then
  QUEUE="$(pwd)/.claude/skills/improve/signal-queue.md"
elif [ -f "$HOME/.claude/skills/improve/signal-queue.md" ]; then
  QUEUE="$HOME/.claude/skills/improve/signal-queue.md"
else
  exit 0
fi

pending=$(awk '
  /<!--/ { in_comment = 1 }
  /-->/ { in_comment = 0; next }
  !in_comment && /^\- \*\*status\*\*: pending/ { count++ }
  END { print count+0 }
' "$QUEUE")
[ "$pending" -eq 0 ] && exit 0

# Extract one-liner per pending signal: skill name + gap (skip comment blocks)
summary=$(awk '
  /<!--/ { in_comment = 1 }
  /-->/ { in_comment = 0; next }
  in_comment { next }
  /^## \[/ { split($0, a, "] "); skill = a[2] }
  /\*\*gap\*\*:/ { gsub(/.*\*\*gap\*\*: /, ""); gap = $0 }
  /\*\*status\*\*: pending/ { print "  [" skill "] " gap }
' "$QUEUE")

echo "## ⚠️ improve signal-queue 有 ${pending} 個待處理 signal"
echo ""
echo "$summary"
echo ""
echo "執行 /improve 以處理。"
