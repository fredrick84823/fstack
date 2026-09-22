# Review wave

Reviewers examine one frozen candidate independently and remain read-only. Run peers concurrently when possible so their conclusions do not contaminate one another.

Read-only covers experiments too. A reviewer never edits a file in the candidate repository—not to run a mutation, not to test a hypothesis, not even when it restores the original content afterwards. A reviewer that wants mutation evidence copies the repository elsewhere or records the request as a finding for the Test Agent.

## Required lenses

### code-review

Run the installed `code-review` skill against the fixed baseline and current candidate. Preserve its axes separately:

- **Spec**: missing/partial requirements, scope creep, and incorrect implementations.
- **Standards**: documented repository standards plus its smell baseline.

One axis passing never cancels a finding in the other.

### ponytail-review

Run the exact installed `ponytail-review` skill. It hunts only unnecessary complexity: dead flexibility, reinvention, unnecessary dependencies, speculative abstractions, and deletable code.

Treat its findings as judgment calls unless they identify concrete current cost. Preference-only shortening is dismissible with a reason; dead code, one-use speculative machinery, or a native/stdlib replacement with equal behavior usually merits a fix.

## Conditional lens: interrogate

Run the exact installed `interrogate` skill when either condition is true:

```text
run_interrogate = residual_reasoning_risk OR explicit_user_request
```

### Explicit request

The task contains `--deep`, `--interrogate`, or language asking for interrogate, adversarial/multi-model review, challenge, stress-testing, blind spots, tearing the change apart, `找盲點`, or `徹底審查`.

### Residual reasoning risk

Trigger when deterministic checks and ordinary review may still share one mental model, especially:

- security, authorization, privacy, tenant isolation;
- data loss, payment, destructive or irreversible behavior;
- concurrency, retries, idempotency, distributed state, or a complex state machine;
- migration or cross-system orchestration;
- silent failure, fallback to a plausible wrong result, or external protocol/API contracts;
- a production incident whose root cause remains uncertain;
- a new architectural seam with long-lived coupling;
- conflict between review lenses;
- surprising dogfood behavior suggesting the team's model is incomplete.

Diff size alone is not a trigger. A tiny auth change may be high-risk; a large generated diff may not be.

If `--no-interrogate` is present, skip ordinary-risk use. For security, data-loss, or irreversible risk, ask the user before suppressing it.

## Fan-out

Preferred shape:

```text
Frozen candidate
  ├─ code-review worker
  ├─ ponytail-review worker
  └─ interrogate worker (conditional)
```

Some skills spawn their own reviewers. If nested subagents are supported, let the skill preserve its native process. If not, the Orchestrator flattens the skill's reviewer seats into fresh peer agents. Never replace independent review with the main session reviewing its own orchestration.

## Consolidation

Normalize findings without erasing their origins or axes. Deduplicate only the underlying claim:

```text
CL-R2-01
sources: code-review/spec, interrogate/reviewer-B
location: src/example.py:42
claim: retry after partial write duplicates billing
evidence: <execution path>
```

Independent agreement increases confidence, not severity by itself. A single reviewer with a concrete execution path can still find a blocker. Several reviewers repeating a preference do not turn it into one.

Use `finding-contract.md` for dispositions.
