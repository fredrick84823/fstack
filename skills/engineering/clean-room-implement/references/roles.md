# Roles and handoffs

## Permission matrix

| Role | Product code | Tests | Review findings | Runtime exploration |
|---|---:|---:|---:|---:|
| Orchestrator | no | no | adjudicates | coordinates |
| Implement Agent | writes | no | receives fixes | may reproduce for diagnosis |
| Test Agent | no | writes | reports test gaps | runs verification |
| Review Agents | no | no | report only | read-only inspection |
| Dogfood Agent | no | no | reports observations | operates public product surface |

The Orchestrator may run read-only discovery and verification commands, freeze candidates, and collect evidence. It does not repair source or tests because doing so would collapse the independence the workflow exists to preserve, and it does not stage or commit another role's files.

A `no` in this matrix means no write at all to the candidate repository. An edit that is reverted afterwards is still an edit: it breaks the guarantee that one frozen candidate is what every gate saw. Work that needs to alter code—mutation, falsification, coverage instrumentation—belongs in a throwaway copy outside the repository.

## Implement Agent

Give it:

- intent, spec, and acceptance criteria;
- repository instructions;
- current failing evidence for debug/fix rounds;
- explicit file/scope boundaries;
- selected constraints and out-of-scope decisions.

Require it to:

- inspect the real call path before editing;
- change product code only;
- commit its own scoped product files itself;
- keep the diff scoped;
- report public interface changes and unresolved assumptions;
- avoid editing, weakening, deleting, or skipping tests.

The same Implement Agent may handle correction rounds. Independence is between implementation and review, not between successive implementation rounds.

## Test Agent

Give it:

- spec and acceptance criteria;
- user-visible bug evidence for debug tasks;
- public interfaces or ports;
- repository test conventions and commands;
- no implementation rationale from the Implement Agent.

Before writing its first test, keep it independent of implementation details. It may inspect existing test conventions, public contracts, boundary adapters, and usage documentation. It should not derive assertions from the implementation body.

If no stable public seam exists, report that as a design blocker. Do not compensate by mirroring private implementation details.

Have it commit its own test files itself, and no product files.

Require tests to assert observable behavior or outgoing requests—not canned mock return values or private call counts. A debug reproducer must first fail for the reported reason. A new test should demonstrate discrimination through a safe falsification, targeted mutation, or equivalent evidence when practical.

## Review Agents

Every review agent is fresh and read-only. Give each:

- the same frozen candidate;
- the same intent/spec;
- baseline and diff command;
- repository standards relevant to its lens.

Do not give it the Implement Agent's defense of the design. Decisions and constraints belong in the shared contract; implementation rationalization does not.

## Dogfood Agent

Use a fresh, black-box agent. Give it user goals, public documentation, credentials/environment boundaries, and the public product surface. Hide implementation, tests, and prior reviewer expectations.

It reports observations and reproductions. It never edits code or tests.

## Handoff contract

Every handoff reports:

```text
candidate
role
scope received
actions taken
files changed (writers only)
commands run
observable evidence
findings or failures
unknowns
```

Agent self-reports are navigation aids, not proof. The Orchestrator verifies changed files, command results, and candidate identity directly.
