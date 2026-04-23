# fstack

Personal Claude Code workflow skills, commands, and hooks — optimized for developer productivity.

## Installation

```bash
claude plugin install https://github.com/fredrick84823/fstack
```

## Skills (25)

| Skill | Description |
|-------|-------------|
| `agent-browser` | Browser automation for AI agents |
| `beautiful-mermaid` | Render professionally-styled Mermaid diagrams |
| `codex-brainstorm` | Adversarial brainstorming with Codex |
| `codex-cli-review` | Review uncommitted changes via Codex CLI |
| `create-handoff` | Create handoff docs for session transitions |
| `create-plan` | Create detailed implementation plans |
| `create-team-plan` | Decompose plans for agent teams |
| `excalidraw-diagram` | Create Excalidraw diagram JSON files |
| `extract-skill` | Extract and build skills from candidate queue |
| `find-skills` | Discover and install agent skills |
| `graphify` | Any input → knowledge graph → HTML |
| `implement-plan` | Execute phased plans with human checkpoints |
| `implement-team-plan` | Execute team-plans with native agent teams |
| `improve` | Skill self-evolution and gap tracking |
| `job-application-optimizer` | Tailor resumes and cover letters |
| `plugin-creator` | Scaffold new Claude Code plugins |
| `research-and-plan` | Research codebase + plan in one step |
| `research-codebase` | Document codebase architecture via sub-agents |
| `resume-handoff` | Resume work from a handoff document |
| `slack-canvas` | Create and update Slack Canvas documents |
| `slack-message` | Send formatted Slack messages via MCP |
| `startup-ideation` | Generate and evaluate startup ideas |
| `ui-ux-pro-max` | UI/UX design intelligence (50 styles, 9 stacks) |
| `vercel-deployment` | Deploy to Vercel with Next.js |
| `work-wrap-up` | Commit + PR + progress sync + Slack notification |

## Commands (10)

| Command | Description |
|---------|-------------|
| `/brief-mode` | Enable terse response mode |
| `/cf-verify` | Cloud Function full test & verification |
| `/clean-worktree` | Safely clean up a merged git worktree |
| `/cv-update` | Update CV with new achievements |
| `/heptabase-title` | Generate Heptabase document titles |
| `/refine-text` | Tighten text, remove filler |
| `/safe-pull` | Pull from origin with auto stash/rebase |
| `/split-audio` | Split audio into 10-minute segments |
| `/start-worktree-task` | Create a new git worktree for isolated work |
| `/work-wrap-up` | Shortcut to the work-wrap-up skill |

## Hooks

Wires the `improve` skill's signal capture into session lifecycle:

- **SessionStart** → checks signal queue for pending improvements
- **Stop** → captures signals and skill candidates automatically

## License

MIT © Fredrick
