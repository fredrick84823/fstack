---
name: research-codebase
description: Document codebase as-is via parallel sub-agents. Use when researching how code works, mapping architecture, or answering questions about existing systems. Auto-detects thoughts/ directory — if present, integrates historical context and syncs; if absent, skips those steps.
allowed-tools: Read, Grep, Glob, Bash, Agent, mcp__plugin_claude-mem_mcp-search__smart_search, mcp__plugin_claude-mem_mcp-search__smart_outline, mcp__plugin_claude-mem_mcp-search__smart_unfold
---

# Research Codebase

Comprehensive codebase research via parallel sub-agents. **Document what EXISTS — no improvements, no critique.**

## Hidden-Requirement Mode

When `research-codebase` is invoked from a planning flow such as
`ask-codebase-questions`, `design-concept`, `structure-outline`,
`create-plan`, or `research-and-plan`, keep the research context as neutral as
possible:

- Research from questions, symbols, components, and code references.
- Do not include the proposed solution, desired implementation, or design
  direction in sub-agent prompts unless it is necessary to locate code.
- Ask sub-agents for facts about current behavior only.
- Write findings as factual current-state notes, not recommendations.

This prevents the research step from confirming the requested design too early.

## Exploration Tools Priority

For code file exploration, prefer **smart-explore tools** (4-18x token savings):

| Tool | Use instead of |
|------|---------------|
| `smart_search(query, path)` — discover files + symbols in one call | Glob + Grep discovery loop |
| `smart_outline(file_path)` — structural skeleton (~1-2k tokens) | Read on files > 100 lines |
| `smart_unfold(file_path, symbol_name)` — one symbol's full source | Read on large files for one function |

**Rule**: Use Read only for files < 100 lines or non-code files (markdown, JSON, config).

## Initial Response

```
I'm ready to research the codebase. Please provide your research question or area of interest.
```

## Process

### 1. Read Mentioned Files First
For code files > 100 lines, prefer `smart_outline` + `smart_unfold` over Read.
For small files, config, or markdown: use Read directly.

### 2. Check for thoughts/ Directory

```bash
test -d thoughts && echo "has_thoughts" || echo "no_thoughts"
```

This determines which agents to spawn and whether to sync.

### 3. Research in Parallel

**Always spawn:**
- **codebase-locator**: Find WHERE files/components live
- **codebase-analyzer**: Understand HOW specific code works
- **codebase-pattern-finder**: Find existing patterns/examples

**If `thoughts/` exists, also spawn:**
- **thoughts-locator**: Find relevant documents in thoughts/
- **thoughts-analyzer**: Extract insights from key thoughts documents

Wait for ALL sub-agents to complete before synthesizing.

In Hidden-Requirement Mode, phrase each sub-agent prompt as:

```text
Research these codebase questions and document current behavior only:
- [question]

Do not propose a solution or implementation plan.
```

### 4. Gather Metadata

**If `shared/scripts/spec_metadata.sh` is accessible:**
```bash
bash ../../shared/scripts/spec_metadata.sh
```

**Otherwise:**
```bash
date && git log --oneline -1 && git branch --show-current
```

### 5. Write Research Document

**If `thoughts/` exists**: `thoughts/shared/research/YYYY-MM-DD[-ENG-XXXX]-description.md`
**Otherwise**: choose an appropriate path in the project

```markdown
---
date: [ISO datetime with timezone]
git_commit: [hash]
branch: [branch]
repository: [repo]
topic: "[research topic]"
tags: [research, codebase, component-names]
status: complete
last_updated: [YYYY-MM-DD]
---

# Research: [Topic]

## Research Question
## Summary
## Detailed Findings
### [Component 1]
- What exists (file:line)

## Code References
- `path/to/file:123` - Description

## Requirement Visibility
[If Hidden-Requirement Mode was used, note that research was question-driven and did not include the proposed solution.]

## Architecture Documentation

## Historical Context (from thoughts/)
[Only if thoughts/ exists]
- `thoughts/shared/something.md` - Historical decision about X

## Open Questions
```

### 6. Sync and Present

**If humanlayer is available:**
```bash
humanlayer thoughts sync
```

Present concise summary with key file references. Ask for follow-up questions.

## Path Handling (when thoughts/ exists)

- `thoughts/searchable/allison/...` → `thoughts/allison/...` (remove only "searchable/")
- Never change directory ownership (allison/ ≠ shared/)
