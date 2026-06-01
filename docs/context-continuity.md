# Context Continuity

Agent work often fails at session boundaries: chat history disappears, repo
state moves on, and the next agent either re-reads too much or trusts stale
instructions. `fstack` treats handoff as a first-class workflow artifact rather
than a note at the end of a session.

## Workflow

```text
research-codebase / create-plan
        |
        v
implement-plan
        |
        v
create-handoff
        |
        v
resume-handoff
        |
        v
verify current repo state before continuing
```

## Why This Exists

Long-running agent work needs two properties:

- **Continuity**: the next session should understand the task, decisions,
  artifacts, and unfinished work without reconstructing everything from chat.
- **Freshness**: the next session must verify that the handoff still matches the
  current repository state before continuing.

`create-handoff` captures the session into a structured document.
`resume-handoff` reads the document, extracts tasks and artifacts, checks the
current codebase, and presents a continuation plan before making changes.

## Handoff Contract

A useful handoff should contain:

- Task status: completed, in progress, planned, and blocked work.
- Critical references: the few files the next agent must inspect first.
- Recent changes: file-level or line-level summary of what changed.
- Learnings: constraints, root causes, design decisions, and local patterns.
- Artifacts: exhaustive list of created or modified files.
- Next steps: concrete continuation actions in dependency order.

See [examples/handoff.md](../examples/handoff.md).

## Resume Contract

Resuming from a handoff is not a blind replay. The next agent should:

- Read the full handoff.
- Verify referenced files and repository state.
- Identify divergence between the handoff and current code.
- Present findings and recommended next actions before implementation.
- Reuse documented learnings instead of rediscovering them.

## Design Principles

- **Handoff is an interface**: it should be concise enough to scan and complete
  enough to let a new agent continue.
- **Verification beats memory**: current repository state is the source of
  truth.
- **Artifacts are evidence**: list paths, commands, and validation outputs so the
  next session can inspect them.
- **Plan status belongs in the handoff**: the next agent should not need to
  re-read an entire plan just to learn which phase is active.
