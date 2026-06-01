---
name: skill-memory-reflect
description: >
  Reflect on /improve Skill Evolution Memory. Use when the user asks to process
  accumulated improve signals, deduplicate skill gaps, generate or refresh
  memory/claims/{skill}.md, generate memory/eval-cases/{skill}.json, enrich
  old memory records, or produce a prioritized /improve worklist from
  signals.jsonl.
---

# Skill Memory Reflect

Turn raw `/improve` memory events into reviewable skill-evolution artifacts. Use this skill after hooks or migrations have written `memory/signals.jsonl` and the user wants recurring gaps consolidated into concrete claims, eval cases, and implementation priorities.

## Workflow

1. Locate the improve memory directory. Prefer an explicit `--memory-dir`; otherwise use `/Users/fredrick/.agents/skills/improve/memory` for installed user memory, or `skills/improve/memory` when working inside a repo fixture.
2. Run a dry reflection package first:

```bash
python3 skills/skill-memory-reflect/scripts/reflect_memory.py --memory-dir /Users/fredrick/.agents/skills/improve/memory --dry-run
```

3. Review the summary. Check especially groups whose `affected_rule` or `gap_type` was inferred from low-confidence text. If the result is noisy, narrow with `--target-skill <skill>`.
4. Write artifacts only after the dry run looks coherent:

```bash
python3 skills/skill-memory-reflect/scripts/reflect_memory.py --memory-dir /Users/fredrick/.agents/skills/improve/memory --write
```

5. Use the generated worklist to drive `/improve` changes. Do not automatically edit target skills from this reflection alone; treat claims and eval cases as a review package.

## Outputs

The script writes derived artifacts under the selected memory directory:

- `claims/{skill}.md`: deduplicated candidate claims with evidence, inferred expected and actual behavior, risk notes, and proposed rule updates.
- `eval-cases/{skill}.json`: A/B/C/D eval cases grounded in signal evidence. A and B cover recall/regression; C covers downstream or workflow impact; D is a false-positive trap.
- `worklists/YYYYMMDDTHHMMSSZ-skill-memory-reflect.md`: prioritized `/improve` worklist across skills.
- `skill-graph.json`: refreshed claim and eval-case indexes.

## Reflection Rules

- Preserve `signals.jsonl` as the raw source of truth. Do not delete or rewrite raw records.
- Group signals by target skill, inferred affected rule, inferred gap type, and normalized gap text. Use repeated evidence to prioritize, but keep single high-risk signals visible.
- Prefer explicit fields from memory records. Infer missing `affected_rule`, `gap_type`, `expected_behavior`, and `actual_behavior` from `gap` text only when the original record has `unknown` or empty values.
- Flag low-confidence groups instead of hiding them. Many backfilled signals are useful even when old records lack structured fields.
- Generate eval cases that test both sides of the rule: a positive recall case and a clean/trap case that must not emit a new GAP.
- Leave queue status changes to `/improve` or a human review step. Reflection produces derived recommendations; it does not mark pending signals resolved.

## Script Notes

`scripts/reflect_memory.py` is deterministic and does not call external services. It uses heuristic text normalization so an agent can perform the semantic review around it instead of reimplementing parsing and file writing each time.
