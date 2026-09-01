# Source Protocol

Use bounded sources only.

## Heptabase Whiteboards

Workflow:

1. `search_whiteboards(keywords=[...])`
2. `get_whiteboard_with_objects(whiteboardId=...)`
3. classify coverage before mining claims

Extract:

- sections
- explicit connections
- mindmap hierarchy when present
- notable cards attached to the whiteboard

Coverage states:

| State | Meaning | Required action |
|---|---|---|
| `complete` | Whiteboard expansion includes enough sections, cards, or connections to reason from the board. | Use board evidence and still fetch high-value cards fully when needed. |
| `partial` | Whiteboard exists but returns only the shell, or returns too few objects for the requested source brief. | Run compensating card search and record the limitation. |
| `not-found` | Requested whiteboard cannot be found. | Search by synonyms or source-brief concepts; record the missing board. |
| `ambiguous` | Multiple plausible whiteboards exist. | Use the most relevant board only after recording the assumption; compensate with card search. |

If object expansion is `partial`, `not-found`, or `ambiguous`:

- record the limitation in the output file
- continue with card-level fetches as compensation
- do not use the whiteboard shell alone as candidate evidence

## Compensating Card Search

Run compensating card search whenever whiteboard coverage is not `complete`.

Search query inputs should include:

- requested whiteboard names
- visible section titles or card titles returned by whiteboard fetch
- source-brief concepts
- known related terms from thoughts files
- named concepts from previous candidate/eval traces

Selection rules:

- Prefer cards with direct title/topic overlap to the source brief.
- Prefer cards attached to related whiteboards over loose matches.
- Fetch selected cards fully with `get_object` before citing them.
- Record why each selected card was included.
- Record important plausible cards or concepts that could not be fetched.

## Heptabase Cards

Workflow:

1. `semantic_search_objects(...)`
2. `get_object(...)`

Use card fetches for:

- blog cards
- concept cards
- note cards referenced by relevant whiteboards

## [concept] Cards

Do not assume `[concept]` is a tag.

Use:

- title search
- semantic search

Do not rely on:

- `get_tag_cards("concept")`

## thoughts Files

Read selected markdown files fully.

Extract:

- claims
- design rules
- failure modes
- lifecycle models
- oracle/review placements

## Output Manifest

The candidate file must include:

- requested sources
- successfully fetched sources
- partial fetches
- substitutions or compensating fetches
- coverage state for each requested whiteboard
- compensating card search queries
- selected compensating cards
- important missing signals
