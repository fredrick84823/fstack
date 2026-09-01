---
name: ask-codebase-questions
description: Create the Questions artifact before codebase research, design, planning, or implementation. Use for feature tickets, architecture changes, unclear code work, CRISPY/QRSPI Questions phase, or when the agent needs to define code-answerable unknowns and human questions before researching or planning.
allowed-tools: Read, Write, Edit, Bash
---

# Ask Codebase Questions

Create a focused Questions artifact before research or planning. The goal is
to define unknowns, not to solve the task.

## Process

### 1. Read Task Context

Read the ticket, PRD, issue, or user-provided task text fully. If the task names
specific files, read those files before writing questions.

### 2. Write Questions

Path:
- If `thoughts/` exists: `thoughts/shared/qds/YYYY-MM-DD-description-questions.md`
- Otherwise: `qds/YYYY-MM-DD-description-questions.md`

Rules:
- Ask only questions that affect architecture, interfaces, data flow, rollout,
  or verification.
- Separate code-answerable questions from human-only questions.
- Include a short "Unknowns to Research" section for `research-codebase`.
- Stop after writing questions when human answers are required.
- If code-answerable unknowns remain, pass only those questions to
  `research-codebase`; do not pass the proposed solution or ask it to design.

Template:

```markdown
# Questions: [Task]

## Task Summary
[1-3 sentences]

## Code-Answerable Questions
- [Question]

## Human Questions
- [Question]

## Unknowns to Research
- [Question to pass into research-codebase without proposed solution details]
```

## Hand Off

After the questions are answered or researched, recommend:

```text
Next: /design-concept <questions-path> [research-doc-path]
```
