#!/usr/bin/env bash
# optimization.sh - SkillOpt-like artifact recorder for /improve.
# Usage:
#   optimization.sh init-run --memory-dir <dir> --target-skill <skill> [--run-id <id>] [--baseline-skill-path <path>]
#   optimization.sh split-evals --skill-dir <dir> --run-id <id> [--memory-dir <dir>] [--heldout-ratio <ratio>]
#   optimization.sh record-rollout --memory-dir <dir> --run-id <id> --input-json <file>
#   optimization.sh record-candidate --memory-dir <dir> --run-id <id> --metadata-json <json> [--diff-preview-file <path>]
#   optimization.sh compare-run --memory-dir <dir> --run-id <id>
#   optimization.sh compare-heldout --memory-dir <dir> --run-id <id>
#   optimization.sh record-decision --memory-dir <dir> --run-id <id> --decision accepted|rejected|needs_modification --reason <text> [--approval-source <source>] [--approved-by <name>]
#   optimization.sh reject-edit --memory-dir <dir> --run-id <id> --reason <reason> --failed-cases <csv> --avoid-next-time <text> [--target-skill <skill>] [--affected-rule <rule>] [--section <section>] [--edit-summary <text>]
#   optimization.sh accept-edit --memory-dir <dir> --run-id <id> --best-skill-path <path> --approval-source <source> --approved-by <name> [--target-skill <skill>]

set -euo pipefail

command="${1:-}"
[ -n "$command" ] && shift || true

usage() {
  sed -n '2,10p' "$0" >&2
  exit 2
}

require_jq() {
  command -v jq >/dev/null 2>&1 || {
    echo "Error: jq is required for optimization memory" >&2
    exit 1
  }
}

now_iso() {
  date "+%Y-%m-%dT%H:%M:%S%z"
}

sha256_file() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    cksum "$1" | awk '{print $1}'
  fi
}

new_run_id() {
  date "+opt_%Y%m%d_%H%M%S"
}

ensure_optimization_dir() {
  local memory_dir="$1"
  mkdir -p \
    "$memory_dir/optimization/rollouts" \
    "$memory_dir/optimization/candidates" \
    "$memory_dir/optimization/decisions" \
    "$memory_dir/optimization/best"
  [ -f "$memory_dir/optimization/rejected-edits.jsonl" ] || : > "$memory_dir/optimization/rejected-edits.jsonl"
}

rollout_path() {
  printf '%s/optimization/rollouts/%s.json' "$1" "$2"
}

decision_path() {
  printf '%s/optimization/decisions/%s.json' "$1" "$2"
}

candidate_path() {
  printf '%s/optimization/candidates/%s-candidate.md' "$1" "$2"
}

candidate_json_path() {
  printf '%s/optimization/candidates/%s-candidate.json' "$1" "$2"
}

load_rollout_field() {
  local memory_dir="$1" run_id="$2" field="$3" path
  path="$(rollout_path "$memory_dir" "$run_id")"
  [ -f "$path" ] || {
    echo "Error: rollout not found: $path" >&2
    exit 1
  }
  jq -r "$field // empty" "$path"
}

init_run() {
  require_jq

  local memory_dir="" target_skill="" run_id="" baseline_skill_path="" ts path

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --memory-dir) memory_dir="$2"; shift 2 ;;
      --target-skill) target_skill="$2"; shift 2 ;;
      --run-id) run_id="$2"; shift 2 ;;
      --baseline-skill-path) baseline_skill_path="$2"; shift 2 ;;
      *) echo "Unknown arg: $1" >&2; usage ;;
    esac
  done

  [ -n "$memory_dir" ] || usage
  [ -n "$target_skill" ] || usage

  ensure_optimization_dir "$memory_dir"
  [ -n "$run_id" ] || run_id="$(new_run_id)"
  ts="$(now_iso)"
  path="$(rollout_path "$memory_dir" "$run_id")"

  if [ -f "$path" ]; then
    echo "Error: rollout already exists: $path" >&2
    exit 1
  fi

  jq -n \
    --arg run_id "$run_id" \
    --arg target_skill "$target_skill" \
    --arg baseline_skill_path "$baseline_skill_path" \
    --arg created_at "$ts" \
    '{
      run_id: $run_id,
      target_skill: $target_skill,
      baseline_skill_path: $baseline_skill_path,
      created_at: $created_at,
      eval_split: {
        train_case_ids: [],
        heldout_case_ids: []
      },
      results: []
    }' > "$path"

  printf '%s\n' "$run_id"
}

