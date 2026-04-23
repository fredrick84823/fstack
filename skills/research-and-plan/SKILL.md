---
name: research-and-plan
description: Research the codebase and create a concise implementation plan in one step. Use for small, focused changes where you want to go straight from research to a ready-to-implement plan without back-and-forth. For larger or more complex changes, use /research-codebase followed by /create-plan instead.
allowed-tools: Read, Write, Grep, Glob, Bash, Agent
model: opus
---

# Research and Plan

Research the codebase, then write a concise plan. No interactive Q&A — just research and output.

## Process

### 1. Read Mentioned Files First

Read any mentioned files FULLY before spawning sub-tasks.

### 2. Research in Parallel

Spawn:
- **codebase-locator**: Find WHERE relevant files/components live
- **codebase-analyzer**: Understand HOW the affected code currently works

If `thoughts/` exists, also spawn:
- **thoughts-locator**: Find relevant prior context

Wait for ALL to complete.

### 3. Write Concise Plan

**If `thoughts/` exists**: `thoughts/shared/plans/YYYY-MM-DD-description.md`
**Otherwise**: choose a sensible path in the project

```markdown
# Plan: [Task]

## What & Why
[1-2 sentences]

## Current State
- `path/to/file:line` — [what exists now]

## Changes

### 1. [Component/File]
**File**: `path/to/file`
- [Specific change, with line reference if applicable]

### 2. [Next component]
...

## Success Criteria
- [ ] [Automated check]
- [ ] [Manual verification]

## Out of Scope
- [What we're NOT doing]
```

### 4. Present

Show plan location and a one-line summary. Ask: "Does this look right, or anything to adjust?"
