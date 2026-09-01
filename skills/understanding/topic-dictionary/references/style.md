# Style and consistency

## Voice

Write in direct, concrete language for the declared audience. Prefer causal explanations and examples over compressed definitions. Define necessary jargon at first use and avoid unexplained acronyms.

## Naming

- Choose the term most commonly used by the domain's practitioners.
- Use one canonical title and slug everywhere; put synonyms or aliases in prose.
- Use singular noun phrases unless the field convention requires otherwise.
- Preserve meaningful capitalization in titles while keeping slugs lowercase kebab-case.
- Do not encode section or order numbers in filenames.

## Explanation discipline

- Start with the concept, not its history.
- Separate what a thing is from what it enables.
- Explain mechanisms in the order events occur.
- State conditional claims as conditional; do not turn heuristics into laws.
- Prefer one representative example that reveals the mechanism over several decorative examples.
- Attribute claims that are empirical, disputed, time-sensitive, or source-specific.

## Multi-language output

Write titles and prose in the requested language. Keep canonical slugs in stable ASCII English when a durable English term exists; otherwise use deterministic transliteration. Never translate the same slug differently during incremental updates. Use a single language per dictionary except for aliases needed to identify domain terminology.

## Determinism

Before drafting, freeze the canonical concept list, aliases, graph, section names, and ordering. Render entries from the template in that order. Regenerate README only after all metadata is final. On incremental runs, preserve existing canonical names and order values unless the curriculum itself must change.
