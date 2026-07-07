---
name: structure-outline
description: Create an interface-first Structure Outline before detailed planning or implementation. Use for CRISPY/QRSPI Structure Outline phase, vertical planning, method signatures, type contracts, API/component boundaries, or converting an accepted design concept into end-to-end slices with verification checkpoints.
allowed-tools: Read, Write, Edit, Bash
---

# Structure Outline

Turn an accepted design into an interface-first outline. This is closer to a
header file than an implementation plan.

## Inputs

Read the Design Concept, Questions artifact, research document, and any named
code files needed to understand existing interfaces.

## Write Structure Outline

Path:
- If `thoughts/` exists: `thoughts/shared/qds/YYYY-MM-DD-description-structure.md`
- Otherwise: `qds/YYYY-MM-DD-description-structure.md`

Rules:
- Define files/modules, public functions, method signatures, types, events,
  API shapes, or component contracts.
- Split work into vertical slices that each go end-to-end.
- Add a verification checkpoint for each vertical slice.
- Do not include implementation bodies, pseudocode algorithms, or broad
  horizontal phases like "build backend, then frontend, then tests."

Template:

~~~markdown
# Structure Outline: [Task]

## Interfaces / Contracts

### `path/to/file`
```language
// signatures/types only
```

## Vertical Slices

### Slice 1: [End-to-end outcome]
**Touches**:
- `path/to/file` - [interface/contract change]

**Checkpoint**:
- [test or manual verification]

### Slice 2: [End-to-end outcome]

## Out of Scope
~~~

## Hand Off

After the structure is accepted, recommend:

```text
Next: /create-plan <structure-outline-path>
```
