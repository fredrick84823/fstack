# Skill Evolution Loop

`fstack` treats workflow failures as evidence for improving the skill system.
The goal is not to let agents rewrite themselves freely. The goal is to capture
repeated failures, consolidate them into reviewable claims, test the proposed
behavior, and only then update durable skill rules.

## Workflow

```text
User correction / repeated failure
        |
        v
<<GAP skill-name: description>>
        |
        v
Stop hook captures the signal
        |
        v
signal-queue.md + memory/signals.jsonl
        |
        v
skill-memory-reflect consolidates claims + eval cases
        |
        v
/improve proposes a SKILL.md update
        |
        v
human gate
        |
        v
skill rule updated + changelog
```

## Components

| Component | Role |
|-----------|------|
| `<<GAP ...>>` marker | Lightweight signal emitted when a reusable skill rule gap is found |
| Stop hook | Captures markers into queue and memory files |
| `signal-queue.md` | Human-readable pending review queue |
| `memory/signals.jsonl` | Raw append-only event log |
| `skill-memory-reflect` | Consolidates raw events into claims, eval cases, and worklists |
| `/improve` | Performs attribution, proposes rule changes, and runs review gates |
| `changelog.md` | Append-only history of accepted skill changes |

## Signal Precision

Not every correction is a skill gap. A signal should only be captured when all
three are true:

- A target skill can be identified.
- The issue points to a reusable rule gap, not a one-off preference.
- Expected behavior and actual behavior can be stated.

Examples that should not become durable skill changes:

- The user changes the audience or tone for a single output.
- Required data did not exist when the skill ran.
- An external service failed because of credentials, quota, or network access.

## Reflection Layer

Raw hook capture is not the final state. `skill-memory-reflect` creates a review
package from accumulated memory:

- `claims/{skill}.md`: deduplicated candidate claims with evidence.
- `eval-cases/{skill}.json`: recall, precision, state transition, and trap
  cases for the proposed rule.
- `worklists/*.md`: prioritized `/improve` implementation queue.
- `skill-graph.json`: compact lookup index for related signals and eval cases.

See [examples/skill-memory-claim.md](../examples/skill-memory-claim.md) and
[examples/eval-cases.json](../examples/eval-cases.json).

## Human Gate

Durable mutation requires review. `/improve` may propose a `SKILL.md` edit, but
the user decides whether to approve, reject, or modify the proposal. This keeps
the system adaptive without allowing noisy or accidental self-modification.

## What This Demonstrates

- Evaluation-aware agent workflow design.
- Practical false-positive control.
- Separation of raw telemetry, reflected knowledge, and durable rules.
- Scope-aware mutation across user, project, and repository skill layers.
