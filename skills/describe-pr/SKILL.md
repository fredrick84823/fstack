---
name: describe-pr
description: >
  Describe a pull request for a reviewer. Use when writing or rewriting
  a PR body, running /describe-pr, or when another skill needs a
  reviewer-facing account of a change.
---

# Describe PR

Reviewer *digests* **problem → observable change → how → proof** without opening the diff.

Repo has `.github/PULL_REQUEST_TEMPLATE.md`? Fill that. Else the five questions below. Section rules apply either way.

Presentation (fold, alerts, details, ship markdown): load the [`scannable-pr`](../scannable-pr/SKILL.md) skill **after the body exists** — start at **Pack bulk**. Keep these headings.

## Title & headings

English: the title, every `##` / `###` heading, and every `<summary>` line. Reviewer's language (繁中 by default): prose, tables, bullets, checklists, code comments.

The split follows *scan surface*, not markdown syntax — a `<summary>` is the only line visible while its `<details>` stays collapsed, so to someone scrolling the PR it is a heading.

Why the split — a session-level "answer in 繁體中文" is about talking to *you*; the title and headings are repo artifacts. They get scanned in `gh pr list`, notification digests, release notes, changelog greps and `Fixes #N` backlinks, where a mixed-script line is the one that stops the eye. The body is where the reviewer already committed to reading, so it can be 繁中.

Title: imperative, ≤72 chars, states the observable change — `fix(cost-export): drop user_email from public NDJSON`, not `修正公開檔案外洩 email`, not `fixed the email leak`. Match the repo's existing title convention (check `gh pr list`); adopt a `feat(scope):` prefix only if the repo already uses one.

## Steps

1. **Read** — full diff, commits, files the diff references but does not show. Split every hunk: *user-facing* vs internal.

   **Done when:** every file in the diff is accounted for; the *problem* is one sentence the diff actually solves.

2. **Frame** — answer each kept question from the change, not from session memory. Drop a question with nothing to say.

   **Done when:** a reader who stops after *problem* + *user-facing* knows whether to care; implementation cites `file:line`; *verify* is commands you ran or marked manual.

3. **Present** — load scannable-pr at Pack bulk. Ship `gh pr create` / `gh pr edit --body-file` markdown.

   **Done when:** paste-ready body; title, headings and `<summary>` lines are English; linked issues use `Fixes`/`Closes`/`Resolves` when merge should close them.

Section's shape unclear — alternative table, boundary table, ship-fact, cost-of-choice, three-way deviation split? [`reference/examples.md`](reference/examples.md) quotes a real PR for each.

## Questions

### What problem(s) was I solving?

The gap as it existed *before* this PR — a failure mode the reviewer recognizes. Cause and intro PR if known. Stop before the fix.

### What user-facing changes did I ship?

What a user or caller can observe. Bold lead-in + one sentence. `No user-facing changes.` is a complete answer.

### How I implemented it

Internals for the person opening the diff. Group by component. `file:line`. Shape and why that shape. Name the non-goal when the diff could be misread as including it.

### How to verify it

Commands you ran — checked if they passed, unchecked with why if not. Manual steps are a walkable path with expected before/after.

### Description for the changelog

One sentence, ship-note voice. Future readers / release notes.

## Risk / migration

Merge or deploy breaks without it → one `IMPORTANT` via scannable-pr. Compat notes live there or under implementation.
