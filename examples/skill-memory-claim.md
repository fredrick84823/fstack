# Skill Memory Claim Example

This is a sanitized example of a reflected claim generated from raw improve
signals.

## Claim: Resume Handoff Must Verify Current Repository State

- **target_skill**: `resume-handoff`
- **affected_rule**: Resume verification
- **gap_type**: missing validation step
- **evidence_count**: 2
- **risk**: stale handoff can cause an agent to continue from outdated context
- **status**: candidate

## Evidence

1. User corrected the agent for trusting a handoff without checking current
   files.
2. A later resume session found that referenced files had changed after the
   handoff was written.

## Expected Behavior

When resuming from a handoff, the agent should read the handoff, inspect the
current repository state, compare referenced artifacts against the handoff, and
present divergence before implementation.

## Actual Behavior

The agent treated the handoff as authoritative and started planning without
first verifying current files or branch state.

## Proposed Rule Update

Add a mandatory "Verify Current State" step before continuation:

```markdown
Before implementation, run repository state checks and inspect critical
references from the handoff. If files or branch state diverge from the handoff,
present the divergence and adjust the continuation plan.
```

## Eval Ideas

- Recall case: handoff references a file that still exists but has changed.
- Precision case: handoff and repository state match; the skill should proceed
  without inventing divergence.
- Trap case: unrelated dirty files exist; the skill should mention them without
  blocking the handoff task unless they affect the referenced work.
