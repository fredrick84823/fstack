#!/usr/bin/env bash
# validate-gap.sh — Layer 2 GAP validator, precision-first.
#
#   validate-gap.sh <target_skill> <gap> [excerpt] [known_signals]
#
# known_signals: the signals already on file for this skill, one per line as
# `<signal_id>\t<gap>`. Empty is fine; without it the validator cannot say
# duplicate, and duplicates were 43% of the queue's worst month.
#
# ── JSON contract ────────────────────────────────────────────────────────────
# One object on stdout, no fences. #44's session-level classifier consumes this
# verbatim, so the field set is frozen here and enforced by
# ../references/validate-gap-schema.json (that file is the machine copy; this
# comment is the human one, and tests/unit/test_validator_contract.py keeps the
# two from drifting):
#
#   verdict         "accept" | "reject"          — uncertain is reject, never accept
#   target_skill    skill the gap is attributed to
#   gap             one-line repeatable rule deficit, normalized
#   duplicate_of    id from known_signals that this restates, else null; always
#                   null on accept — same complaint, different words, still duplicate
#   evidence_quote  verbatim user sentence proving it; "" when reject
#   expected        what the skill should have done; "" when reject
#   actual          what it did instead;             "" when reject
#   risk_class      valid_gap | placeholder | doc_echo | one_shot_pref |
#                   data_issue | misroute | duplicate | self_referential | uncertain
#   reason          one sentence naming the deciding evidence
#
# Invariants: verdict == "accept" implies risk_class == "valid_gap", non-empty
# evidence_quote / expected / actual, and duplicate_of == null. A model that breaks
# either one is downgraded to reject here rather than trusted — an accept nobody can
# trace back to a user sentence, or one that points at a signal already on file, is
# exactly the failure this rewrite exists to stop.
#
# The judgement rules live in ../references/validate-gap-prompt.md. This script
# only wires them up; do not restate a rule here.
#
# ── Model ────────────────────────────────────────────────────────────────────
#   $IMPROVE_VALIDATOR_MODEL, default claude-haiku-4-5-20251001.
#
# ── Failure is closed ────────────────────────────────────────────────────────
# Exit 0 with one JSON object, or exit non-zero having printed nothing. The old
# version exited 0 silently when `claude` was missing; a caller that cannot tell
# "reject" from "the validator never ran" ends up accepting everything.

set -euo pipefail

usage() { echo "usage: validate-gap.sh <target_skill> <gap> [excerpt] [known_signals]" >&2; exit 2; }
die() { echo "validate-gap: $*" >&2; exit 1; }

[ $# -ge 2 ] || usage
skill="$1"
gap="$2"
excerpt="${3:-}"
known_signals="${4:-}"
[ -n "$skill" ] && [ -n "$gap" ] || usage

model="${IMPROVE_VALIDATOR_MODEL:-claude-haiku-4-5-20251001}"

command -v claude >/dev/null 2>&1 || die "claude CLI not found"
command -v jq >/dev/null 2>&1 || die "jq not found"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
template="$script_dir/../references/validate-gap-prompt.md"
schema="$script_dir/../references/validate-gap-schema.json"
[ -f "$template" ] || die "missing prompt: $template"
[ -f "$schema" ] || die "missing schema: $schema"

# --safe-mode: the user's own CLAUDE.md / hooks / MCP must not reach the classifier.
# No --allowed-tools plus --permission-prompts none: every tool call is auto-denied,
# so the verdict can only come from the excerpt it was handed.
raw="$(
  {
    cat "$template"
    printf '\n===INPUT===\ntarget_skill: %s\ngap: %s\n' "$skill" "$gap"
    printf '\n===CONTEXT===\n%s\n' "$excerpt"
    printf '\n===KNOWN_SIGNALS===\n%s\n' "$known_signals"
  } | claude -p \
        --safe-mode \
        --model "$model" \
        --output-format json \
        --json-schema "$(cat "$schema")" \
        --no-session-persistence \
        --permission-prompts none 2>/dev/null
)" || die "claude -p failed (model=$model)"

printf '%s' "$raw" | jq -ce '
  ([.. | objects | select(has("structured_output"))] | last | .structured_output) as $o
  | if $o == null or ($o | type) != "object" then
      error("no structured output in claude -p response")
    elif $o.verdict == "accept" and ($o.duplicate_of // null) != null then
      $o + {
        verdict: "reject",
        risk_class: "duplicate",
        evidence_quote: "", expected: "", actual: "",
        reason: "accept pointing at an existing signal — downgraded by validate-gap.sh"
      }
    elif $o.verdict == "accept"
         and (($o.evidence_quote // "") == ""
              or ($o.expected // "") == ""
              or ($o.actual // "") == "") then
      $o + {
        verdict: "reject",
        risk_class: "uncertain",
        evidence_quote: "", expected: "", actual: "",
        reason: "accept without evidence_quote/expected/actual — downgraded by validate-gap.sh"
      }
    else $o end
' || die "could not read a verdict out of the claude -p response"
