# fstack

Personal Claude Code workflow skills, commands, and hooks — optimized for developer productivity.

## Installation

```bash
claude plugin install https://github.com/fredrick84823/fstack
```

## Skills (16)

| Skill | Description |
|-------|-------------|
| `beautiful-mermaid` | Render professionally-styled Mermaid diagrams |
| `codex-brainstorm` | Adversarial brainstorming with Codex |
| `codex-cli-review` | Review uncommitted changes via Codex CLI |
| `create-handoff` | Create handoff docs for session transitions |
| `create-plan` | Create detailed implementation plans |
| `create-team-plan` | Decompose plans for agent teams |
| `deep-module` | Enforce Deep Module principle for interface-first design |
| `extract-skill` | Extract and build skills from candidate queue |
| `grill-me` | Turn vague ideas into concrete PRDs through targeted questioning |
| `implement-plan` | Execute phased plans with human checkpoints |
| `implement-team-plan` | Execute team-plans with native agent teams |
| `improve` | Skill self-evolution and gap tracking |
| `research-and-plan` | Research codebase + plan in one step |
| `research-codebase` | Document codebase architecture via sub-agents |
| `resume-handoff` | Resume work from a handoff document |
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

## Agents (6)

Sub-agents for the research → plan → implement workflow (from [HumanLayer](https://github.com/humanlayer/humanlayer/tree/main/.claude)):

| Agent | Description |
|-------|-------------|
| `session-ender` | Session 收尾：識別 improve signals → 提示 /work-wrap-up |
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