split_evals() {
  require_jq

  local skill_dir="" memory_dir="" run_id="" heldout_ratio="0.3"
  local eval_file="" skill_file="" path="" tmp="" ts="" evals_sha="" skill_sha=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --skill-dir) skill_dir="$2"; shift 2 ;;
      --memory-dir) memory_dir="$2"; shift 2 ;;
      --run-id) run_id="$2"; shift 2 ;;
      --heldout-ratio) heldout_ratio="$2"; shift 2 ;;
      *) echo "Unknown arg: $1" >&2; usage ;;
    esac
  done

  [ -n "$skill_dir" ] || usage
  [ -n "$run_id" ] || usage
  [ -n "$memory_dir" ] || memory_dir="$skill_dir/memory"

  ensure_optimization_dir "$memory_dir"
  eval_file="$skill_dir/evals/evals.json"
  skill_file="$skill_dir/SKILL.md"
  path="$(rollout_path "$memory_dir" "$run_id")"
  [ -f "$eval_file" ] || {
    echo "Error: eval file not found: $eval_file" >&2
    exit 1
  }
  [ -f "$skill_file" ] || {
    echo "Error: skill file not found: $skill_file" >&2
    exit 1
  }
  [ -f "$path" ] || {
    echo "Error: rollout not found: $path" >&2
    exit 1
  }

  ts="$(now_iso)"
  evals_sha="$(sha256_file "$eval_file")"
  skill_sha="$(sha256_file "$skill_file")"
  tmp="$(mktemp)"
  jq \
    --slurpfile evals "$eval_file" \
    --argjson ratio "$heldout_ratio" \
    --arg generated_at "$ts" \
    --arg evals_sha256 "$evals_sha" \
    --arg skill_sha256 "$skill_sha" \
    '
    ($evals[0].evals | map(.id)) as $ids
    | ($ids | length) as $total
    | if $total == 0 then error("evals/evals.json has no eval cases") else . end
    | (($total * $ratio) | ceil) as $raw_count
    | ([1, $raw_count] | max | if . > $total then $total else . end) as $heldout_count
    | ($evals[0].evals
        | map(select(.prototype == "D" and (.case_type == "precision_clean" or .case_type == "false_positive_trap")) | .id)
        | last) as $guard_id
    | ($ids | reverse | .[0:$heldout_count] | reverse) as $tail_heldout
    | (if $guard_id == null or ($tail_heldout | index($guard_id)) != null
       then $tail_heldout
       elif ($tail_heldout | length) == 0
       then [$guard_id]
       else (($tail_heldout[1:] + [$guard_id]) | unique)
       end) as $heldout
    | ($ids | map(select(($heldout | index(.)) | not))) as $train
    | .eval_split = {
        train_case_ids: $train,
        heldout_case_ids: $heldout,
        heldout_ratio: $ratio,
        policy: "stable-tail-with-d-no-gap-guard",
        policy_version: 1,
        rounding: "ceil(total * heldout_ratio), minimum 1",
        order: "evals/evals.json array order",
        guard: "if available, held-out must include the last D precision_clean or false_positive_trap case",
        evals_sha256: $evals_sha256,
        skill_sha256: $skill_sha256,
        generated_at: $generated_at
      }' "$path" > "$tmp"
  mv "$tmp" "$path"

  jq '.eval_split' "$path"
}

