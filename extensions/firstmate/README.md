# Firstmate

Firstmate is a Pi team lead for thought capture, delegation, and durable local memory.

## Start

Install this repository as a Pi package, then start Pi normally:

```bash
pi install git:github.com/fredrick84823/fstack
pi
```

For development from this checkout:

```bash
pi --extension ./extensions/firstmate/index.ts
```

Firstmate becomes the active team-lead persona. Dump thoughts as ordinary prompts. Use `/crew` to list teammates.

## Tools

- `firstmate_delegate({ tasks })`: runs 1-8 isolated teammate tasks, with at most four Pi subprocesses concurrently.
- `firstmate_memory({ action, ... })`: remembers, recalls, forgets, or reports durable local memories.

Bundled teammates are `scout`, `planner`, `worker`, and `reviewer`. Add user teammates under `~/.pi/agent/firstmate/teammates/*.md`. Trusted projects may override them under `.pi/firstmate/teammates/*.md`.

A teammate definition uses YAML frontmatter:

```markdown
---
name: tester
description: Runs focused tests and diagnoses failures
tools: read, grep, find, ls, bash
---

You are a test specialist...
```

## Memory and privacy

Ordinary non-command prompts are archived automatically as project-scoped thought memories. Set `FIRSTMATE_AUTO_MEMORY=0` to disable automatic capture. Firstmate rejects likely credentials and private keys.

Memory is local and append-only under `~/.pi/agent/firstmate/memory/` (or `FIRSTMATE_MEMORY_DIR`), using `0700` directories and `0600` files. Project filenames contain hashes rather than readable project paths. Relevant bounded memories are added to model context, so recalled text is sent to the selected model provider.

## Verification

```bash
npm run test:firstmate
pi --no-session -p --no-extensions \
  --extension ./extensions/firstmate/index.ts \
  --tools firstmate_memory \
  "Use firstmate_memory status, then report the result."
```
