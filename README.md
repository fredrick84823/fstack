# fstack

Personal Claude Code workflow skills, commands, and hooks.

`fstack` is my personal agent operating system for Claude Code: it preserves
context across sessions, turns repeated workflow failures into skill
improvements, and keeps agent work auditable through plans, handoffs, hooks,
queues, eval cases, and human review gates.

## What This Demonstrates

- **Context continuity**: long-running agent work can be paused, handed off,
  resumed, and verified against the current repository state.
- **Closed-loop skill evolution**: user corrections and repeated failures are
  captured as signals, consolidated into claims and eval cases, then reviewed
  before changing durable skill behavior.
- **Auditable agent work**: questions, research docs, design concepts, structure
  outlines, plans, handoffs, changelogs, queues, and validation reports make
  agent decisions inspectable instead of hidden in chat history.
- **Human-gated automation**: agents can propose changes, but durable workflow
  mutations pass through explicit review.

## Installation

```bash
claude plugin install https://github.com/fredrick84823/fstack
```

## Core Workflows

### Context Continuity

```text
ask-codebase-questions
        |
        v
research-codebase
        |
        v
design-concept
        |
        v
structure-outline
        |
        v
create-plan
        |
        v
implement-plan
        |
        v
create-handoff
        |
        v
resume-handoff
        |
        v
verify current repo state before continuing
```

This replaces the older Research → Plan → Implement shape with a smaller
artifact chain: Questions → hidden-requirement Research → Design → Structure
Outline → Plan → Implement. The change keeps architecture alignment readable,
keeps codebase research fact-only, and avoids oversized plan files becoming a
substitute for reading code. Source: Dexter Horthy, [Everything We Got Wrong
About Research-Plan-Implement](https://www.youtube.com/watch?v=YwZR6tc7qYg).

See [docs/context-continuity.md](docs/context-continuity.md) and
[examples/handoff.md](examples/handoff.md).

### Skill Evolution Loop

```text
User correction / repeated failure
        |
        v
<<GAP skill-name: description>>
        |
        v
Stop hook captures the signal
        |
        v
signal-queue.md + memory/signals.jsonl
        |
        v
skill-memory-reflect consolidates claims + eval cases
        |
        v
/improve proposes a SKILL.md update
        |
        v
human gate
        |
        v
skill rule updated + changelog
```

See [docs/skill-evolution-loop.md](docs/skill-evolution-loop.md),
[examples/improve-signal.md](examples/improve-signal.md),
[examples/skill-memory-claim.md](examples/skill-memory-claim.md), and
[examples/eval-cases.json](examples/eval-cases.json).

## Design Principles

- **Verify before continuing**: resumed work validates repository state instead
  of trusting stale notes.
- **Raw events are not decisions**: hook-captured signals are evidence; reflected
  claims and eval cases are the review package.
- **Human gate before mutation**: skill rewrites require explicit approval before
  changing durable behavior.
- **Precision over noise**: not every complaint becomes a skill gap; false
  positive traps are part of eval design.
- **Scope-aware mutation**: user, project, and repo skill scopes prevent
  accidental cross-context edits.

## Skills (27)

| Skill | Description |
|-------|-------------|
| `ask-codebase-questions` | Create question artifacts before research or planning |
| `beautiful-mermaid` | Render professionally-styled Mermaid diagrams |
| `brainstorming` | Structured brainstorming coach |
| `codex-brainstorm` | Adversarial brainstorming with Codex |
| `codex-cli-review` | Review uncommitted changes via Codex CLI |
| `create-handoff` | Create handoff docs for session transitions |
| `create-plan` | Create detailed implementation plans |
| `create-team-plan` | Decompose plans for agent teams |
| `deep-module` | Enforce Deep Module principle for interface-first design |
| `design-concept` | Create concise architecture design concepts for human alignment |
| `doc-to-html` | Convert technical and knowledge documents into responsive single-page HTML |
| `extract-skill` | Extract and build skills from candidate queue |
| `grill-me` | Turn vague ideas into concrete PRDs through targeted questioning |
| `heptabase-task-card` | Create Sprint-ready Heptabase task cards |
| `implement-plan` | Execute phased plans with human checkpoints |
| `implement-team-plan` | Execute team-plans with native agent teams |
| `improve` | Skill self-evolution and gap tracking |
| `knowledge-map` | Build visual-first learning maps from learning targets and current state |
| `personal-wiki-mine` | Mine mechanism-first candidate claims from bounded thoughts/ and Heptabase sources |
| `research-and-plan` | Research codebase + plan in one step |
| `research-codebase` | Document codebase architecture via sub-agents |
| `resume-handoff` | Resume work from a handoff document |
| `skill-memory-reflect` | Consolidate improve memory into claims, eval cases, and worklists |
| `start-day` | Build a daily task board from local and external work signals |
| `structure-outline` | Create interface-first outlines with vertical verification slices |
| `topic-dictionary` | Build dependency-aware concept dictionaries in learning order |
| `work-wrap-up` | Commit + PR + progress sync + Slack notification |

## Commands (8)

| Command | Description |
|---------|-------------|
| `/brief-mode` | Enable terse response mode |
| `/cf-verify` | Cloud Function full test & verification |
| `/clean-worktree` | Safely clean up a merged git worktree |
| `/heptabase-title` | Generate Heptabase document titles |
| `/refine-text` | Tighten text, remove filler |
| `/safe-pull` | Pull from origin with auto stash/rebase |
| `/start-worktree-task` | Create a new git worktree for isolated work |
| `/work-wrap-up` | Shortcut to the work-wrap-up skill |

## Agents (8)

Sub-agents for the Questions → Research → Design → Structure → Plan →
Implement workflow (from
[HumanLayer](https://github.com/humanlayer/humanlayer/tree/main/.claude)):

| Agent | Description |
|-------|-------------|
| `session-ender` | Session 收尾：識別 improve signals → 提示 /work-wrap-up |
| `skill-verifier` | Independently verify proposed skill rule changes and eval scenarios |
| `codebase-analyzer` | Deep analysis of specific codebase components |
| `codebase-locator` | Locate relevant files and entry points for a task |
| `codebase-pattern-finder` | Find existing patterns and conventions |
| `thoughts-analyzer` | Analyze context from thoughts/ docs |
| `thoughts-locator` | Locate relevant prior decisions in thoughts/ |
| `web-search-researcher` | Research external context via web search |

## Hooks

Wires the `improve` skill's signal capture into session lifecycle:

- **SessionStart** → checks signal queue for pending improvements
- **Stop** → captures `<<GAP skill: desc>>` markers and skill candidates automatically

## Post-install: Enable auto gap detection

Add the following to your `~/.claude/CLAUDE.md` so Claude emits gap signals after skill execution:

```markdown
# Skill Gap Detection

After executing any skill, if a gap or improvement opportunity is found, output at the end of the response (not inside a code block):
<<GAP skill-name: one-line description of the gap>>
```

This rule tells Claude to emit `<<GAP>>` markers that the Stop hook captures into `signal-queue.md`. Run `/improve` to process pending signals.

## License

MIT © Fredrick
