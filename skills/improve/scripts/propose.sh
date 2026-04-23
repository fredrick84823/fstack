#!/usr/bin/env bash
# propose.sh - Manually append a skill candidate to the queue
# Use in Codex CLI or any environment without Stop hooks.
# Usage: propose.sh --name <name> [--reason <text>] [--steps <text>] [--hints <text>]

set -euo pipefail

name=""
reason=""
steps=""
hints=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)   name="$2";   shift 2 ;;
    --reason) reason="$2"; shift 2 ;;
    --steps)  steps="$2";  shift 2 ;;
    --hints)  hints="$2";  shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

[ -z "$name" ] && { echo "Error: --name is required" >&2; exit 1; }

if [ -f "$(pwd)/.claude/skills/improve/candidate-queue.md" ]; then
  queue="$(pwd)/.claude/skills/improve/candidate-queue.md"
else
  queue="$HOME/.claude/skills/improve/candidate-queue.md"
  mkdir -p "$(dirname "$queue")"
  touch "$queue"
fi

ts=$(date -Iseconds)

{
  echo ""
  echo "## [$ts] $name"
  echo ""
  echo "- **status**: pending"
  echo "- **hit_count**: 1"
  echo "- **first_seen**: $ts"
  echo "- **last_seen**: $ts"
  [ -n "$reason" ] && echo "- **reason**: $reason"
  [ -n "$steps"  ] && echo "- **steps**: $steps"
  [ -n "$hints"  ] && echo "- **invoker_hints**: $hints"
} >> "$queue"

echo "✅ Candidate '$name' appended to $queue"
