---
name: create-plan
description: Create detailed implementation plans through interactive research and iteration. Use when starting a new feature or ticket that needs a comprehensive technical plan. Saves plan to thoughts/shared/plans/.
allowed-tools: Read, Write, Bash, Agent
---

# Create Plan

Create detailed implementation plans through an interactive, iterative process.

## Initial Response

If no parameters: ask for task/ticket description and wait.
If file path provided: read it FULLY and begin immediately.

```
Tip: /create-plan thoughts/shared/tickets/eng_1234.md
```

## Process

### 1. Read Context Files Fully
Read all mentioned files FULLY (no limit/offset). Do NOT spawn sub-tasks before reading.

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

**Path**: `thoughts/shared/plans/YYYY-MM-DD[-ENG-XXXX]-description.md`

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

### 6. Sync and Review

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
