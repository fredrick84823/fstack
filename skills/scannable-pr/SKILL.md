---
name: scannable-pr
description: >
  Write a scannable GitHub PR body. Use when drafting or polishing a pull
  request description, PR template, or `gh pr create`/`gh pr edit` body.
---

# Scannable PR

Reviewer grasps **what / why / risk** **above the fold** — no expand, no scroll hunt.

## Steps

1. **Skeleton** — fill from the real change; drop empty headings:

```markdown
## Summary
<!-- 1–3 sentences: what + why -->

## Changes
- …

> [!IMPORTANT]
> <!-- only if merge/deploy breaks without it; else delete this block -->

## Test plan
- [ ] …

Fixes #N
```

**Done when:** every kept section has real content; no placeholder headings.

2. **Pack bulk** — logs, SQL, long tables, mermaid, rollback → `<details>`. Alerts: at most **two**, never consecutive, never indented.

**Done when:** above-the-fold is ≤ ~15 lines of dense prose+lists; bulk is one click away.

3. **Ship body** — output ready for `gh pr create --body-file` / PR form. Add `@reviewer` only when a named person must act.

**Done when:** paste-ready Markdown; linked issues use `Fixes`/`Closes`/`Resolves` when merge should close them.

## Toolkit

| Tool | Syntax | Use |
|------|--------|-----|
| Alert | `> [!NOTE\|TIP\|IMPORTANT\|WARNING\|CAUTION]` then `> body` | NOTE skim · TIP optional · IMPORTANT must-know · WARNING avoid harm · CAUTION bad outcome |
| Collapse | `<details>` / `<summary>` / `</details>` | bulk; blank line after `</summary>` |
| Tasks | `- [ ]` / `- [x]` | test plan |
| Diff | ` ```diff ` | behaviour before/after |
| Mermaid | ` ```mermaid ` | flow/sequence only if it beats prose |
| Table | `\| a \| b \|` | numeric / before-after compare |
| Close | `Fixes #N` | auto-close on merge |
| Snippet | file line permalink | conversation only (not in `.md` files) |

Edge cases / pitfalls: load [`references/gfm.md`](references/gfm.md) when an alert fails to render, details swallow code, or you need color swatches / permalinks / multi-template paths.
