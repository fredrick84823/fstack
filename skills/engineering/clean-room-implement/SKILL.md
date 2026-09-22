---
name: clean-room-implement
description: Manually implement a feature or fix a defect clean-room: the agent that writes it neither tests nor reviews it, and one frozen candidate must pass every gate unchanged.
disable-model-invocation: true
compatibility: Requires a Git repository and a runtime that can spawn isolated subagents. Review skills and real-system test tools are used when available.
---

# Clean-room implement

Orchestrate implementation, independent testing, review, correction, and real-user exploration until one unchanged candidate has passed every selected gate.

The main session is the **Orchestrator**. It coordinates and judges evidence; it does not write product code or tests. Separation matters because an agent that knows how code was implemented tends to reproduce the same assumptions in its tests and review.

Load references when their branch begins:

- Read [roles.md](references/roles.md) before the first dispatch.
- Read [testing-ladder.md](references/testing-ladder.md) when selecting verification.
- Read [review-wave.md](references/review-wave.md) before review.
- Read [dogfood.md](references/dogfood.md) only when a user-observable workflow exists.
- Read [finding-contract.md](references/finding-contract.md) before adjudication and closure.

## Invocation

The text after the skill invocation is the task and its constraints. Preserve it as the intent; enrich it with decisions made in the conversation, but do not replace it with a description of the diff.

Flags:

- `--deep` or `--interrogate`: force interrogate.
- `--no-interrogate`: skip interrogate when risk is ordinary. If hard residual risk remains—security, data loss, or irreversible behavior—pause for confirmation instead of silently skipping it.

Mentions such as `interrogate`, `adversarial review`, `multi-model review`, `challenge`, `stress-test`, `find blind spots`, `tear this apart`, `找盲點`, or `徹底審查` also force interrogate.

## Preconditions

1. Confirm the working directory is the intended Git repository.
2. Capture:
   - baseline SHA and comparison point;
   - initial `git status`;
   - task/spec source;
   - repository instructions and native test commands.
3. Ensure the task runs on a non-default feature branch and can produce scoped local commits. The required `code-review` skill compares committed history; do not let uncommitted work disappear from its scope.
4. Separate pre-existing unrelated changes from this task. Ask only when scope cannot be inferred safely; use an isolated worktree when that is safer than touching unrelated work.
5. Classify the task as **feature** or **debug**. Ask if the ordering would materially change and the class is ambiguous.
6. Confirm the runtime can create genuinely separate agents. If it cannot, stop: the Orchestrator must not impersonate Implement, Test, Review, or Dogfood roles.
7. Locate the `code-review`, `ponytail-review`, and `interrogate` skills. `code-review` and `ponytail-review` are required review lenses. If their exact skills are unavailable, report the missing dependency rather than silently substituting a generic review.

## Candidate discipline

A **candidate** is one frozen commit under review.

- Allow only one writing role at a time.
- Have each writer commit its own scoped files; never include unrelated pre-existing changes. The Orchestrator does not stage or commit source or tests on a writer's behalf.
- Run every experiment that alters code—mutation, falsification, coverage probes—in a throwaway copy outside the repository. The candidate worktree is never modified by a non-writing role, and restoring a file afterwards does not make the edit acceptable.
- Enter each review wave with a clean worktree and record the baseline, candidate SHA, status, and diff summary.
- Give every reviewer in that wave the same candidate and intent.
- Any source or test edit creates and commits a new candidate, invalidating earlier approval.
- Do not rewrite candidate history or mutate the worktree while a review wave is active.

## Flow

### 1. Establish the contract

Write a compact run contract for agents:

- user intent and spec source;
- acceptance criteria;
- in-scope and out-of-scope behavior;
- baseline and diff command;
- repository rules;
- known risks and approval-gated operations;
- the test-ownership map when the task calls for test-driven implementation (see below).

Resolve missing product decisions with the user. Discover repository facts yourself.

### 2A. Feature path

1. Dispatch an **Implement Agent** with the contract. It writes product code only and reports changed public interfaces.
2. Dispatch a separate **Test Agent** with the spec, acceptance criteria, repository test conventions, and public interfaces—not the Implement Agent's reasoning. It writes tests only.
3. If tests fail because product behavior is wrong, return evidence to Implement. If the test is wrong, return it to Test. The Orchestrator decides ownership; agents do not edit each other's files.

#### When the task calls for test-driven implementation

