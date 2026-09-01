#!/usr/bin/env bash
# resolve_scope.sh - Determine improve scope and paths
# Usage: resolve_scope.sh [TARGET_SKILL] [SCOPE_OVERRIDE]
# Output: scope=... / skill_path=... / queue_path=...

TARGET_SKILL="${1:-}"
SCOPE_OVERRIDE="${2:-}"
AGENTS_SKILLS_HOME="${AGENTS_SKILLS_HOME:-$HOME/.agents/skills}"

determine_scope() {
  [ -n "$SCOPE_OVERRIDE" ] && { echo "$SCOPE_OVERRIDE"; return; }

  # Repo mode: cwd has skills/ directory with at least one SKILL.md
  if [ -d "$(pwd)/skills" ] && find "$(pwd)/skills" -name "SKILL.md" -maxdepth 2 | grep -q .; then
    echo "repo"; return
  fi

  # Project mode: cwd has .agents/skills/
  if [ -d "$(pwd)/.agents/skills" ]; then
    echo "project"; return
  fi

  # User mode: ~/.agents/skills/ exists
  if [ -d "$AGENTS_SKILLS_HOME" ]; then
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
    skill_path="$(pwd)/.agents/skills${TARGET_SKILL:+/$TARGET_SKILL}/SKILL.md"
    queue_path="$(pwd)/.agents/skills/improve/signal-queue.md"
    # Fallback to user queue if project queue doesn't exist
    [ ! -f "$queue_path" ] && queue_path="$AGENTS_SKILLS_HOME/improve/signal-queue.md"
    ;;
  *)
    skill_path="$AGENTS_SKILLS_HOME${TARGET_SKILL:+/$TARGET_SKILL}/SKILL.md"
    queue_path="$AGENTS_SKILLS_HOME/improve/signal-queue.md"
    ;;
esac

echo "scope=$scope"
echo "skill_path=$skill_path"
echo "queue_path=$queue_path"
