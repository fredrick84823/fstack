# Improve Signal Digest Prompt

You are generating a review-only digest for the `improve` skill memory system.

## Goal

Read the current improve signal sources, summarize new and unresolved signals,
cluster repeated gaps, and produce a dated markdown report for human review.

This workflow reduces review cost. It must not change long-term skill behavior
without explicit human approval.

## Inputs

Primary sources:

- `~/.agents/skills/improve/signal-queue.md` — sole authority for current lifecycle status
- `~/.agents/skills/improve/memory/signals.jsonl` — immutable raw evidence; its legacy `status` is capture-time only
- `~/.agents/skills/improve/memory/transitions.jsonl` — append-only decision evidence

Useful context, only if needed:

- `~/.agents/skills/improve/SKILL.md`
- `~/.agents/skills/improve/memory/claims/`
- `~/.agents/skills/improve/memory/eval-cases/`
- `~/.agents/skills/improve/memory/worklists/`
- `~/.agents/skills/improve/memory/optimization/rejected-edits.jsonl`

Do not read private-sensitive directories or unrelated private communications.

## Output

Write one markdown report to:

`~/.agents/skills/improve/memory/digests/YYYY-MM-DD-improve-signal-digest.md`

Use the current local date for `YYYY-MM-DD`.

If there are no meaningful new or unresolved signals, still write a short report
that says no action is recommended.

## Strict Non-Goals

Do not modify:

- Any `SKILL.md`
- `signal-queue.md`
- `memory/signals.jsonl`
- `memory/claims/`
- `memory/eval-cases/`
- `memory/worklists/`
- `memory/optimization/`
- Any signal status, resolution metadata, queue status, or approval decision

Do not mark items as resolved or rejected.

Do not create candidate patches.

Do not run optimization rollouts.

Do not send Slack messages, emails, or external notifications.

## Analysis Rules

Use source evidence from the queue and JSONL records. Separate facts from
inference.

Build the actionable/unresolved set only from `signal-queue.md` entries whose
current status is `pending`. Never union queue pending entries with JSONL or
skill-graph pending records. Use JSONL, transitions, claims, and eval cases only
as historical evidence for the queue-selected signals.

Classify findings into:

- Candidate improvement: likely reusable skill-rule gap
- Duplicate or already covered: similar to existing signal, claim, or rule
- Needs human decision: recurring issue, but policy/product boundary is unclear
- Reject or low value: one-off issue, missing data, transient failure, or
  preference change

Prioritize candidates using:

1. Recurrence across signals or sessions
2. Clear target skill and affected rule
3. Clear expected behavior vs actual behavior
4. Risk of future regression if ignored
5. Availability of evidence for an eval case

Prefer conservative triage. If the evidence is weak, put the item under "Needs
Human Decision" instead of recommending adoption.

## Report Format

Use this structure:

```md
# Improve Signal Digest - YYYY-MM-DD

## Summary

- New or unresolved signals reviewed: N
- Candidate improvements: N
- Duplicates or already covered: N
- Needs human decision: N
- Reject or low value: N

## Recommended Approval Queue

| Priority | Target skill | Gap | Evidence | Suggested next step |
|---|---|---|---|---|
| P1 | skill-name | Short gap summary | signal ids / queue headings | Ask <maintainer> to approve creating or updating a rule/eval |

## Needs Human Decision

| Target skill | Question | Why it needs <maintainer> |
|---|---|---|

## Duplicates Or Already Covered

| Target skill | Signal | Existing coverage | Recommendation |
|---|---|---|---|

## Reject Or Low Value

| Target skill | Signal | Reason |
|---|---|---|

## Suggested Review Prompt

Paste-ready prompt <maintainer> can use to approve, reject, or ask for deeper review.

## Source Notes

- Files read:
- Important assumptions:
- Items intentionally not modified:
```

Keep the report concise but evidence-backed. Link to absolute local paths when
useful.

## Final Response

After writing the report, respond in Traditional Chinese with:

- The digest file path
- A short summary of recommended approvals
- A clear statement that no source queues, statuses, claims, evals, or skills
  were modified
