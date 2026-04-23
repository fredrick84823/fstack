---
name: research-codebase
description: Document codebase as-is via parallel sub-agents. Use when researching how code works, mapping architecture, or answering questions about existing systems. Auto-detects thoughts/ directory — if present, integrates historical context and syncs; if absent, skips those steps.
allowed-tools: Read, Grep, Glob, Bash, Agent
---

# Research Codebase

Comprehensive codebase research via parallel sub-agents. **Document what EXISTS — no improvements, no critique.**

## Initial Response

```
I'm ready to research the codebase. Please provide your research question or area of interest.
```

## Process

### 1. Read Mentioned Files First
Read any mentioned files FULLY before spawning sub-tasks.

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
