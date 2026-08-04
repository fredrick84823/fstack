# Quality gates

Run `scripts/validate_dictionary.py <dictionary-dir>` after generating the README. Errors block completion; warnings require either a repair or an explicit judgment.

## Structural gates

- Every entry contains all required frontmatter fields and sections.
- Slugs are unique, kebab-case, and match filenames.
- Section names have one consistent `section_order`.
- Section/order pairs are unique.
- Every prerequisite and related slug resolves to an entry.
- The prerequisite graph has no cycle or self-edge.
- Every relative Markdown link resolves.

## Knowledge gates

### Missing prerequisites

Read each entry as if only its prerequisite entries were known. Terms necessary to understand the mechanism must already be defined, linked, or explained inline. Repeated undefined terms usually deserve their own concept.

### Circular definitions

A definition is circular when it relies on the concept itself, an alias, or a downstream concept. Rephrase using prerequisites and observable behavior. Graph acyclicity alone does not prove prose is non-circular.

### Duplicate concepts

Compare purpose, mechanism, prerequisites, and consequences—not just titles. Merge aliases. Preserve separate entries only when the boundary teaches an important distinction.

### Weak explanations

Reject entries that could fit in a glossary. Each must explain why the concept exists and how it works, give a use condition, correct a misconception, and create a bridge to later learning. Short prose is acceptable only when it remains causal and complete.

### Naming consistency

Search titles, headings, graph metadata, README labels, and link text for alternate capitalization, pluralization, or spelling. Pick one canonical form and record genuine aliases in prose.

## Audit modes

- **Standard:** run the validator and manually inspect its warnings.
- **Audit:** additionally trace every graph edge, sample prose links in both directions, and compare terminology against authoritative sources.
- **Expand:** validate before and after adding concepts; confirm existing slugs and links remain stable.

The validator uses conservative heuristics for prose depth. Passing it is necessary, not sufficient; perform the knowledge gates manually.