record_rollout() {
  require_jq

  local memory_dir="" run_id="" input_json=""
  local case_id="" variant="" verdict="" failure_type="" notes="" expected_output="" observed_output="" prompt="" split="" evaluator="agent-session" source="manual-record"
  local protected_behavior_checked="[]"
  local path="" tmp="" ts="" result_json=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --memory-dir) memory_dir="$2"; shift 2 ;;
      --run-id) run_id="$2"; shift 2 ;;
      --input-json) input_json="$2"; shift 2 ;;
      --case-id) case_id="$2"; shift 2 ;;
      --variant) variant="$2"; shift 2 ;;
      --verdict) verdict="$2"; shift 2 ;;
      --failure-type) failure_type="$2"; shift 2 ;;
      --prompt) prompt="$2"; shift 2 ;;
      --expected-output) expected_output="$2"; shift 2 ;;
      --observed-output) observed_output="$2"; shift 2 ;;
      --split) split="$2"; shift 2 ;;
      --evaluator) evaluator="$2"; shift 2 ;;
      --source) source="$2"; shift 2 ;;
      --protected-behavior-checked) protected_behavior_checked="$2"; shift 2 ;;
      --notes) notes="$2"; shift 2 ;;
      *) echo "Unknown arg: $1" >&2; usage ;;
    esac
  done

  [ -n "$memory_dir" ] || usage
  [ -n "$run_id" ] || usage

  ensure_optimization_dir "$memory_dir"
  path="$(rollout_path "$memory_dir" "$run_id")"
  [ -f "$path" ] || {
    echo "Error: rollout not found: $path" >&2
    exit 1
  }

  ts="$(now_iso)"
  if [ -n "$input_json" ]; then
    [ -f "$input_json" ] || {
      echo "Error: input JSON not found: $input_json" >&2
      exit 1
    }
    jq -e '
      (.case_id | type == "number") and
      (.variant == "baseline" or .variant == "candidate") and
      (.verdict == "pass" or .verdict == "fail") and
      (.expected_output | type == "string") and
      (.observed_output | type == "string") and
      (.notes | type == "string")
    ' "$input_json" >/dev/null || {
      echo "Error: rollout input must include case_id, variant, verdict, expected_output, observed_output, and notes" >&2
      exit 1
    }
    result_json="$(
      jq \
        --arg recorded_at "$ts" \
        '{
          case_id,
          variant,
          verdict,
          split: (.split // null),
          failure_type: (.failure_type // null),
          prompt: (.prompt // ""),
          expected_output,
          observed_output,
          notes,
          evaluator: (.evaluator // "agent-session"),
          source: (.source // "manual-record"),
          protected_behavior_checked: (.protected_behavior_checked // []),
          recorded_at: $recorded_at
        }' "$input_json"
    )"
  else
    [ -n "$case_id" ] || usage
    [ "$variant" = "baseline" ] || [ "$variant" = "candidate" ] || {
      echo "Error: --variant must be baseline or candidate" >&2
      exit 1
    }
    [ "$verdict" = "pass" ] || [ "$verdict" = "fail" ] || {
      echo "Error: --verdict must be pass or fail" >&2
      exit 1
    }
    [ -n "$expected_output" ] || usage
    [ -n "$observed_output" ] || usage
    [ -n "$notes" ] || usage
    jq -e 'type == "array"' >/dev/null <<<"$protected_behavior_checked" || {
      echo "Error: --protected-behavior-checked must be a JSON array" >&2
      exit 1
    }
    result_json="$(
      jq -n \
        --argjson case_id "$case_id" \
        --arg variant "$variant" \
        --arg verdict "$verdict" \
        --arg split "$split" \
        --arg failure_type "$failure_type" \
        --arg prompt "$prompt" \
        --arg expected_output "$expected_output" \
        --arg observed_output "$observed_output" \
        --arg notes "$notes" \
        --arg evaluator "$evaluator" \
        --arg source "$source" \
        --argjson protected_behavior_checked "$protected_behavior_checked" \
        --arg recorded_at "$ts" \
        '{
          case_id: $case_id,
          variant: $variant,
          verdict: $verdict,
          split: (if $split == "" then null else $split end),
          failure_type: (if $failure_type == "" then null else $failure_type end),
          prompt: $prompt,
          expected_output: $expected_output,
          observed_output: $observed_output,
          notes: $notes,
          evaluator: $evaluator,
          source: $source,
          protected_behavior_checked: $protected_behavior_checked,
          recorded_at: $recorded_at
        }'
    )"
  fi

  tmp="$(mktemp)"
  jq --argjson result "$result_json" '.results = (.results // []) + [$result]' "$path" > "$tmp"
  mv "$tmp" "$path"
}

validate_candidate_metadata() {
  local metadata="$1" op_count="" lr=""

  jq -e '
    (.textual_learning_rate | type == "string") and
    (.edit_operations | type == "array") and
    ((.edit_operations | length) > 0) and
    (.expected_behavior_change | type == "string") and
    (.protected_behavior | type == "array")
  ' >/dev/null <<<"$metadata" || {
    echo "Error: candidate metadata must include textual_learning_rate, edit_operations, expected_behavior_change, and protected_behavior" >&2
    exit 1
  }

  lr="$(jq -r '.textual_learning_rate' <<<"$metadata")"
  op_count="$(jq '.edit_operations | length' <<<"$metadata")"

  case "$lr" in
    lr_small)
      [ "$op_count" -le 1 ] || {
        echo "Error: lr_small allows at most 1 edit operation" >&2
        exit 1
      }
      ;;
    lr_medium)
      [ "$op_count" -le 3 ] || {
        echo "Error: lr_medium allows at most 3 edit operations" >&2
        exit 1
      }
      ;;
    lr_large)
      jq -e '.human_preapproval_required == true' >/dev/null <<<"$metadata" || {
        echo "Error: lr_large requires human_preapproval_required=true" >&2
        exit 1
      }
      ;;
    *)
      echo "Error: textual_learning_rate must be lr_small, lr_medium, or lr_large" >&2
      exit 1
      ;;
  esac
}

