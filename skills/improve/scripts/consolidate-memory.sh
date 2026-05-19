#!/usr/bin/env bash
# consolidate-memory.sh - Consolidate Skill Evolution Memory into claims.
# Usage: consolidate-memory.sh --memory-dir <dir> [--min-evidence N] [--target-skill skill]

set -euo pipefail

memory_dir=""
min_evidence="2"
target_skill=""

usage() {
  sed -n '2,3p' "$0" >&2
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --memory-dir) memory_dir="$2"; shift 2 ;;
    --min-evidence) min_evidence="$2"; shift 2 ;;
    --target-skill) target_skill="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; usage ;;
  esac
done

[ -n "$memory_dir" ] || usage
command -v jq >/dev/null 2>&1 || { echo "Error: jq is required" >&2; exit 1; }

mkdir -p "$memory_dir/claims" "$memory_dir/eval-cases"
[ -f "$memory_dir/signals.jsonl" ] || : > "$memory_dir/signals.jsonl"

summary_json="$(
  jq -s \
    --arg target_skill "$target_skill" \
    --argjson min_evidence "$min_evidence" \
    '
    def key: [.target_skill, .affected_rule, .gap_type] | join("|");
    [
      .[]
      | select($target_skill == "" or .target_skill == $target_skill)
    ]
    | group_by(key)
    | map({
        target_skill: .[0].target_skill,
        affected_rule: .[0].affected_rule,
        gap_type: .[0].gap_type,
        evidence_count: length,
        signal_ids: map(.signal_id),
        latest_signal_at: (map(.timestamp) | max),
        status: (if length >= $min_evidence then "candidate" else "accumulate" end),
        claim_id: ("claim_" + (.[0].target_skill | gsub("[^A-Za-z0-9]+"; "_") | ascii_downcase) + "_" + (.[0].affected_rule | gsub("[^A-Za-z0-9]+"; "_") | ascii_downcase) + "_" + (.[0].gap_type | gsub("[^A-Za-z0-9]+"; "_") | ascii_downcase))
      })
    ' "$memory_dir/signals.jsonl"
)"

skills="$(printf '%s\n' "$summary_json" | jq -r '.[].target_skill' | sort -u)"

while IFS= read -r skill; do
  [ -n "$skill" ] || continue
  claims_file="$memory_dir/claims/$skill.md"
  {
    echo "# $skill Skill Evolution Claims"
    echo ""
    echo "此檔案由 \`scripts/consolidate-memory.sh\` 依 Skill Evolution Memory 產生。人工確認後，才可把 candidate claim 推進 skill rewrite。"
    echo ""
    echo "## Candidate Claims"
    echo ""
    printf '%s\n' "$summary_json" | jq -r --arg skill "$skill" '
      .[]
      | select(.target_skill == $skill and .status == "candidate")
      | "- **" + .claim_id + "**: `" + .affected_rule + "` / `" + .gap_type + "`，evidence_count=" + (.evidence_count|tostring) + "，signals=" + (.signal_ids|join(", "))'
    echo ""
    echo "## Accumulating Signals"
    echo ""
    printf '%s\n' "$summary_json" | jq -r --arg skill "$skill" '
      .[]
      | select(.target_skill == $skill and .status == "accumulate")
      | "- `" + .affected_rule + "` / `" + .gap_type + "`，evidence_count=" + (.evidence_count|tostring) + "，signals=" + (.signal_ids|join(", "))'
    echo ""
    echo "## Superseded Claims"
    echo ""
    echo "目前尚無 superseded claim。"
  } > "$claims_file"

  eval_file="$memory_dir/eval-cases/$skill.json"
  printf '%s\n' "$summary_json" | jq --arg skill "$skill" '
    {
      skill_name: $skill,
      generated_from: "Skill Evolution Memory consolidated claims",
      eval_cases: [
        .[]
        | select(.target_skill == $skill and .status == "candidate")
        | {
            id: ("eval_" + .claim_id),
            prototype: (if .gap_type == "false_positive" then "D" else "B" end),
            source_claim: .claim_id,
            affected_rule: .affected_rule,
            gap_type: .gap_type,
            evidence_signals: .signal_ids,
            prompt: ("請驗證 `" + .target_skill + "` 的 `" + .affected_rule + "` 規則是否已處理 `" + .gap_type + "` 類型缺口。"),
            expected_output: (if .gap_type == "false_positive" then "必須同時包含 recall、precision clean、false-positive trap 判斷，且不得對 clean/trap case 標 GAP。" else "必須列出可判斷的 scenario/rubric，並說明 candidate rule 是否修復原 gap。" end)
          }
      ]
    }' > "$eval_file"
done <<< "$skills"

graph_tmp="$(mktemp)"
jq \
  --argjson claims "$summary_json" \
  '.claims = $claims | .updated_at = (now | todateiso8601)' \
  "$memory_dir/skill-graph.json" > "$graph_tmp"
mv "$graph_tmp" "$memory_dir/skill-graph.json"

printf '%s\n' "$summary_json"
