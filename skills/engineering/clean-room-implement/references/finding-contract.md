# Findings and completion report

## Finding record

Normalize every review, verification, and dogfood problem without flattening its origin:

```text
id: CL-R<round>-<number>
source: code-review/spec | code-review/standards | ponytail-review | interrogate | test | integration | dogfood
location: file:line, public surface, or runtime boundary
claim: one concrete problem
evidence: execution path, violated spec/rule, failing assertion, or observation
disposition: fix | dismiss | ask-user
reason: why this disposition is correct
owner: Implement | Test | user | none
status: open | resolved
verification: candidate and evidence proving resolution
```

## Adjudication rules

### Fix

Use when evidence shows incorrect behavior, a violated contract/standard, a meaningful current maintainability cost, or a verification defect.

Route product defects to Implement and verification defects to Test. Review and Dogfood agents remain read-only.

### Dismiss

Use when the finding is:

- contradicted by a reachable call path, type constraint, test, or repository rule;
- duplicate of another record;
- outside the agreed scope;
- a preference without concrete harm;
- based on missing context already captured in the shared contract.

Record the evidence. “Not important” is not enough.

### Ask user

Use when resolution changes product intent, accepts a meaningful residual risk, adds scope, makes an irreversible choice, or trades one user group against another.

Do not ask the user for repository facts that agents can inspect.

## Blocking policy

Block completion on:

- failing required verification;
- concrete Spec or documented Standards violations;
- correctness, security, privacy, data-loss, or irreversible-operation findings;
- unresolved `Act On` findings from interrogate;
- dogfood bugs or spec gaps without disposition;
- missing required review skill or role independence;
- a final candidate that changed after its last review or verification.

Ponytail suggestions and interrogate `Consider` items require disposition but are not automatically blockers.

## Final report

Use exactly this shape:

```markdown
## Outcome
PASS | BLOCKED | USER DECISION NEEDED

Candidate: <commit or patch checksum>
Intent: <user goal, not a diff summary>
Rounds: <number>

## Changes
- <scoped behavior delivered>

## Verification
| Gate | Selection | Result | Evidence |
|---|---|---|---|
| ... | ... | ... | ... |

## Review
| Source / axis | Fixed | Dismissed | Open | Worst remaining issue |
|---|---:|---:|---:|---|
| ... | ... | ... | ... | ... |

## Dogfood
- Journey: <what the fresh agent attempted, or why inapplicable>
- Observations: <resolved/dismissed/open summary>
- Evidence: <paths or runtime details>

## Residual risk
- <what remains unproved; “none identified” only when justified>

## Finding ledger
- `<id>` — `<disposition>`: <one-line claim and resolution/reason>
```

Do not say “all tests passed” when only a subset ran. Name the selected gates and the unchanged candidate they proved.