record_candidate() {
  require_jq

  local memory_dir="" run_id="" metadata_json="" diff_preview_file="" path="" json_path="" ts="" diff_preview=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --memory-dir) memory_dir="$2"; shift 2 ;;
      --run-id) run_id="$2"; shift 2 ;;
      --metadata-json) metadata_json="$2"; shift 2 ;;
      --diff-preview-file) diff_preview_file="$2"; shift 2 ;;
      *) echo "Unknown arg: $1" >&2; usage ;;
    esac
  done

  [ -n "$memory_dir" ] || usage
  [ -n "$run_id" ] || usage
  [ -n "$metadata_json" ] || usage

  ensure_optimization_dir "$memory_dir"
  validate_candidate_metadata "$metadata_json"

  if [ -n "$diff_preview_file" ] && [ ! -f "$diff_preview_file" ]; then
    echo "Error: diff preview file not found: $diff_preview_file" >&2
    exit 1
  fi

  ts="$(now_iso)"
  path="$(candidate_path "$memory_dir" "$run_id")"
  json_path="$(candidate_json_path "$memory_dir" "$run_id")"
  if [ -n "$diff_preview_file" ]; then
    diff_preview="$(sed -n '1,400p' "$diff_preview_file")"
  else
    diff_preview=""
  fi

  jq -n \
    --arg run_id "$run_id" \
    --arg recorded_at "$ts" \
    --arg candidate_markdown "$path" \
    --arg diff_preview "$diff_preview" \
    --argjson metadata "$metadata_json" \
    '{
      run_id: $run_id,
      recorded_at: $recorded_at,
      candidate_markdown: $candidate_markdown,
      metadata: $metadata,
      diff_preview: $diff_preview
    }' > "$json_path"

  {
    printf '# Candidate Patch: %s\n\n' "$run_id"
    printf 'Recorded at: `%s`\n\n' "$ts"
    printf 'Machine-readable sidecar: `%s`\n\n' "$json_path"
    printf '## Metadata\n\n'
    printf '```json\n'
    jq '.' <<<"$metadata_json"
    printf '```\n\n'
    printf '## Diff Preview\n\n'
    if [ -n "$diff_preview_file" ]; then
      printf '```diff\n'
      cat "$diff_preview_file"
      printf '\n```\n'
    else
      printf '_No diff preview provided._\n'
    fi
  } > "$path"

  printf '%s\n' "$json_path"
}

