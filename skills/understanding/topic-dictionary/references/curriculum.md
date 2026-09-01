# Curriculum design

## Define scope

Record a one-sentence domain statement, the target reader, what they should be able to understand or do, explicit exclusions, output language, and approximate entry count. Treat a requested entry count as a budget rather than a quota.

## Discover candidates

Use several passes so the result is not shaped by one source or one taxonomy:

1. **Foundation pass:** vocabulary required to state the domain's central problem.
2. **Mechanism pass:** parts, processes, states, and causal relationships.
3. **Practice pass:** tools, operations, decisions, and recurring failure modes.
4. **Boundary pass:** contrasts, adjacent concepts, and commonly conflated terms.
5. **Evidence pass:** concepts repeatedly used by authoritative sources or practitioners.

For each candidate, write a provisional one-sentence meaning. Merge synonyms under one canonical name, record aliases, and remove branded instances unless the instance teaches a general mechanism.

## Build the graph

Represent each concept as a node. Add edge `A -> B` only when a reader must understand A before B can be explained without hand-waving. Do not use prerequisite edges merely for topical similarity; record those under `related`.

Check the graph before writing:

- Every non-foundational concept has enough prerequisites to be independently explainable.
- No concept requires itself, directly or transitively.
- Dense clusters expose a missing abstraction or an overly broad concept.
- Orphan nodes are either true foundations or out of scope.
- Two nodes with nearly identical prerequisite and consequence sets may be duplicates.

## Form learning sections

Topologically sort the graph, then group adjacent concepts by the kind of mental model they establish. A typical progression is foundations, mechanisms, composition, application, and trade-offs, but use domain-native sections when clearer.

Assign stable integer metadata:

- `section_order`: the section's learning position.
- `order`: the concept's position within that section.

Break ties deterministically by canonical slug. Never alphabetize the entire dictionary: alphabetical order may be used only as the final tie-breaker among concepts with equal learning priority.

## Revise the curriculum

Draft entry outlines before prose. If an outline repeatedly needs an undefined term, add that term as a prerequisite concept or rewrite it away. If an entry cannot support all required questions without becoming a survey, split it. If two entries repeat the same mechanism, merge them or make their boundaries explicit.
