#!/usr/bin/env bash
# memory.sh - Minimal Skill Evolution Memory store for improve.
# Usage:
#   memory.sh capture --memory-dir <dir> --timestamp <ts> --target-skill <skill> --type <S1|S2|S3> --source <source> --gap <text>
#   memory.sh lookup --memory-dir <dir> --target-skill <skill> [--affected-rule <rule>] [--gap-type <type>]

set -euo pipefail

command="${1:-}"
[ -n "$command" ] && shift || true

usage() {
  sed -n '2,6p' "$0" >&2
  exit 2
}

require_jq() {
  command -v jq >/dev/null 2>&1 || {
    echo "Error: jq is required for Skill Evolution Memory" >&2
    exit 1
  }
}

ensure_memory_dir() {
  local memory_dir="$1"
  mkdir -p "$memory_dir/claims" "$memory_dir/eval-cases" "$memory_dir/versions"
  [ -f "$memory_dir/signals.jsonl" ] || : > "$memory_dir/signals.jsonl"
  if [ ! -f "$memory_dir/skill-graph.json" ]; then
    cat > "$memory_dir/skill-graph.json" <<'JSON'
{
  "version": 1,
  "updated_at": null,
  "signals": [],
  "claims": [],
  "eval_cases": [],
  "versions": []
}
JSON
  fi
}

slugify() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr -cs '[:alnum:]' '_' | sed 's/^_//; s/_$//'
}

short_hash() {
  if command -v shasum >/dev/null 2>&1; then
    printf '%s' "$1" | shasum | cut -c1-8
  else
    printf '%s' "$1" | cksum | awk '{print $1}'
  fi
}

capture_signal() {
  require_jq

  local memory_dir="" timestamp="" target_skill="" signal_type="" source="" gap=""
  local affected_rule="unknown" gap_type="unknown" expected_behavior="" actual_behavior=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --memory-dir) memory_dir="$2"; shift 2 ;;
      --timestamp) timestamp="$2"; shift 2 ;;
      --target-skill) target_skill="$2"; shift 2 ;;
      --type) signal_type="$2"; shift 2 ;;
      --source) source="$2"; shift 2 ;;
      --gap) gap="$2"; shift 2 ;;
      --affected-rule) affected_rule="$2"; shift 2 ;;
      --gap-type) gap_type="$2"; shift 2 ;;
      --expected-behavior) expected_behavior="$2"; shift 2 ;;
      --actual-behavior) actual_behavior="$2"; shift 2 ;;
      *) echo "Unknown arg: $1" >&2; usage ;;
    esac
  done

  [ -n "$memory_dir" ] || usage
  [ -n "$timestamp" ] || usage
  [ -n "$target_skill" ] || usage
  [ -n "$signal_type" ] || usage
  [ -n "$source" ] || usage
  [ -n "$gap" ] || usage

  ensure_memory_dir "$memory_dir"

  local slug hash signal_id record graph_tmp
  slug="$(slugify "$target_skill")"
  hash="$(short_hash "$timestamp|$target_skill|$gap")"
  signal_id="sig_${timestamp//[-:+T]/}_${slug}_${hash}"

  record="$(
    jq -cn \
      --arg signal_id "$signal_id" \
      --arg timestamp "$timestamp" \
      --arg target_skill "$target_skill" \
      --arg affected_rule "$affected_rule" \
      --arg gap_type "$gap_type" \
      --arg expected_behavior "$expected_behavior" \
      --arg actual_behavior "$actual_behavior" \
      --arg type "$signal_type" \
      --arg source "$source" \
      --arg gap "$gap" \
      '{
        signal_id: $signal_id,
        timestamp: $timestamp,
        target_skill: $target_skill,
        affected_rule: $affected_rule,
        gap_type: $gap_type,
        expected_behavior: $expected_behavior,
        actual_behavior: $actual_behavior,
        evidence_count: 1,
        status: "pending",
        type: $type,
        source: $source,
        gap: $gap,
        links: {
          duplicates: [],
          tested_by: [],
          caused_false_positive: []
        }
      }'
  )"

  printf '%s\n' "$record" >> "$memory_dir/signals.jsonl"

  graph_tmp="$(mktemp)"
  jq \
    --arg signal_id "$signal_id" \
    --arg timestamp "$timestamp" \
    --arg target_skill "$target_skill" \
    --arg affected_rule "$affected_rule" \
    --arg gap_type "$gap_type" \
    --arg status "pending" \
    '.signals = (.signals // []) + [{
      signal_id: $signal_id,
      timestamp: $timestamp,
      target_skill: $target_skill,
      affected_rule: $affected_rule,
      gap_type: $gap_type,
      status: $status
    }] | .updated_at = $timestamp' \
    "$memory_dir/skill-graph.json" > "$graph_tmp"
  mv "$graph_tmp" "$memory_dir/skill-graph.json"

  printf '%s\n' "$signal_id"
}

lookup_memory() {
  require_jq

  local memory_dir="" target_skill="" affected_rule="" gap_type=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --memory-dir) memory_dir="$2"; shift 2 ;;
      --target-skill) target_skill="$2"; shift 2 ;;
      --affected-rule) affected_rule="$2"; shift 2 ;;
      --gap-type) gap_type="$2"; shift 2 ;;
      *) echo "Unknown arg: $1" >&2; usage ;;
    esac
  done

  [ -n "$memory_dir" ] || usage
  [ -n "$target_skill" ] || usage

  ensure_memory_dir "$memory_dir"

  local claims_file eval_file
  claims_file="$memory_dir/claims/$target_skill.md"
  eval_file="$memory_dir/eval-cases/$target_skill.json"

  jq -s \
    --arg target_skill "$target_skill" \
    --arg affected_rule "$affected_rule" \
    --arg gap_type "$gap_type" \
    --arg claims_file "$claims_file" \
    --arg eval_file "$eval_file" \
    '{
      target_skill: $target_skill,
      filters: {
        affected_rule: (if $affected_rule == "" then null else $affected_rule end),
        gap_type: (if $gap_type == "" then null else $gap_type end)
      },
      prior_signals: [
        .[]
        | select(.target_skill == $target_skill)
        | select($affected_rule == "" or .affected_rule == $affected_rule)
        | select($gap_type == "" or .gap_type == $gap_type)
      ],
      claims_file: $claims_file,
      eval_cases_file: $eval_file
    }' "$memory_dir/signals.jsonl"
}

case "$command" in
  capture) capture_signal "$@" ;;
  lookup) lookup_memory "$@" ;;
  *) usage ;;
esac