compare_run() {
  require_jq

  local memory_dir="" run_id="" path=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --memory-dir) memory_dir="$2"; shift 2 ;;
      --run-id) run_id="$2"; shift 2 ;;
      *) echo "Unknown arg: $1" >&2; usage ;;
    esac
  done

  [ -n "$memory_dir" ] || usage
  [ -n "$run_id" ] || usage

  path="$(rollout_path "$memory_dir" "$run_id")"
  [ -f "$path" ] || {
    echo "Error: rollout not found: $path" >&2
    exit 1
  }

  jq '
    def count_variant($variant; $verdict):
      [.results[]? | select(.variant == $variant and .verdict == $verdict)] | length;
    def in_heldout($heldout): . as $result | ($heldout | index($result.case_id)) != null;
    def count_heldout($variant; $verdict; $heldout):
      [.results[]? | select(.variant == $variant and .verdict == $verdict and in_heldout($heldout))] | length;
    def protected_ok:
      all(.results[]?.protected_behavior_checked[]?; (.status // "pass") == "pass");
    (.eval_split.heldout_case_ids // []) as $heldout
    | {
        run_id,
        target_skill,
        baseline: {
          pass: count_variant("baseline"; "pass"),
          fail: count_variant("baseline"; "fail")
        },
        candidate: {
          pass: count_variant("candidate"; "pass"),
          fail: count_variant("candidate"; "fail")
        },
        heldout: {
          case_ids: $heldout,
          baseline: [.results[]? | select(.variant == "baseline" and in_heldout($heldout))],
          candidate: [.results[]? | select(.variant == "candidate" and in_heldout($heldout))],
          baseline_pass: count_heldout("baseline"; "pass"; $heldout),
          baseline_fail: count_heldout("baseline"; "fail"; $heldout),
          candidate_pass: count_heldout("candidate"; "pass"; $heldout),
          candidate_fail: count_heldout("candidate"; "fail"; $heldout)
        },
        protected_behavior_status: (if protected_ok then "pass" else "fail" end),
        decision_hint:
          (if (count_heldout("candidate"; "fail"; $heldout) == 0 and (protected_ok) and count_variant("candidate"; "pass") >= count_variant("baseline"; "pass"))
          then "accept_or_human_review"
          else "reject_or_modify"
          end)
      }' "$path"
}

record_decision() {
  require_jq

  local memory_dir="" run_id="" decision="" reason="" approval_source="" approved_by="" path="" rollout="" ts="" summary=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --memory-dir) memory_dir="$2"; shift 2 ;;
      --run-id) run_id="$2"; shift 2 ;;
      --decision) decision="$2"; shift 2 ;;
      --reason) reason="$2"; shift 2 ;;
      --approval-source) approval_source="$2"; shift 2 ;;
      --approved-by) approved_by="$2"; shift 2 ;;
      *) echo "Unknown arg: $1" >&2; usage ;;
    esac
  done

  [ -n "$memory_dir" ] || usage
  [ -n "$run_id" ] || usage
  case "$decision" in
    accepted|rejected|needs_modification) ;;
    *) echo "Error: --decision must be accepted, rejected, or needs_modification" >&2; exit 1 ;;
  esac
  [ -n "$reason" ] || usage

  ensure_optimization_dir "$memory_dir"
  rollout="$(rollout_path "$memory_dir" "$run_id")"
  [ -f "$rollout" ] || {
    echo "Error: rollout not found: $rollout" >&2
    exit 1
  }

  ts="$(now_iso)"
  summary="$(compare_run --memory-dir "$memory_dir" --run-id "$run_id")"
  path="$(decision_path "$memory_dir" "$run_id")"

  jq -n \
    --arg run_id "$run_id" \
    --arg decision "$decision" \
    --arg reason "$reason" \
    --arg approval_source "$approval_source" \
    --arg approved_by "$approved_by" \
    --arg decided_at "$ts" \
    --argjson comparison "$summary" \
    '{
      run_id: $run_id,
      decision: $decision,
      reason: $reason,
      approval_source: (if $approval_source == "" then null else $approval_source end),
      approved_by: (if $approved_by == "" then null else $approved_by end),
      decided_at: $decided_at,
      comparison: $comparison
    }' > "$path"

  printf '%s\n' "$path"
}