A spec, repository policy, or user instruction may require the implementer to work
test-first. Red-green is a design technique, so the tests it produces encode the
implementer's own assumptions—the very thing independent testing exists to catch. Allow
both, and keep them apart:

1. Before dispatching, write the **test-ownership map** into the contract: one path the
   Implement Agent owns for its red-green tests, one path the Test Agent owns. Prefer the
   repository's existing convention for developer-level unit tests; if it has none, give
   the Implement Agent a dedicated file or directory and record it. The two sets never
   overlap, and neither agent edits the other's path.
2. The Implement Agent drives its own red-green loop inside its path, and still writes no
   product behavior the spec did not ask for.
3. The Test Agent writes its independent suite from the spec and public interfaces as
   usual. It does not read the Implement Agent's tests: those carry the same assumptions
   as the implementation, and reading them defeats the separation.
4. Scaffolding is not verification. Only the independent suite closes an acceptance
   criterion or demonstrates discrimination. The implementer's tests must still pass—a red
   one blocks like any other failing test—but a gate is never satisfied by them alone.

Without such a requirement, the default holds: the Implement Agent writes no tests.

### 2B. Debug path

1. Dispatch a **Test Agent** first to reproduce the reported behavior through a public seam. The reproducer must fail for the expected reason.
2. If no reliable reproduction is possible, gather more runtime evidence; do not guess-fix.
3. Dispatch an **Implement Agent** with the failing evidence. It fixes product code only.
4. Return to Test to prove the reproducer now passes and still detects the original defect.

### 3. Inner verification

Have the Test Agent run the selected fast gates from [testing-ladder.md](references/testing-ladder.md): repository-native tests, acceptance/regression tests, lint/type checks, and relevant property tests.

Do not advance with unexplained failures, skipped required checks, or a test that never demonstrated discrimination.

### 4. Review wave

Freeze the candidate, then run the independent read-only reviewers described in [review-wave.md](references/review-wave.md):

- `code-review`: always;
- `ponytail-review`: always;
- `interrogate`: when residual reasoning risk exists or the user requested it.

Run independent reviewers on the same candidate, concurrently when capacity allows. They report findings only and never edit files.

If a review skill normally performs nested delegation but the runtime cannot nest agents, flatten that fan-out at the Orchestrator level. Preserve fresh agents and the skill's distinct lenses; never collapse the work into the main session.

### 5. Adjudicate and correct

Normalize every finding using [finding-contract.md](references/finding-contract.md). Give each one exactly one disposition:

- `fix`: concrete problem; send it to Implement, or to Test when the defect is in verification;
- `dismiss`: unsupported, duplicate, preference-only, or contradicted by repository evidence; record why;
- `ask-user`: changes intended behavior or requires a product trade-off.

Never silently drop a finding. Review agents do not fix code.

After any fix:

1. run inner verification;
2. freeze a new candidate;
3. dispatch fresh reviewers;
4. repeat until no blocking finding remains.

Default maximum: three fix rounds. On non-convergence, stop with the unresolved evidence and ask the user.

### 6. Outer verification

Once the review wave is clean, dispatch the **Test Agent** to run the selected expensive or real-boundary gates from [testing-ladder.md](references/testing-ladder.md): targeted CRAP and mutation analysis, integration tests, relevant `make verify`, and safe falsification. Mutation and falsification work happens in a throwaway copy; the candidate stays byte-identical. The Orchestrator collects the evidence and does not run these gates in place of the Test Agent.

Then dispatch a fresh **Dogfood Agent** when a user-observable workflow exists. Dogfood explores plausible behavior as a first-time user rather than replaying acceptance scripts; follow [dogfood.md](references/dogfood.md).

An outer-verification or dogfood defect returns to the loop:

```text
Test evidence → Implement fix → inner verification → fresh review → affected outer gates
```

Ask before real operations that can incur cost, mutate production data, send messages, deploy, or require user authentication.

### 7. Close

Completion requires all of these:

- selected inner and outer gates passed, or a gate is explicitly inapplicable with evidence;
- every review and dogfood finding has a disposition;
- no unresolved blocker or user decision remains;
- Implement and Review were always different agents;
- no acceptance criterion or discrimination claim rests on the implementer's own tests;
- no non-writing role modified the candidate worktree, even transiently;
- final review and final verification refer to the same unchanged candidate;
- unrelated pre-existing changes remain preserved.

Report using the exact structure in [finding-contract.md](references/finding-contract.md). Do not claim checks that were not run.
