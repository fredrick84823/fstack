#!/usr/bin/env python3
"""Reflect /improve Skill Evolution Memory into claims, eval cases, and worklists."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


STOPWORDS = {
    "the",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "for",
    "with",
    "when",
    "should",
    "skill",
    "應",
    "應該",
    "加入",
    "需要",
    "避免",
    "使用",
    "不是",
    "而是",
    "應主動",
}

RULE_PATTERNS = [
    ("Signal Collection", ["signal collection", "emit gap", "gap", "信號", "signal"]),
    ("Workflow Steps", ["step", "workflow", "流程", "標準流程", "步驟"]),
    ("Verification", ["verify", "validation", "e2e", "測試", "驗證", "dry run"]),
    ("Troubleshooting", ["troubleshooting", "debug", "diagnostic", "診斷", "調查"]),
    ("Output Contract", ["output", "format", "schema", "section", "報告", "格式", "輸出"]),
    ("Triggering", ["trigger", "觸發", "主動使用", "應自動"]),
    ("Scope Resolution", ["scope", "path", "路徑", "目錄", "whiteboard", "section"]),
]

GAP_TYPE_PATTERNS = [
    ("false_positive", ["false positive", "誤判", "不應標", "不得標", "不要標", "不應 emit", "do not emit", "clean/trap"]),
    ("false_negative", ["漏", "少了", "未", "沒有", "應主動", "應自動", "forgot"]),
    ("workflow_gap", ["流程", "step", "workflow", "標準", "runbook", "mode"]),
    ("verification_gap", ["測試", "驗證", "e2e", "dry run", "benchmark", "確認"]),
    ("output_contract_gap", ["format", "schema", "section", "欄位", "格式", "標示", "顯示"]),
    ("tooling_gap", ["script", "tool", "command", "指令", "mcp", "hook", "plugin"]),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--memory-dir", required=True, type=Path)
    parser.add_argument("--target-skill", default="")
    parser.add_argument("--min-evidence", type=int, default=2)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Print summary without writing artifacts")
    mode.add_argument("--write", action="store_true", help="Write derived artifacts")
    return parser.parse_args()


def load_signals(memory_dir: Path) -> list[dict[str, Any]]:
    signals_path = memory_dir / "signals.jsonl"
    if not signals_path.exists():
        return []

    records: list[dict[str, Any]] = []
    with signals_path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{signals_path}:{line_no}: invalid JSON: {exc}") from exc
            if isinstance(record, dict):
                records.append(record)
    return records


def field(record: dict[str, Any], name: str, default: str = "") -> str:
    value = record.get(name, default)
    if value is None:
        return default
    return str(value).strip()


def pick_pattern(text: str, existing: str, patterns: list[tuple[str, list[str]]], fallback: str) -> tuple[str, str]:
    if existing and existing != "unknown":
        return existing, "explicit"

    lowered = text.lower()
    for label, needles in patterns:
        if any(needle.lower() in lowered for needle in needles):
            return label, "inferred"
    return fallback, "low_confidence"


def normalize_text(text: str) -> str:
    words = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+", text.lower())
    kept = [word for word in words if word not in STOPWORDS and len(word) > 1]
    return " ".join(kept[:16]) or "unknown"


def short_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def claim_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value.lower()).strip("_")
    return slug or "unknown"


def safe_filename(value: str) -> str:
    name = re.sub(r"[\\/:\0]+", "_", value).strip()
    return name or "unknown"


def enrich(record: dict[str, Any]) -> dict[str, Any]:
    gap = field(record, "gap")
    combined = " ".join(
        part
        for part in [
            gap,
            field(record, "expected_behavior"),
            field(record, "actual_behavior"),
            field(record, "source"),
        ]
        if part
    )
    affected_rule, rule_source = pick_pattern(
        combined,
        field(record, "affected_rule", "unknown"),
        RULE_PATTERNS,
        "Unknown Rule",
    )
    gap_type, gap_type_source = pick_pattern(
        combined,
        field(record, "gap_type", "unknown"),
        GAP_TYPE_PATTERNS,
        "unknown",
    )
    expected_behavior = field(record, "expected_behavior") or infer_expected(gap, affected_rule, gap_type)
    actual_behavior = field(record, "actual_behavior") or infer_actual(gap, gap_type)

    return {
        **record,
        "target_skill": field(record, "target_skill", "unknown"),
        "affected_rule": affected_rule,
        "affected_rule_source": rule_source,
        "gap_type": gap_type,
        "gap_type_source": gap_type_source,
        "expected_behavior": expected_behavior,
        "actual_behavior": actual_behavior,
        "gap": gap,
        "signal_id": field(record, "signal_id", short_hash(json.dumps(record, sort_keys=True))),
        "timestamp": field(record, "timestamp"),
        "status": field(record, "status", "pending"),
    }


def infer_expected(gap: str, affected_rule: str, gap_type: str) -> str:
    if gap_type == "false_positive":
        return f"`{affected_rule}` should abstain for clean or one-off cases that do not prove a reusable skill rule gap."
    if gap_type == "false_negative":
        return f"`{affected_rule}` should explicitly detect and handle this recurring gap."
    if gap_type == "verification_gap":
        return f"`{affected_rule}` should include a repeatable verification step for this scenario."
    if gap_type == "output_contract_gap":
        return f"`{affected_rule}` should define the expected output structure clearly enough for downstream use."
    return f"`{affected_rule}` should document the repeatable behavior implied by this signal."


def infer_actual(gap: str, gap_type: str) -> str:
    if gap:
        return gap
    if gap_type == "false_positive":
        return "The current rule may over-trigger on cases that should be ignored."
    if gap_type == "false_negative":
        return "The current workflow may miss a recurring skill gap."
    return "The current skill instructions do not yet cover this signal clearly."


def group_signals(records: list[dict[str, Any]], target_skill: str) -> list[dict[str, Any]]:
    enriched = [enrich(record) for record in records]
    if target_skill:
        enriched = [record for record in enriched if record["target_skill"] == target_skill]

    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in enriched:
        signature = group_signature(record)
        key = (record["target_skill"], record["affected_rule"], record["gap_type"], signature)
        groups[key].append(record)

    reflected: list[dict[str, Any]] = []
    for (skill, rule, gap_type, signature), members in groups.items():
        evidence_count = len(members)
        confidence_flags = sorted(
            {
                flag
                for member in members
                for flag in [member["affected_rule_source"], member["gap_type_source"]]
                if flag != "explicit"
            }
        )
        priority = score_priority(evidence_count, gap_type, confidence_flags)
        claim_id = "claim_{}_{}_{}_{}".format(
            claim_slug(skill),
            claim_slug(rule),
            claim_slug(gap_type),
            short_hash("|".join(member["signal_id"] for member in members)),
        )
        reflected.append(
            {
                "claim_id": claim_id,
                "target_skill": skill,
                "affected_rule": rule,
                "gap_type": gap_type,
                "signature": signature,
                "priority": priority,
                "confidence": "low" if "low_confidence" in confidence_flags else "medium" if confidence_flags else "high",
                "evidence_count": evidence_count,
                "signal_ids": [member["signal_id"] for member in members],
                "latest_signal_at": max([member["timestamp"] for member in members if member["timestamp"]] or [""]),
                "expected_behavior": choose_longest(member["expected_behavior"] for member in members),
                "actual_behavior": choose_longest(member["actual_behavior"] for member in members),
                "example_gap": choose_longest(member["gap"] for member in members),
                "members": members,
            }
        )

    return sorted(reflected, key=lambda item: (-item["priority"], item["target_skill"], item["affected_rule"]))


def group_signature(record: dict[str, Any]) -> str:
    if record["affected_rule_source"] == "explicit" and record["gap_type_source"] == "explicit":
        return normalize_text(record["gap"] or record["actual_behavior"])
    if record["affected_rule"] == "Unknown Rule" or record["gap_type"] == "unknown":
        return normalize_text(record["gap"] or record["actual_behavior"])
    return "inferred-bucket"


def choose_longest(values: Any) -> str:
    clean = [str(value).strip() for value in values if str(value).strip()]
    return max(clean, key=len) if clean else ""


def score_priority(evidence_count: int, gap_type: str, confidence_flags: list[str]) -> int:
    score = evidence_count * 10
    if gap_type in {"false_positive", "false_negative", "workflow_gap", "verification_gap"}:
        score += 5
    if "low_confidence" in confidence_flags:
        score -= 3
    return max(score, 1)


def claim_status(group: dict[str, Any], min_evidence: int) -> str:
    if group["evidence_count"] >= min_evidence:
        return "candidate"
    if group["priority"] >= 15:
        return "candidate"
    return "accumulate"


def render_claims(skill: str, groups: list[dict[str, Any]], min_evidence: int) -> str:
    candidate_groups = [group for group in groups if claim_status(group, min_evidence) == "candidate"]
    accumulating_groups = [group for group in groups if claim_status(group, min_evidence) != "candidate"]

    lines = [
        f"# {skill} Skill Evolution Claims",
        "",
        "Generated by `skill-memory-reflect/scripts/reflect_memory.py` from raw Skill Evolution Memory. Treat these as review candidates; only `/improve` or human review should rewrite target skills or resolve source signals.",
        "",
        "## Candidate Claims",
        "",
    ]
    if not candidate_groups:
        lines.append("No candidate claims met the current threshold.")
    for group in candidate_groups:
        lines.extend(render_claim_group(group))

    lines.extend(["", "## Accumulating Signals", ""])
    if not accumulating_groups:
        lines.append("No accumulating signals.")
    for group in accumulating_groups:
        lines.append(
            "- **{}**: `{}` / `{}`, evidence_count={}, confidence={}, signals={}".format(
                group["claim_id"],
                group["affected_rule"],
                group["gap_type"],
                group["evidence_count"],
                group["confidence"],
                ", ".join(group["signal_ids"]),
            )
        )

    lines.extend(["", "## Superseded Claims", "", "No superseded claims recorded by this reflection run."])
    return "\n".join(lines) + "\n"


def render_claim_group(group: dict[str, Any]) -> list[str]:
    return [
        f"### {group['claim_id']}",
        "",
        f"- **Priority**: {group['priority']}",
        f"- **Affected rule**: `{group['affected_rule']}`",
        f"- **Gap type**: `{group['gap_type']}`",
        f"- **Confidence**: {group['confidence']}",
        f"- **Evidence**: {group['evidence_count']} signal(s): {', '.join(group['signal_ids'])}",
        f"- **Expected behavior**: {group['expected_behavior']}",
        f"- **Actual behavior**: {group['actual_behavior']}",
        f"- **Proposed update**: Update `{group['target_skill']}` so `{group['affected_rule']}` handles this recurring scenario without creating false positives.",
        f"- **Eval plan**: Add recall and regression cases from `{group['claim_id']}` before resolving source signals.",
        "",
    ]


def eval_cases_for_group(group: dict[str, Any]) -> list[dict[str, Any]]:
    base = {
        "source_claim": group["claim_id"],
        "target_skill": group["target_skill"],
        "affected_rule": group["affected_rule"],
        "gap_type": group["gap_type"],
        "evidence_signals": group["signal_ids"],
    }
    return [
        {
            **base,
            "id": f"eval_{group['claim_id']}_A_recall",
            "prototype": "A",
            "prompt": f"Run `{group['target_skill']}` on a task where this recurring gap appears: {group['example_gap']}",
            "expected_output": f"The agent identifies the `{group['affected_rule']}` issue and applies the updated workflow or emits the intended GAP.",
        },
        {
            **base,
            "id": f"eval_{group['claim_id']}_B_regression",
            "prototype": "B",
            "prompt": f"Run `{group['target_skill']}` on a normal task adjacent to `{group['affected_rule']}` but without the recorded failure.",
            "expected_output": "The agent completes the normal workflow without adding irrelevant steps or changing unrelated behavior.",
        },
        {
            **base,
            "id": f"eval_{group['claim_id']}_C_downstream",
            "prototype": "C",
            "prompt": f"Use the output of `{group['target_skill']}` in the next downstream workflow that depends on `{group['affected_rule']}`.",
            "expected_output": "The downstream workflow receives enough structure or verification to avoid rediscovering the same gap.",
        },
        {
            **base,
            "id": f"eval_{group['claim_id']}_D_false_positive_trap",
            "prototype": "D",
            "prompt": f"Run `{group['target_skill']}` on a one-off user preference change mentioning similar words: {group['signature']}",
            "expected_output": "The agent does not treat a one-off preference, missing data, or external failure as a reusable skill gap.",
        },
    ]


def render_worklist(groups: list[dict[str, Any]], min_evidence: int, generated_at: str) -> str:
    lines = [
        "# Skill Memory Reflect Worklist",
        "",
        f"Generated at: `{generated_at}`",
        "",
        "## Priority Queue",
        "",
    ]
    candidates = [group for group in groups if claim_status(group, min_evidence) == "candidate"]
    if not candidates:
        lines.append("No candidate claims met the current threshold.")
    for index, group in enumerate(candidates, start=1):
        lines.extend(
            [
                f"{index}. `/improve {group['target_skill']}` for `{group['affected_rule']}` / `{group['gap_type']}`",
                f"   - claim: `{group['claim_id']}`",
                f"   - priority: {group['priority']}, evidence_count: {group['evidence_count']}, confidence: {group['confidence']}",
                f"   - source signals: {', '.join(group['signal_ids'])}",
                f"   - expected: {group['expected_behavior']}",
                f"   - actual: {group['actual_behavior']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Review Notes",
            "",
            "- Check low-confidence inferred groups before editing any skill.",
            "- Keep raw `signals.jsonl` unchanged until `/improve` or human review resolves the source queue items.",
            "- Add or reuse A/B/C/D eval cases before merging rule changes.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_artifacts(memory_dir: Path, groups: list[dict[str, Any]], min_evidence: int, generated_at: str) -> dict[str, Any]:
    claims_dir = memory_dir / "claims"
    eval_dir = memory_dir / "eval-cases"
    worklists_dir = memory_dir / "worklists"
    claims_dir.mkdir(parents=True, exist_ok=True)
    eval_dir.mkdir(parents=True, exist_ok=True)
    worklists_dir.mkdir(parents=True, exist_ok=True)

    by_skill: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for group in groups:
        by_skill[group["target_skill"]].append(group)

    written_claims = []
    written_evals = []
    eval_index = []
    claim_index = []

    for skill, skill_groups in sorted(by_skill.items()):
        file_stem = safe_filename(skill)
        claims_path = claims_dir / f"{file_stem}.md"
        claims_path.write_text(render_claims(skill, skill_groups, min_evidence), encoding="utf-8")
        written_claims.append(str(claims_path))

        eval_cases = [
            case
            for group in skill_groups
            if claim_status(group, min_evidence) == "candidate"
            for case in eval_cases_for_group(group)
        ]
        eval_payload = {
            "skill_name": skill,
            "generated_at": generated_at,
            "generated_from": "Skill Evolution Memory reflected claims",
            "eval_cases": eval_cases,
        }
        eval_path = eval_dir / f"{file_stem}.json"
        eval_path.write_text(json.dumps(eval_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written_evals.append(str(eval_path))

        for group in skill_groups:
            claim_index.append(
                {
                    "claim_id": group["claim_id"],
                    "target_skill": group["target_skill"],
                    "affected_rule": group["affected_rule"],
                    "gap_type": group["gap_type"],
                    "status": claim_status(group, min_evidence),
                    "priority": group["priority"],
                    "evidence_count": group["evidence_count"],
                    "signal_ids": group["signal_ids"],
                }
            )
        eval_index.extend(
            {
                "id": case["id"],
                "target_skill": case["target_skill"],
                "source_claim": case["source_claim"],
                "prototype": case["prototype"],
            }
            for case in eval_cases
        )

    worklist_name = f"{generated_at.replace('-', '').replace(':', '')}-skill-memory-reflect.md"
    worklist_path = worklists_dir / worklist_name
    worklist_path.write_text(render_worklist(groups, min_evidence, generated_at), encoding="utf-8")

    graph_path = memory_dir / "skill-graph.json"
    graph = {"version": 1}
    if graph_path.exists():
        graph = json.loads(graph_path.read_text(encoding="utf-8") or "{}")
    graph["updated_at"] = generated_at
    graph["claims"] = claim_index
    graph["eval_cases"] = eval_index
    graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "claims": written_claims,
        "eval_cases": written_evals,
        "worklist": str(worklist_path),
        "skill_graph": str(graph_path),
    }


def main() -> int:
    args = parse_args()
    memory_dir = args.memory_dir.expanduser()
    records = load_signals(memory_dir)
    groups = group_signals(records, args.target_skill)
    generated_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    summary = {
        "memory_dir": str(memory_dir),
        "generated_at": generated_at,
        "input_signal_count": len(records),
        "reflected_group_count": len(groups),
        "candidate_count": sum(1 for group in groups if claim_status(group, args.min_evidence) == "candidate"),
        "target_skill": args.target_skill or None,
        "groups": [
            {
                "claim_id": group["claim_id"],
                "target_skill": group["target_skill"],
                "affected_rule": group["affected_rule"],
                "gap_type": group["gap_type"],
                "priority": group["priority"],
                "confidence": group["confidence"],
                "evidence_count": group["evidence_count"],
                "status": claim_status(group, args.min_evidence),
                "signal_ids": group["signal_ids"],
            }
            for group in groups
        ],
    }

    if args.write:
        summary["written"] = write_artifacts(memory_dir, groups, args.min_evidence, generated_at)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