reject_edit() {
  require_jq

  local memory_dir="" run_id="" reason="" failed_cases="" avoid_next_time=""
  local target_skill="" affected_rule="" section="" edit_summary="" ts="" record="" candidate_file="" decision_file=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --memory-dir) memory_dir="$2"; shift 2 ;;
      --run-id) run_id="$2"; shift 2 ;;
      --reason) reason="$2"; shift 2 ;;
      --failed-cases) failed_cases="$2"; shift 2 ;;
      --avoid-next-time) avoid_next_time="$2"; shift 2 ;;
      --target-skill) target_skill="$2"; shift 2 ;;
      --affected-rule) affected_rule="$2"; shift 2 ;;
      --section) section="$2"; shift 2 ;;
      --edit-summary) edit_summary="$2"; shift 2 ;;
      *) echo "Unknown arg: $1" >&2; usage ;;
    esac
  done

  [ -n "$memory_dir" ] || usage
  [ -n "$run_id" ] || usage
  [ -n "$reason" ] || usage
  [ -n "$failed_cases" ] || usage
  [ -n "$avoid_next_time" ] || usage

  ensure_optimization_dir "$memory_dir"
  [ -n "$target_skill" ] || target_skill="$(load_rollout_field "$memory_dir" "$run_id" ".target_skill")"
  [ -n "$section" ] || section="unknown"
  [ -n "$affected_rule" ] || affected_rule="$section"
  [ -n "$edit_summary" ] || edit_summary="unknown"
  ts="$(now_iso)"
  candidate_file="$(candidate_json_path "$memory_dir" "$run_id")"
  decision_file="$(decision_path "$memory_dir" "$run_id")"

  record="$(
    jq -cn \
      --arg run_id "$run_id" \
      --arg timestamp "$ts" \
      --arg target_skill "$target_skill" \
      --arg affected_rule "$affected_rule" \
      --arg section "$section" \
      --arg edit_summary "$edit_summary" \
      --arg rejection_reason "$reason" \
      --arg failed_cases "$failed_cases" \
      --arg avoid_next_time "$avoid_next_time" \
      --arg candidate_file "$candidate_file" \
      --arg decision_file "$decision_file" \
      '{
        run_id: $run_id,
        timestamp: $timestamp,
        target_skill: $target_skill,
        affected_rule: $affected_rule,
        section: $section,
        edit_summary: $edit_summary,
        rejection_reason: $rejection_reason,
        failed_cases: ($failed_cases | split(",") | map(select(. != ""))),
        failed_case_ids: ($failed_cases | split(",") | map(select(. != ""))),
        candidate_file: $candidate_file,
        decision_file: $decision_file,
        avoid_next_time: $avoid_next_time
      }'
  )"

  printf '%s\n' "$record" >> "$memory_dir/optimization/rejected-edits.jsonl"
  record_decision --memory-dir "$memory_dir" --run-id "$run_id" --decision rejected --reason "$reason" >/dev/null
  printf '%s\n' "$record"
}

accept_edit() {
  require_jq

  local memory_dir="" run_id="" best_skill_path="" target_skill="" approval_source="" approved_by="" ts="" best_dir="" best_file="" manifest=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --memory-dir) memory_dir="$2"; shift 2 ;;
      --run-id) run_id="$2"; shift 2 ;;
      --best-skill-path) best_skill_path="$2"; shift 2 ;;
      --approval-source) approval_source="$2"; shift 2 ;;
      --approved-by) approved_by="$2"; shift 2 ;;
      --target-skill) target_skill="$2"; shift 2 ;;
      *) echo "Unknown arg: $1" >&2; usage ;;
    esac
  done

  [ -n "$memory_dir" ] || usage
  [ -n "$run_id" ] || usage
  [ -n "$best_skill_path" ] || usage
  [ -n "$approval_source" ] || usage
  [ -n "$approved_by" ] || usage
  [ -f "$best_skill_path" ] || {
    echo "Error: best skill path not found: $best_skill_path" >&2
    exit 1
  }

  ensure_optimization_dir "$memory_dir"
  [ -n "$target_skill" ] || target_skill="$(load_rollout_field "$memory_dir" "$run_id" ".target_skill")"
  ts="$(now_iso)"
  best_dir="$memory_dir/optimization/best"
  best_file="$best_dir/$target_skill.SKILL.md"
  manifest="$best_dir/manifest.json"

  cp "$best_skill_path" "$best_file"
  jq -n \
    --arg target_skill "$target_skill" \
    --arg run_id "$run_id" \
    --arg source_skill_path "$best_skill_path" \
    --arg checkpoint_path "$best_file" \
    --arg approval_source "$approval_source" \
    --arg approved_by "$approved_by" \
    --arg accepted_at "$ts" \
    '{
      target_skill: $target_skill,
      run_id: $run_id,
      source_skill_path: $source_skill_path,
      checkpoint_path: $checkpoint_path,
      approval_source: $approval_source,
      approved_by: $approved_by,
      accepted_at: $accepted_at
    }' > "$manifest"

  record_decision --memory-dir "$memory_dir" --run-id "$run_id" --decision accepted --reason "approved_checkpoint" --approval-source "$approval_source" --approved-by "$approved_by" >/dev/null
  printf '%s\n' "$manifest"
}

case "$command" in
  init-run) init_run "$@" ;;
  split-evals) split_evals "$@" ;;
  record-rollout) record_rollout "$@" ;;
  record-candidate) record_candidate "$@" ;;
  compare-run) compare_run "$@" ;;
  compare-heldout) compare_run "$@" ;;
  record-decision) record_decision "$@" ;;
  reject-edit) reject_edit "$@" ;;
  accept-edit) accept_edit "$@" ;;
  *) usage ;;
esac
