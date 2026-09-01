# Examples

Load when a section's shape is unclear. Each entry is the *move* — the reason that shape beats prose — not a template to copy.

## What problems was I solving

### Alternative the change beats

Do not open with the new thing. Open with why the incumbent cannot do the job, one row per limitation:

```markdown
| # | Limitation of the incumbent | Consequence | Does this PR fix it? |
|---|---|---|---|
| 1 | Requests rejected upstream leave no record | "someone keeps hitting the cap" is invisible | ✅ new `status="blocked"` row |
| 2 | 180-day retention ceiling | no year-over-year trend | ⚠️ partial — needs a separate export |
| — | Pricing conversion is notional under reservations | amounts are distorted | ❌ neither side solves this |
```

Then one sentence naming the leftover role of the incumbent. The table is the argument; the prose only names what the table does not.

Use when the PR is a design choice against a known alternative. Skip when there is no incumbent.

### Boundary the change must hold

When the PR exists to *keep* a boundary rather than add a capability, show the boundary as a table instead of asserting it in a paragraph:

```markdown
| Layer | May contain |
|---|---|
| private per-row table | full identity fields |
| aggregate view | — |
| **public export** | **hashed id only** |
```

### Ship-fact

End on a checkable fact, not a hope. "Run one query and within minutes that row appears in the sink, including the blocked ones" beats "this should give us visibility."

### Baseline

Measure the gap before claiming it. Two sources counted side by side, then a three-line conclusion, turns a blind spot from hypothesis into fact. Use when a reviewer could read the gap as speculative.

## What user-facing changes did I ship

No tool or return-shape change? Say so, then show what *is* the contract. When a payload is consumed downstream by schema inference, the payload **is** the contract — show it once, in full.

Otherwise: file + one clause of what that file now owns, then an explicit non-goal. Name the observable artifact (the URL, the log line, the new flag), not the infrastructure that produced it.

## How I implemented it

### Decisions, then shape

Draw the structure once — a tree, a three-line list — then isolate only the decisions that are not obvious from reading the diff: why this option is not optional, why there is no expiration, why the filter is pinned to one event type. Omit the rest of the file tour.

Across layers, the same move: each layer gets the one decision a reviewer would otherwise have to reverse-engineer.

For a single emitter with several call sites: why it lives on that class, why the body swallows exceptions, why amounts are floats, why the error type reads the cause chain. The control-flow rewrite is a short snippet, not a walk through every line.

### Cost of the choice

Price the rejected alternatives in a table, then name the *real* growth risk — which is often not the one the table is about. Use when the implementation is a cheaper path that looks like a missing one.

## Deviations from the plan

| Bucket | What goes here |
|---|---|
| Done per the issue | acceptance criteria that shipped |
| Added, not in the issue | extras + why they exist |
| In the issue, not done | left unchecked, pointed at verify |

The middle bucket is where a reviewer learns the most: "this manual acceptance criterion became a test, because the failure it guards cannot be undone" tells them more than the test file name.

Use when an issue or plan exists. Drop the heading when there is neither.

## How to verify it

Split what this branch can prove *now* from what needs apply/deploy.

- Unit tests are the prove-now bar; state the count.
- Infrastructure plans (`terraform plan` showing exactly N creates and nothing else) are prove-now; post-apply checks stay unchecked.
- An alert states what does not exist yet, and lists apply preconditions.
- The walkable path is a command a reviewer can run, with the expected before/after — e.g. a `curl` with no credentials, then an assertion that a forbidden field is absent.
