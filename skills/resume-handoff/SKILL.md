---
name: resume-handoff
description: Resume work from a handoff document with context analysis and validation. Use when the user requests to resume from a handoff, continue previous work, or references a handoff path or ticket number (ENG-XXXX). Supports quick mode (default) and full mode (--full flag).
allowed-tools: Read, Write, Bash, Agent
---

# Resume Handoff

Resume work from a handoff document through interactive context analysis and validation.

## Quick Start

**Handoff path provided:**
- Immediately read the handoff document FULLY
- Quick mode (default): Don't auto-read referenced plans
- Full mode (`--full`): Spawn sub-agents to read all referenced documents

**Ticket number provided (`ENG-XXXX`):**
- Run `humanlayer thoughts sync` to update thoughts/
- Find most recent handoff for the ticket
- If zero files: Ask user for path; if one file: proceed; if multiple: use most recent

**No parameters:**
```
Which handoff would you like to resume from?
Tip: /resume_handoff thoughts/shared/handoffs/ENG-XXXX/file.md [--full]
     /resume_handoff ENG-XXXX [--full]
```

## Process

### 1. Read and Analyze
- Read entire handoff document
- Extract all sections: tasks, changes, learnings, artifacts, action items
- In Full Mode: use sub-agents to read referenced artifacts

### 2. Present Analysis
Cover: original tasks vs current verification, key learnings, recent changes, recommended next actions.

**Get confirmation before proceeding.**

### 3. Create Action Plan
- Use TaskCreate to track handoff action items
- Add newly discovered tasks
- Prioritize by dependencies

### 4. Begin Implementation
- Start with first approved task
- Reference learnings throughout
- Apply documented patterns

## Common Scenarios

| State | Approach |
|-------|----------|
| Clean Continuation | All changes present → proceed as planned |
| Diverged Codebase | Changes missing → reconcile and adapt |
| Incomplete Work | In-progress tasks → complete unfinished first |
| Stale Handoff | Significant time elapsed → re-evaluate strategy |

## Key Principles

- **Verify first**: Never assume handoff state matches current state
- **Be interactive**: Present findings before starting work
- **Leverage wisdom**: Apply learnings and patterns from handoff
