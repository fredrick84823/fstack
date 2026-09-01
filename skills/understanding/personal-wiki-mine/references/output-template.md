# Output Template

Use this file structure:

```markdown
---
date: YYYY-MM-DD
topic: "personal-wiki-mine — Candidate Claims"
curation_time: "YYYY-MM-DDTHH:MM+08:00"
status: awaiting-user-scoring
source_protocol: bounded-source-brief-with-coverage-audit
lifecycle_state: candidate
---

# personal-wiki-mine — Candidate Claims

## Source Manifest

| # | Source | Type | Purpose |
|---|---|---|---|

## Source Coverage Audit

### Whiteboard Coverage

| Requested whiteboard | Search result | Coverage state | Evidence available | Required compensation |
|---|---|---|---|---|

### Compensating Card Search

| Query | Reason | Selected cards | Fully fetched? |
|---|---|---|---|

### Missing Or Partial Signals

- ...

## Heptabase Fetch Notes

- ...

## GT Pattern Summary

1. ...
2. ...
3. ...

---

## #1. ...
...

## Self-Audit

| # | Pure metaphor? | Has mechanism? | Single-source writable? | Operational consequence? | Source coverage sufficient? |
|---|---|---|---|---|---|

## User Instructions

1. Score each candidate.
2. Mark passes using avg >= 4.0.
3. Write overall reflection.

## Overall Reflection

**# passes / 5**: _
```

Lifecycle rule:

- generated file state = `candidate`
- scored file state may become `candidate-passed`
- promotion is not part of this skill

Coverage rule:

- partial whiteboard fetches must be disclosed
- partial whiteboards must be compensated with card-level search where possible
- candidates must not rely on a whiteboard shell as their only Heptabase evidence
