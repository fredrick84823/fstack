#!/usr/bin/env bash
# cluster-sessions.sh — skill miner's model step: one week of sessions in, recurring tasks out.
#
#   cluster-sessions.sh < input        input = ===SESSIONS=== and ===INSTALLED_SKILLS=== blocks
#
# Same shape as validate-gap.sh: --safe-mode, a JSON schema
# (../references/cluster-sessions-schema.json), and fail-closed. Exit 0 with one JSON
# object on stdout — the schema's `clusters` plus `usage` and `total_cost_usd` from the
# claude -p response — or exit non-zero having printed nothing. Silence must never read
# as "no clusters".
#
# The clustering rules live in ../references/cluster-sessions-prompt.md.
# Model: $IMPROVE_MINER_MODEL, default sonnet.

set -euo pipefail

die() { echo "cluster-sessions: $*" >&2; exit 1; }

model="${IMPROVE_MINER_MODEL:-sonnet}"
command -v claude >/dev/null 2>&1 || die "claude CLI not found"
command -v jq >/dev/null 2>&1 || die "jq not found"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
template="$script_dir/../references/cluster-sessions-prompt.md"
schema="$script_dir/../references/cluster-sessions-schema.json"
[ -f "$template" ] || die "missing prompt: $template"
[ -f "$schema" ] || die "missing schema: $schema"

# --safe-mode: the user's own CLAUDE.md / hooks / MCP must not reach the clusterer.
# No --allowed-tools plus --permission-prompts none: the answer can only come from stdin.
raw="$(
  { cat "$template"; printf '\n'; cat; } | claude -p \
        --safe-mode \
        --model "$model" \
        --output-format json \
        --json-schema "$(cat "$schema")" \
        --no-session-persistence \
        --permission-prompts none 2>/dev/null
)" || die "claude -p failed (model=$model)"

printf '%s' "$raw" | jq -ce '
  ([.. | objects | select(has("structured_output"))] | last) as $r
  | if $r == null or ($r.structured_output | type) != "object" or ($r.structured_output.clusters | type) != "array" then
      error("no structured output in claude -p response")
    else $r.structured_output + {usage: $r.usage, total_cost_usd: $r.total_cost_usd} end
' || die "could not read clusters out of the claude -p response"
