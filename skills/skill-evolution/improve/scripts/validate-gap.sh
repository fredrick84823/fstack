#!/usr/bin/env bash
# validate-gap.sh - Layer 2 context-aware GAP validator.
# Args: $1=skill $2=gap $3=excerpt
# Output: {"verdict":"...","reason":"...","risk_class":"..."} or empty.

set -euo pipefail

skill="$1"
gap="$2"
excerpt="${3:-}"

command -v claude >/dev/null 2>&1 || exit 0

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
template="$script_dir/../references/validate-gap-prompt.md"
[ -f "$template" ] || exit 0

prompt_file="$(mktemp -t improve-validate.XXXXXX)"
trap 'rm -f "$prompt_file"' EXIT

cat "$template" > "$prompt_file"
{
  printf '\n===INPUT===\n'
  printf 'target_skill: %s\n' "$skill"
  printf 'gap: %s\n' "$gap"
  printf '\n===CONTEXT===\n%s\n' "$excerpt"
} >> "$prompt_file"

raw="$(claude -p --model claude-sonnet-4-6 --output-format text < "$prompt_file" 2>/dev/null || true)"
printf '%s\n' "$raw" | tr -d '\r' | awk 'match($0,/\{[^{}]*"verdict"[^{}]*\}/){print substr($0,RSTART,RLENGTH); exit}'
