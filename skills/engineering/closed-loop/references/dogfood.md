# Dogfood: exploratory behavioral testing

Dogfood searches for realistic behavior the engineering plan did not anticipate.

```text
make verify  → known promises, scripted evidence
dogfood      → unknown user behavior, exploratory evidence
```

It is not a replay of acceptance criteria and not a second implementation-aware QA pass.

## Preconditions

Run dogfood after known inner/review/outer gates are green enough to expose a coherent product. Use a fresh agent with no implementation or test context.

Give it only:

- the user goal and public feature description;
- public documentation or discoverable interface;
- the environment and allowed accounts/data;
- safety boundaries and prohibited side effects;
- how to capture evidence.

Do not give it source internals, implementation rationale, test assertions, or reviewer predictions.

## Brief

Use this intent when dispatching:

> Act as a first-time real user trying to achieve the stated goal. Explore plausible paths rather than replaying a fixed checklist. Notice confusing behavior, silent failure, wrong-but-plausible results, inability to recover, and any need to know implementation details. Record reproducible evidence. Do not inspect or modify source code or tests.

## Exploration heuristics

Choose plausible actions for the product rather than forcing every item:

- take a reasonable path different from the documented happy path;
- repeat, retry, refresh, navigate back, cancel, and resume;
- use empty, extreme, malformed, copied, or mixed-format real-world input;
- combine the changed feature with adjacent features;
- encounter expired login, missing permission, stale state, or partial progress when safely possible;
- interpret labels and documentation literally as a new user would;
- recover from an error without privileged knowledge;
- compare displayed success with the actual resulting state.

Exploration is bounded by safety. Never create charges, contact real users, alter production/shared data, bypass access controls, or perform destructive actions without approval.

## Actuator selection

Dogfood is a method, not a browser requirement.

| Product surface | Actuator |
|---|---|
| Web application | Load and use the installed browser skill; prefer `ego-browser` when available. |
| CLI/TUI | Operate the real executable in an appropriate terminal. |
| API/MCP | Use the real supported client/protocol, not a mocked direct function call. |
| Mobile/desktop | Use the available real interaction harness; report when unavailable. |

If human login, MFA, CAPTCHA, device approval, or permission consent is required, hand control to the user and resume the same session afterward.

## Observation format

```text
journey: <goal attempted>
starting state: <environment/account/data>
actions: <minimal reproducible sequence>
expected from public contract: <expectation or “no explicit promise”>
observed: <visible result>
evidence: <screenshot/log/response/state>
reproducibility: <n>/<attempts>
impact: blocker | degraded | confusing | observation
```

Do not call a surprise a product bug merely because it differs from the agent's preference.

## Routing observations

The Orchestrator classifies each observation:

- **bug** → Test Agent creates a failing reproduction; Implement fixes it;
- **usability defect** → ask only if remediation changes intended behavior, otherwise route through Test and Implement;
- **spec gap** → ask the user;
- **expected behavior** → dismiss with public-contract evidence;
- **environment/tool issue** → record separately; do not charge it to the product.

A dogfood-driven edit creates a new candidate and requires inner verification, fresh review, and affected outer gates again.
