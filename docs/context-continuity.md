# Context Continuity

Agent work often fails at session boundaries: chat history disappears, repo
state moves on, and the next agent either re-reads too much or trusts stale
instructions. `fstack` treats handoff as a first-class workflow artifact rather
than a note at the end of a session.

## Workflow

```text
ask-codebase-questions
        |
        v
research-codebase
        |
        v
design-concept
        |
        v
structure-outline
        |
        v
create-plan
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

For small or low-risk changes, `research-and-plan` can still compress research
and planning. For non-trivial code work, prefer the explicit artifact chain.

## Why This Exists

Long-running agent work needs two properties:

- **Continuity**: the next session should understand the task, decisions,
  artifacts, and unfinished work without reconstructing everything from chat.
- **Freshness**: the next session must verify that the handoff still matches the
  current repository state before continuing.

`create-handoff` captures the session into a structured document.
`resume-handoff` reads the document, extracts tasks and artifacts, checks the
current codebase, and presents a continuation plan before making changes.

## Why The Development Flow Changed

The original workflow in this repo was effectively Research → Plan → Implement.
That shape was useful, but it made the plan too central: agents could produce
large plans that drifted from the actual code, and humans could end up reviewing
plans instead of the code and architecture.

The current flow splits alignment into smaller artifacts:

- **Questions**: define code-answerable unknowns and human questions before
  research.
- **Research**: document current code behavior from questions only. In
  hidden-requirement mode, do not pass the proposed solution into research
  prompts.
- **Design Concept**: align on current state, desired state, tradeoffs, and
  patterns to follow or avoid.
- **Structure Outline**: define interfaces, signatures, type contracts, and
  vertical slices before tactical planning.
- **Plan / Implement**: write the execution plan only after architecture is
  aligned, then implement and verify each slice.

This keeps each step small enough to inspect, moves human review earlier to the
architecture shape, and preserves the expectation that production code must be
read and owned directly.

Source:
- Dexter Horthy, [Everything We Got Wrong About Research-Plan-Implement](https://www.youtube.com/watch?v=YwZR6tc7qYg).
- The public interview summary [Making AI Agents Mainstream with Dexter Horthy](https://thehumansintheloop.substack.com/p/making-agents-mainstream-for-dev-with-dexter-horthy)
  describes the shift from the original Research / Plan / Implement workflow to
  a smaller staged pipeline of Questions, Research, Design, Structure, Plan,
  Worktree, and Implement.

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
