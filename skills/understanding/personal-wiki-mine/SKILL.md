---
name: personal-wiki-mine
description: >
  Mine mechanism-first candidate claims from a bounded source set across thoughts/ and Heptabase MCP.
  Writes candidate files to thoughts/global/fredrick/candidates/ and stops for human scoring.
  Trigger: "personal-wiki-mine", "zettel mine", "candidate claims", "卡片盒連結挖掘".
allowed-tools: Read, Write, Bash, Agent
---

# personal-wiki-mine

Generate candidate claims for a personal knowledge mining workflow. The output is always a `candidate`, never adopted knowledge.

## Scope

Use this skill when the user wants to:

- mine cross-source candidate claims;
- rerun a bounded Zettelkasten-style curation workflow;
- produce a reviewable candidate file for human scoring;
- turn a known source bundle into mechanism-first insights.

Do not use this skill for:

- background scanning;
- automatic wiki promotion;
- team wiki ingestion;
- unbounded discovery across every available source.

## Required Input

The user must provide a bounded source brief, explicit file paths, or a known source bundle.

Examples:

- `Mine candidate claims from AI Coding / personal wiki / item-label sources`
- `Use the successful v2 source set again`
- `Generate candidate claims from these 5 thoughts files and related Heptabase cards`

If the source brief is missing, ask for it before proceeding.

## Output Path

Write the result to:

`thoughts/global/fredrick/candidates/YYYY-MM-DD-personal-wiki-mine-candidates.md`

If `thoughts/global/fredrick/candidates/` does not exist, create it first.

## Workflow

### 1. Resolve Source Set

Turn the user request into a bounded source manifest:

- Heptabase whiteboards/cards to fetch
- card-level search queries to use if whiteboard coverage is partial
- thoughts files to read fully
- any previous candidate or decision files to use as eval traces

Record any assumptions in the output manifest.

### 2. Fetch Heptabase Sources

Whiteboards:

1. `search_whiteboards` to confirm the target
2. `get_whiteboard_with_objects` to fetch sections, connections, and cards
3. classify coverage for each requested whiteboard:
   - `complete`: sections/cards/connections are available
   - `partial`: whiteboard exists but object expansion is empty or clearly incomplete
   - `not-found`: requested whiteboard cannot be found
   - `ambiguous`: multiple plausible whiteboards exist

Cards:

1. `semantic_search_objects` to find candidates
2. `get_object` to read the selected cards fully

`[concept]` cards:

- use title/semantic search
- do not rely on `get_tag_cards("concept")`

Coverage rule:

- Do not treat a partial whiteboard fetch as complete source coverage.
- If a requested whiteboard is `partial`, `not-found`, or `ambiguous`, run compensating card search before mining claims.
- Compensating searches must use the whiteboard name, source-brief concepts, visible section/card titles when available, and known related terms from thoughts sources.
- Fetch selected compensating cards fully with `get_object`.
- Do not use a partial whiteboard shell as direct evidence for a candidate unless it is paired with fetched cards or thoughts files.
- Record the coverage classification, compensating queries, selected cards, and known missing signals in the output file.

### 3. Read thoughts Sources Fully

Read all selected markdown files fully.

Extract:

- strong claims
- failure modes
- design rules
- lifecycle states
- review/oracle positions

Do not treat raw facts as claims until they imply a stance or mechanism.

### 4. Extract GT Patterns

From whiteboards, extract the user's hand-authored relation shapes:

- problem -> technique
- technique -> workflow
- workflow -> best practice
- concept -> concrete action

Summarize 3-5 GT patterns in the candidate file before mining claims.

### 5. Extract Atomic Claims

From each source, produce 1-5 atomic claims.

Atomic claims should be:

- one sentence
- opinionated or explanatory
- grounded in the source
- reusable in multi-source synthesis

### 6. Mine Candidate Claims

Generate 5 candidate claims.

Each candidate must have:

- at least 3 evidence items
- at least 2 source types
- a mechanism-first hypothesis
- a falsifiable rebuttal path
- an operational next step

Prefer cross-context mechanisms over clever metaphors.

### 7. Run Calibrated Anti-Filter

Reject any candidate that is:

- pure structural analogy
- single-source summary disguised as synthesis
- built on `similar`, `related`, or `both` without mechanism
- unable to produce a checklist, schema, workflow, experiment, or implementation decision

Use the rules in `references/filter-calibration.md`.

### 8. Write Candidate File

Use `references/output-template.md` and `references/candidate-schema.md`.

The file must include:

- frontmatter with `status: awaiting-user-scoring`
- source manifest
- source coverage audit
- Heptabase fetch notes
- GT pattern summary
- 5 candidate claims
- self-audit table
- user scoring section
- overall reflection section

If `scripts/validate_candidate_file.py` is available, run it on the generated file and fix structural failures before stopping.

### 9. Stop For Human Scoring

Do not promote anything into `thoughts/wiki/`.

The workflow ends after writing the candidate file and telling the user where it is.

## Quality Bar

The candidate file is only acceptable if:

- every candidate is mechanism-first;
- evidence is concrete and source-linked;
- next steps are operational;
- failed or partial MCP fetches are disclosed and compensated with card-level search where possible;
- no candidate relies only on a partial whiteboard shell as evidence;
- source coverage audit explains what was requested, fetched, compensated, and still missing;
- the output clearly remains in `candidate` state.

## References

- `references/candidate-schema.md`
- `references/filter-calibration.md`
- `references/source-protocol.md`
- `references/output-template.md`
- `scripts/validate_candidate_file.py`
- `evals/evals.json`
