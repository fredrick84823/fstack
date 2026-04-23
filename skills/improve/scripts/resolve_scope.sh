#!/usr/bin/env bash
# resolve_scope.sh - Determine improve scope and paths
# Usage: resolve_scope.sh [TARGET_SKILL] [SCOPE_OVERRIDE]
# Output: scope=... / skill_path=... / queue_path=...

TARGET_SKILL="${1:-}"
SCOPE_OVERRIDE="${2:-}"

determine_scope() {
  [ -n "$SCOPE_OVERRIDE" ] && { echo "$SCOPE_OVERRIDE"; return; }

  # Repo mode: cwd has skills/ directory with at least one SKILL.md
  if [ -d "$(pwd)/skills" ] && find "$(pwd)/skills" -name "SKILL.md" -maxdepth 2 | grep -q .; then
    echo "repo"; return
  fi

  # Project mode: cwd has .claude/skills/
  if [ -d "$(pwd)/.claude/skills" ]; then
    echo "project"; return
  fi

  # User mode: ~/.claude/skills/ exists
  if [ -d "$HOME/.claude/skills" ]; then
    echo "user"; return
  fi

  echo "unknown"
}

scope=$(determine_scope)

case "$scope" in
  repo)
    skill_path="$(pwd)/skills${TARGET_SKILL:+/$TARGET_SKILL}/SKILL.md"
    queue_path="$(pwd)/skills/improve/signal-queue.md"
    ;;
  project)
    skill_path="$(pwd)/.claude/skills${TARGET_SKILL:+/$TARGET_SKILL}/SKILL.md"
    queue_path="$(pwd)/.claude/skills/improve/signal-queue.md"
    # Fallback to user queue if project queue doesn't exist
    [ ! -f "$queue_path" ] && queue_path="$HOME/.claude/skills/improve/signal-queue.md"
    ;;
  *)
    skill_path="$HOME/.claude/skills${TARGET_SKILL:+/$TARGET_SKILL}/SKILL.md"
    queue_path="$HOME/.claude/skills/improve/signal-queue.md"
    ;;
esac

echo "scope=$scope"
echo "skill_path=$skill_path"
echo "queue_path=$queue_path"
