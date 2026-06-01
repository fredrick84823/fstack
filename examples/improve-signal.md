# Improve Signal Example

This example shows how a reusable workflow gap becomes reviewable evidence.

## User Correction

```text
You forgot to verify the current repository state before resuming from the
handoff. That should happen every time, not just for this task.
```

## Agent Marker

The assistant emits a marker at the end of the response:

```text
<<GAP resume-handoff: resume workflow must verify current repository state before continuing from a handoff>>
```

## Captured Queue Entry

The Stop hook appends:

```markdown
## [2026-05-30T17:42:00+08:00] resume-handoff

- **type**: S2
- **source**: agent auto-detected
- **gap**: resume workflow must verify current repository state before continuing from a handoff
- **status**: pending
```

## Memory Event

The hook also writes a structured event to `memory/signals.jsonl`:

```json
{
  "signal_id": "sig_20260530_174200_resume_handoff",
  "target_skill": "resume-handoff",
  "affected_rule": "Resume verification",
  "gap_type": "missing_validation_step",
  "expected_behavior": "verify repository state before continuing from a handoff",
  "actual_behavior": "trusted handoff context without verifying current state",
  "evidence_count": 1,
  "status": "pending"
}
```

## Review Path

`skill-memory-reflect` later groups this signal with related evidence and
generates candidate claims and eval cases. `/improve` can then propose a
specific `SKILL.md` rule update for human review.
