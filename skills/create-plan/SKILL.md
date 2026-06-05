---
name: create-plan
description: Create detailed implementation plans through interactive research and iteration. Use when starting a new feature or ticket that needs a comprehensive technical plan. Saves plans to the repo-appropriate plans location and emits Personal Knowledge events when applicable.
allowed-tools: Read, Write, Bash, Agent, mcp__plugin_claude-mem_mcp-search__smart_search, mcp__plugin_claude-mem_mcp-search__smart_outline, mcp__plugin_claude-mem_mcp-search__smart_unfold
---

# Create Plan

Create detailed implementation plans through an interactive, iterative process.

## Exploration Tools Priority

For code file exploration, prefer **smart-explore tools** (4-18x token savings):

| Tool | Use instead of |
|------|---------------|
| `smart_search(query, path)` — discover files + symbols in one call | Glob + Grep discovery loop |
| `smart_outline(file_path)` — structural skeleton (~1-2k tokens) | Read on files > 100 lines |
| `smart_unfold(file_path, symbol_name)` — one symbol's full source | Read on large files for one function |

**Rule**: Use Read only for files < 100 lines or non-code files (markdown, JSON, config, tickets).

## Initial Response

If no parameters: ask for task/ticket description and wait.
If file path provided: read it FULLY and begin immediately.

```
Tip: /create-plan thoughts/shared/tickets/eng_1234.md
```

## Process

### 1. Read Context Files Fully
Read all mentioned files fully (no limit/offset). For code files > 100 lines, prefer `smart_outline` + `smart_unfold`. Do NOT spawn sub-tasks before reading.

### 1.5. Query claude-mem for prior context

Before spawning sub-agents, pull past work on this feature/ticket.

1. **Search**: `mcp__plugin_claude-mem_mcp-search__search(query="<feature/ticket topic>", project="<repo>", limit=15, orderBy="relevance")`
2. **Fetch** the 3-6 most relevant IDs: `mcp__plugin_claude-mem_mcp-search__get_observations(ids=[...])`

Embed results into sub-agent prompts and include a brief summary in "Present Understanding" so the user sees what past work informs this plan. Skip silently if unavailable.

### 2. Research in Parallel

Spawn parallel agents:
- **codebase-locator**: Find related files
- **codebase-analyzer**: Understand current implementation
- **thoughts-locator**: Find existing thoughts on this feature
- **linear-ticket-reader**: Get full ticket details (if Linear ticket mentioned)

Wait for ALL to complete. Then read all identified relevant files.

### 3. Present Understanding + Questions

```
Based on [ticket] and codebase research, I understand we need to [summary].

Found:
- [Current implementation at file:line]
- [Pattern to follow]

Questions (only what code can't answer):
- [Question 1]
```

### 4. Develop Plan Structure

Propose phasing first, get buy-in before writing details.

### 5. Write Plan

**Path**:
- Personal Knowledge repo: `plans/YYYY-MM-DD-description.md`
- HumanLayer thoughts repos: `thoughts/shared/plans/YYYY-MM-DD[-ENG-XXXX]-description.md`
- Other repos: use the nearest established `plans/`, `docs/plans/`, or `thoughts/shared/plans/` convention.

```markdown
# [Feature] Implementation Plan

## Overview
## Current State Analysis
## Desired End State
### Key Discoveries

## What We're NOT Doing

## Implementation Approach

## Phase 1: [Name]
### Overview
### Changes Required
#### 1. [Component]
**File**: `path/to/file`
**Changes**: [summary]

### Success Criteria
#### Automated Verification:
- [ ] `make test`
#### Manual Verification:
- [ ] Feature works as expected

**Note**: Pause after automated verification for human manual testing confirmation.

---

## Testing Strategy
## References
```

### 6. Emit Personal Knowledge Event When Applicable

If the plan is created inside `/Users/fredrick/Desktop/02_Personal/personal-knowledge` or is about Fredrick's Personal Knowledge system, append a metadata-only event to:

`/Users/fredrick/Desktop/02_Personal/personal-knowledge/queues/events/knowledge-events.jsonl`

Event rules:
- Use `source_class: "plan"` and `signal_type: "artifact_completed"`.
- Use a repo-relative `source_ref`, such as `plans/YYYY-MM-DD-description.md`.
- Keep `summary` short and non-sensitive; do not copy plan body into the event.
- Set `privacy` from the plan context when obvious; otherwise default to `sensitive`.
- Set `suggested_route` to `wiki_candidate` or `wiki_source_queue`.
- Set `status: "queued"`.
- Add a candidate file only when the plan contains durable architecture, operating rules, or decisions that should later be reviewed for wiki ingestion.
- Validate the JSONL after writing:

```bash
jq -c . /Users/fredrick/Desktop/02_Personal/personal-knowledge/queues/events/knowledge-events.jsonl >/dev/null
```

### 7. Sync and Review

For Personal Knowledge repo plans, sync with git:

```bash
git status --short
git add plans/YYYY-MM-DD-description.md queues/events/knowledge-events.jsonl
git commit -m "docs(plans): add <description> plan"
git push origin main
```

For HumanLayer thoughts repos:

```bash
humanlayer thoughts sync
```

Present plan location and ask for feedback. Iterate until satisfied.

## Guidelines

- Be skeptical: question vague requirements
- Be interactive: get buy-in at each step
- Be thorough: specific file paths and line numbers
- No open questions in final plan — resolve before writing
- Separate automated vs manual success criteria
