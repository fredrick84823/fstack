#!/usr/bin/env bash
# list_candidate_downstream.sh - Dynamically infer downstream skills
# Usage: list_candidate_downstream.sh TARGET_SKILL SCOPE
# Output: comma-separated list of skill names that reference TARGET_SKILL

TARGET_SKILL="${1:?TARGET_SKILL required}"
SCOPE="${2:-user}"

case "$SCOPE" in
  repo)    SKILLS_BASE="$(pwd)/skills" ;;
  project) SKILLS_BASE="$(pwd)/.claude/skills" ;;
  *)       SKILLS_BASE="$HOME/.claude/skills" ;;
esac

[ ! -d "$SKILLS_BASE" ] && echo "無" && exit 0

found=()
while IFS= read -r -d '' skill_md; do
  skill_name=$(basename "$(dirname "$skill_md")")
  [ "$skill_name" = "$TARGET_SKILL" ] && continue
  grep -q "$TARGET_SKILL" "$skill_md" 2>/dev/null && found+=("$skill_name")
done < <(find "$SKILLS_BASE" -name "SKILL.md" -print0)

if [ ${#found[@]} -eq 0 ]; then
  echo "無"
else
  ( IFS=', '; echo "${found[*]}" )
fi
