# closed-loop — iteration 1

**Case**: `case1-json-flag` — add `--json` to an existing CLI `status` command (feature, ordinary risk).
**Graded on**: execution traces and git history, not the orchestrator's final report.
**Runs**: 2 waves × (with-skill, baseline), 2026-09-21 and 2026-09-22.

## Result

| | baseline | with skill (run 1) | with skill (run 2) |
|---|---|---|---|
| agents | 0 | 14 | 11 |
| review waves | 0 | 3 | 2 |
| pass / fail / n.a. | 5 / 7 / 6 | 17 / 1 / 0 | 11 / 7 / 0 |
| cost | $0.54 | $9.55 | $8.26 |
| wall clock | 37s | 33min | 18min |

Both variants produced working code: `--json` emits JSON, the human-readable default is
byte-identical, tests pass. The difference is process, not output — baseline spawned no
agent, ran no review, committed nothing, and left the worktree dirty.

## What the two skill runs disagreed about

Same skill, same prompt, different behavior:

| | run 1 | run 2 |
|---|---|---|
| mutation experiments | throwaway `/tmp` copy | **candidate worktree, edited then restored** |
| who commits | each writer, own scoped files | **orchestrator staged both roles' files** |

Run 2's `ponytail-review` reviewer — a role the skill declares read-only — wrote
`mytool/cli.py` to run mutations. The Test Agent did the same, four times.

Root cause was in the skill's own text: `testing-ladder.md` told agents to
"break one key behavior and prove the test turns red, then restore and re-run".
The agents followed it. Run 1 choosing a scratch copy was luck, not instruction.

## Changes made after this iteration

- `SKILL.md` — experiments that alter code run in a throwaway copy; restoring afterwards
  does not make the edit acceptable; writers commit their own scoped files and the
  orchestrator commits neither; outer verification is dispatched to the Test Agent.
- `references/review-wave.md` — read-only covers experiments.
- `references/roles.md` — a `no` in the permission matrix means no write at all, reverted
  or not; each writer commits its own files.
- `references/testing-ladder.md` — falsification and mutation happen in a scratch copy.

Not yet re-run against the fixture. Iteration 2 should confirm the four rules hold.

## Harness notes

Two measurement bugs were fixed while grading, both of which had silently inflated scores:

- Under bypass permissions the agents edit files through `Bash` heredocs, so `Write`/`Edit`
  attribution goes blind. Runs now use `--permission-mode acceptEdits --allowedTools Bash`,
  and attribution also falls back to pairing each actor's `git commit` with the commit's files.
- An empty role set scored as a pass (no implementer means "implementer wrote no tests" is
  vacuously true). Checks are now tri-state: pass / fail / n.a.
