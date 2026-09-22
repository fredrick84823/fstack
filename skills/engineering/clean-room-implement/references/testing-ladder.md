# Testing ladder

Select the cheapest evidence that can falsify the changed behavior, then climb toward real boundaries. Existing repository commands and policies override generic examples.

Tests the implementer wrote for itself are excluded from every gate below. They run, and a
failing one blocks, but they cannot close an acceptance criterion or stand as discrimination
evidence—they were written by the same reasoning they would have to falsify.

## Inner loop

Run after initial implementation and every correction.

| Gate | Default | Selection rule |
|---|---:|---|
| Repository-native tests | required | Run the relevant unit/test command already maintained by the repo. |
| Acceptance/regression tests | required | Feature: prove acceptance criteria. Debug: reproduce the defect red, then green. |
| Lint/type/static checks | required when present | Run relevant native commands; do not invent substitute tooling. |
| Property testing | conditional | Use for parsers, codecs, state machines, pagination, normalization, arithmetic boundaries, and broad input spaces expressible as invariants. |

A property test needs an independently derived oracle or invariant. Rewriting the product algorithm as the reference model reproduces the same blind spot.

## Outer loop

Run after review is clean because these gates are slower or touch real boundaries.

| Gate | Selection rule |
|---|---|
| CRAP/coverage-complexity | Run when the repo has the tooling and changed logic is complex or weakly covered. Treat the result as a hotspot signal, not proof. |
| Mutation testing | Target changed functions, new branches, critical request construction, mock-heavy logic, or reviewer-identified weak tests. Avoid a full-repo run by default. Mutate a throwaway copy, never the candidate. |
| Integration testing | Run when the change crosses a database, API, filesystem, queue, process, container, auth, or external-service boundary. |
| `make verify` or equivalent | Run the repository's relevant local production-shape verification when it exists—for example a local container receiving simulated gateway upstream identity. |
| Falsification | For a critical contract, copy the repository to a scratch directory, break one key behavior there, and prove the test turns red. Skip when mutation evidence already demonstrates the same fact or when alteration is unsafe. Restoring an edited candidate is not an acceptable substitute for working in a copy. |
| Dogfood | Run when a user-observable workflow exists; see `dogfood.md`. |

## Mutation interpretation

Prefer targeted mutation over a ceremonial global percentage.

- `no-tests` on in-scope product code must reach zero.
- Compare against the function's prior baseline where available.
- Classify survivors as weak test, equivalent mutation, unreachable/dead code, or unresolved.
- Do not lower a threshold merely to make a gate pass.
- Record evidence for equivalent mutations instead of pretending they were killed.

## Real operations

Ask before commands that:

- mutate production or shared data;
- deploy or publish;
- send email/messages/notifications;
- incur meaningful external cost;
- require the user to authenticate or approve access.

A skipped real-system gate must say why and what remains unproved.

## Evidence format

For every selected gate, record:

```text
gate: <name>
selection: required | selected because <risk> | inapplicable because <evidence>
command or interaction: <exact action>
result: pass | fail | blocked
candidate: <patch checksum or commit>
evidence: <counts, output path, screenshot, response, or failing assertion>
```

Do not convert an unavailable check into a pass.
