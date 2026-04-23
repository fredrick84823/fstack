---
name: create-handoff
description: Create comprehensive handoff documents for transferring work to another agent session. Use when the user requests to create a handoff, end a session, or document work-in-progress for future continuation.
allowed-tools: Read, Write, Bash
---

# Create Handoff

Create thorough yet concise handoff documents to transfer work context to another agent session.

## Step 1: Generate Metadata

```bash
bash ../../shared/scripts/spec_metadata.sh
```

## Step 2: Determine File Path

**With ticket**: `thoughts/shared/handoffs/ENG-XXXX/YYYY-MM-DD_HH-MM-SS_ENG-XXXX_description.md`
**Without ticket**: `thoughts/shared/handoffs/YYYY-MM-DD_HH-MM-SS_description.md`

- `YYYY-MM-DD` = today's date
- `HH-MM-SS` = current time in 24-hour format
- `description` = brief kebab-case description
- Subfolder: `client/`, `framework/`, `tools/`, or `general/` (only if that subdirectory already exists in the project)

## Step 3: Write Handoff Document

Use YAML frontmatter then content:

```markdown
---
date: [ISO datetime with timezone]
git_commit: [commit hash]
branch: [branch name]
repository: [repo name]
topic: "[Feature/Task Name] Implementation Strategy"
tags: [implementation, relevant-component-names]
status: complete
last_updated: [YYYY-MM-DD]
---

# Handoff: [ENG-XXXX or title]

## Task(s)
[Description + status (completed/in-progress/planned). If on a plan, summarize phase status HERE so next agent doesn't need to re-read the plan file.]

## Critical References
[2-3 most important file paths]

## Recent Changes
[Changes in file:line syntax]

## Learnings
[Patterns, root causes, important discoveries]

## Artifacts
[Exhaustive list of created/updated file paths]

## Action Items & Next Steps
[What the next agent should do]

## Other Notes
[Codebase locations, references, other context]
```

## Step 4: Sync

```bash
humanlayer thoughts sync
```

## Step 5: Respond to User

```
Handoff created and synced! Resume in a new session with:

/resume_handoff path/to/handoff.md
```

## Guidelines

- More information, not less
- Prefer `file:line` references over code snippets
- Summarize plan status in Task(s) section — don't rely on the next agent reading the full plan
