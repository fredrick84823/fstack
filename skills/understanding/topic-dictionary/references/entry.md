# Entry authoring

Start from `templates/entry-template.md`. Keep metadata machine-readable and prose useful to a reader arriving from a prerequisite entry.

## Frontmatter contract

- `title`: unique display name.
- `slug`: unique lowercase kebab-case identifier matching the filename.
- `section`: stable learning-section name.
- `section_order`: positive integer shared by entries in the section.
- `order`: positive integer unique within the section.
- `summary`: one plain-language sentence used by the generated index.
- `prerequisites`: canonical slugs that must be understood first.
- `related`: canonical slugs that clarify boundaries or adjacent ideas.
- `sources`: optional URLs or source identifiers used to verify the entry.

Use YAML block lists. Use `[]` for an empty list. Do not add fields with ambiguous semantics.

## Required answers

### What is it?

State the category and distinguishing mechanism. A reader should be able to tell it apart from its nearest neighbor. Do not merely restate the title.

### Why does it exist?

Name the problem, pressure, or limitation that made the concept useful. Explain what becomes harder or impossible without it.

### How does it work?

Trace the mechanism in causal order. Introduce only terminology that is already a prerequisite, defined inline, or linked to another entry.

### When is it used?

Give recognizable conditions and at least one concrete example or decision. Include a non-use case when the boundary is easy to misunderstand.

### Common misconceptions

Correct specific wrong mental models. Explain why each is wrong; avoid generic cautions.

### Related concepts

Link each related concept and state the relationship in a phrase. Do not dump a list of links.

### What to learn next

Offer one to three linked successors that the current concept unlocks. Explain why that sequence is useful. Terminal concepts may explicitly say that the core path is complete and point to an application area.

## Cross-linking

Use ordinary relative Markdown links. Entry-to-entry links within `concepts/` use `slug.md`. Link the first meaningful mention in a section; avoid linking every repetition. Ensure `prerequisites`, `related`, prose links, and next-step recommendations agree.
