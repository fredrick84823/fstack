---
name: topic-dictionary
description: Discover, structure, and author a concept dictionary for any domain as a dependency-aware learning path. Use when a user asks to map a field, build a domain dictionary or conceptual curriculum, explain a topic through linked concept entries, audit an existing dictionary, or expand one with new concepts.
---

# Topic Dictionary

Turn a domain into a teachable system of concepts. Discover the field's load-bearing ideas, order them by dependency, and write explanations that build understanding rather than merely list definitions.

## Core principles

- Treat the dictionary as a curriculum expressed through linked concepts.
- Discover concepts from the domain; do not start from an alphabetical glossary.
- Make prerequisites explicit and keep the prerequisite graph acyclic.
- Explain mechanisms, purposes, use cases, and boundaries in plain language.
- Prefer a smaller complete learning path over a broad collection of shallow entries.
- Keep naming, structure, and ordering deterministic across runs.

## Workflow

1. Define the topic, audience, boundaries, output language, and desired depth.
2. Discover candidate concepts and evidence. Read [references/curriculum.md](references/curriculum.md).
3. Build the prerequisite graph, remove duplicates, and group concepts into learning sections.
4. Write one Markdown entry per concept from [templates/entry-template.md](templates/entry-template.md). Read [references/entry.md](references/entry.md) and [references/style.md](references/style.md).
5. Add prerequisite, related-concept, and next-step links using canonical slugs.
6. Generate the index with `python3 scripts/generate_readme.py <dictionary-dir>`.
7. Validate with `python3 scripts/validate_dictionary.py <dictionary-dir>` and repair every error. Read [references/quality.md](references/quality.md) before resolving warnings.

For audit mode, begin at step 2 using the existing entries as candidates. For expand mode, preserve canonical names and section numbering, add only the missing subgraph, then regenerate and validate the whole dictionary.

## Entry requirements

Place entries in `<dictionary-dir>/concepts/<slug>.md` and generate `<dictionary-dir>/README.md`. Every entry must include canonical metadata and answer:

- What is it?
- Why does it exist?
- How does it work?
- When is it used?
- What are common misconceptions?
- Which concepts are related?
- What should the reader learn next?

Use `examples/http-caching/` as a structural example, not as a domain-content source.
