---
name: design-concept
description: Create a concise Design Concept artifact after questions and codebase research are available. Use for CRISPY/QRSPI Design phase, architecture alignment, feature design discussion, or turning current-state research into a small human-reviewable proposed shape before detailed planning.
allowed-tools: Read, Write, Edit, Bash
---

# Design Concept

Create a small design proposal for human/agent architecture alignment. This is
not a tactical implementation plan.

## Inputs

Read the task, Questions artifact, human answers, and research document if
provided. If current code behavior is still unclear, run `research-codebase`
with question-only prompts before designing.

## Write Design Concept

Aim for about 100-200 lines maximum.

Path:
- If `thoughts/` exists: `thoughts/shared/qds/YYYY-MM-DD-description-design.md`
- Otherwise: `qds/YYYY-MM-DD-description-design.md`

Rules:
- State current state and desired state.
- Name the primary tradeoffs and preferred direction.
- Call out patterns to follow and patterns to avoid.
- Include only enough detail to align architecture.
- Do not write step-by-step implementation tasks.

Template:

```markdown
# Design Concept: [Task]

## Goal

## Current State
- `path:line` - [fact]

## Desired State

## Proposed Shape

## Patterns to Follow

## Patterns to Avoid

## Risks / Tradeoffs

## Open Alignment Points
```

## Hand Off

If the design direction is uncertain, stop for human adjustment. If aligned,
recommend:

```text
Next: /structure-outline <design-concept-path>
```
