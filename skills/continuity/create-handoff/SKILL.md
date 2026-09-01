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

## Step 1.5: Fetch session's claude-mem observations (optional)

Pull this session's observations to enrich the handoff's Activity Log section.

1. **Search** — limit to today + current project:
   ```
   mcp__plugin_claude-mem_mcp-search__search(
     query="<task or topic theme>",
     project="<repo>",
     dateStart="<today YYYY-MM-DD>",
     limit=30,
     orderBy="date_desc"
   )
   ```

2. **Filter** — typically 5-15 observations per session.

3. **Fetch** in chronological order:
   ```
   mcp__plugin_claude-mem_mcp-search__get_observations(
     ids=[<picked ids>],
     orderBy="date_asc"
   )
   ```

If claude-mem unavailable, skip — Activity Log section in Step 3 template will be omitted.

## Step 2: Determine File Path

**Personal Knowledge repo**:
- With topic folder: `handoffs/<topic-folder>/YYYY-MM-DD_HH-MM-SS_description.md`
- General: `handoffs/general/YYYY-MM-DD_HH-MM-SS_description.md`

**HumanLayer thoughts repos**:
- With ticket: `thoughts/shared/handoffs/ENG-XXXX/YYYY-MM-DD_HH-MM-SS_ENG-XXXX_description.md`
- Without ticket: `thoughts/shared/handoffs/YYYY-MM-DD_HH-MM-SS_description.md`

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

## Activity Log (from claude-mem)
[Chronological list of this session's observations. Format each as:
 - **[type emoji]** <title> — <one-line narrative summary>
 Example:
 - **🔵 Discovery** Identified four-bridge integration model — claude-mem (auto, granular) and thoughts/ (curated, structured) are non-overlapping, bridges connect them
 - **🟣 Feature** Drafted Phase plan for skill modifications

Omit this section entirely if claude-mem unavailable in Step 1.5.]

## Other Notes
[Codebase locations, references, other context]
```

## Step 4: Emit Personal Knowledge Event When Applicable

If the handoff is created inside `/Users/fredrick/Desktop/02_Personal/personal-knowledge` or documents Personal Knowledge system work, append a metadata-only event to:

`/Users/fredrick/Desktop/02_Personal/personal-knowledge/queues/events/knowledge-events.jsonl`

Event rules:
- Use `source_class: "handoff"` and `signal_type: "artifact_completed"`.
- Use a repo-relative `source_ref`, such as `handoffs/general/YYYY-MM-DD_HH-MM-SS_description.md`.
- Keep `summary` short and non-sensitive; do not copy the handoff body into the event.
- Set `privacy` from the handoff context when obvious; otherwise default to `sensitive`.
- Set `suggested_route` to `wiki_candidate` or `wiki_source_queue`.
- Set `status: "queued"`.
- Add a candidate file only when the handoff contains durable decisions, process changes, architecture, or reusable lessons.
- Validate the JSONL after writing:

```bash
jq -c . /Users/fredrick/Desktop/02_Personal/personal-knowledge/queues/events/knowledge-events.jsonl >/dev/null
```

## Step 5: Sync

For Personal Knowledge repo handoffs, sync with git:

```bash
git status --short
git add handoffs/ queues/events/knowledge-events.jsonl
git commit -m "docs(handoffs): add <description> handoff"
git push origin main
```

For HumanLayer thoughts repos:

```bash
humanlayer thoughts sync
```

## Step 6: Respond to User

```
Handoff created and synced! Resume in a new session with:

/resume_handoff path/to/handoff.md
```

## Guidelines

- More information, not less
- Prefer `file:line` references over code snippets
- Summarize plan status in Task(s) section — don't rely on the next agent reading the full plan
