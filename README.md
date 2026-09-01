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

### Non-engineer quick start (no clone, no build)

If you don't use Claude Code plugins, or you're on Codex, Cursor, or another
agent, use the [`skills` CLI](https://github.com/vercel-labs/skills) to pull
skills straight from this repo. Just tell your agent:

> Run `npx skills add https://github.com/fredrick84823/fstack --all -y` to
> install all skills from this repo.

Or paste the command directly into any terminal your agent has access to:

```bash
# install everything (all skills, all detected agents)
npx skills add https://github.com/fredrick84823/fstack --all

# install just one skill, e.g. doc-to-html
npx skills add https://github.com/fredrick84823/fstack -s doc-to-html

# preview what's available before installing
npx skills add https://github.com/fredrick84823/fstack --list
```

Add `-g` to install globally (available in every project) instead of just the
current project. No git clone, no Node build step, no manual file copying —
`npx skills` handles fetching and wiring the skill into your agent's config.

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

## Skills (34 loaded + 1 archived)

#### Pipeline

[`skills/pipeline/`](skills/pipeline/README.md) — 有序階段 + 中間產物 + 人類 gate。兩套 dev workflow 各一個子資料夾。

| Skill | Chain | Description |
|-------|-------|-------------|
| [`brainstorming`](skills/pipeline/brainstorming/SKILL.md) | intake | 個人腦力激盪教練。用結構化技巧逼出你自己的想法，而非替你產生點子 |
| [`create-plan`](skills/pipeline/humanlayer/create-plan/SKILL.md) | `humanlayer` | Create a detailed, phased implementation plan through interactive research |
| [`create-team-plan`](skills/pipeline/humanlayer/create-team-plan/SKILL.md) | `humanlayer` | Decompose a plan into a team-plan with task briefs, dependency graph, model assignments |
| [`design-concept`](skills/pipeline/humanlayer/design-concept/SKILL.md) | `humanlayer` | Turn current-state research into a small, human-reviewable proposed shape |
| [`implement-plan`](skills/pipeline/humanlayer/implement-plan/SKILL.md) | `humanlayer` | Execute an approved plan phase by phase, pausing for human verification |
| [`implement-team-plan`](skills/pipeline/humanlayer/implement-team-plan/SKILL.md) | `humanlayer` | Execute a team-plan using native agent teams — one teammate per task brief |
| [`research-and-plan`](skills/pipeline/humanlayer/research-and-plan/SKILL.md) | `humanlayer` | Research + plan in one pass — the shortcut for small, focused changes |
| [`research-codebase`](skills/pipeline/humanlayer/research-codebase/SKILL.md) | `humanlayer` | Document a codebase as-is via parallel sub-agents |
| [`structure-outline`](skills/pipeline/humanlayer/structure-outline/SKILL.md) | `humanlayer` | Turn an accepted design into an interface-first outline — closer to a header file than a plan |
| [`ask-codebase-questions`](skills/pipeline/matt-pocock/ask-codebase-questions/SKILL.md) | `matt-pocock` | Create the Questions artifact: define the unknowns before researching or planning |
| [`grill-me`](skills/pipeline/matt-pocock/grill-me/SKILL.md) | `matt-pocock` | 把模糊的功能想法逼成具體的 PRD，迭代到對齊後交給 create-plan |

#### Engineering

[`skills/engineering/`](skills/engineering/README.md)

| Skill | Description |
|-------|-------------|
| [`codex-brainstorm`](skills/engineering/codex-brainstorm/SKILL.md) | Adversarial brainstorming. Claude and Codex independently research then debate until Nash equilibrium. For solution exploration, feasibility analysis,… |
| [`codex-cli-review`](skills/engineering/codex-cli-review/SKILL.md) | Use Codex CLI (not MCP) to review uncommitted changes. Codex explores the codebase independently with full disk read access |
| [`describe-pr`](skills/engineering/describe-pr/SKILL.md) | Write a pull request description a reviewer can digest without opening the diff |
| [`scannable-pr`](skills/engineering/scannable-pr/SKILL.md) | Write a scannable GitHub PR body |
| [`work-wrap-up`](skills/engineering/work-wrap-up/SKILL.md) | 功能完成後的收尾三連發：commit+PR → 進度同步 → (選配) Slack 通知 |
| [`writing-great-issues`](skills/engineering/writing-great-issues/SKILL.md) | 把問題、提案或工作項寫成顆粒度適中的 GitHub issue，預設產出 draft |

#### Continuity

[`skills/continuity/`](skills/continuity/README.md)

| Skill | Description |
|-------|-------------|
| [`create-handoff`](skills/continuity/create-handoff/SKILL.md) | Create comprehensive handoff documents for transferring work to another agent session |
| [`heptabase-task-card`](skills/continuity/heptabase-task-card/SKILL.md) | 在 Heptabase 建立符合 Sprint whiteboard 標準格式的任務卡片 |
| [`resume-handoff`](skills/continuity/resume-handoff/SKILL.md) | Resume work from a handoff document with context analysis and validation |
| [`spawn`](skills/continuity/spawn/SKILL.md) | Hand this session's handoff doc to a fresh Claude in a new cmux surface |
| [`start-day`](skills/continuity/start-day/SKILL.md) | 每日早晨任務看板：整合 gsheet / GitHub / Heptabase Sprint 三處任務狀態 |

#### Understanding

[`skills/understanding/`](skills/understanding/README.md)

| Skill | Description |
|-------|-------------|
| [`beautiful-mermaid`](skills/understanding/beautiful-mermaid/SKILL.md) | Render restrained, Craft-style Mermaid diagrams (SVG / interactive HTML / ASCII) |
| [`doc-to-html`](skills/understanding/doc-to-html/SKILL.md) | Convert RFCs, design docs, PRDs and research notes into readable single-page HTML |
| [`knowledge-map`](skills/understanding/knowledge-map/SKILL.md) | Build a visual-first learning map from your learning target and current state |
| [`personal-wiki-mine`](skills/understanding/personal-wiki-mine/SKILL.md) | Mine mechanism-first candidate claims from a bounded set of sources |
| [`topic-dictionary`](skills/understanding/topic-dictionary/SKILL.md) | Build a dependency-aware concept dictionary in learning order |
| [`viz-it`](skills/understanding/viz-it/SKILL.md) | Turn any content into a visual-first single-page HTML where every diagram is a pan/zoom canvas |

#### Skill evolution

[`skills/skill-evolution/`](skills/skill-evolution/README.md)

| Skill | Description |
|-------|-------------|
| [`extract-skill`](skills/skill-evolution/extract-skill/SKILL.md) | 從 candidate-queue.md 讀取候選 skill，去重、合併、review，批准後才建立 |
| [`improve`](skills/skill-evolution/improve/SKILL.md) | 通用 skill 自我進化工具：把使用者的修正收成 signal，確認是可重複的規則缺口才改 skill |
| [`skill-memory-reflect`](skills/skill-evolution/skill-memory-reflect/SKILL.md) | Reflect on /improve Skill Evolution Memory |

#### Comms

[`skills/comms/`](skills/comms/README.md)

| Skill | Description |
|-------|-------------|
| [`generate-meeting-notes`](skills/comms/generate-meeting-notes/SKILL.md) | 把逐字稿、字幕或錄音轉成結構化繁中會議記錄，發佈到 Google Doc 與 Slack |
| [`slack-pm`](skills/comms/slack-pm/SKILL.md) | 把要發給非工程師同事（PM／AM／業務／主管）的 Slack 訊息寫成交辦簡述 |
| [`slack-rd`](skills/comms/slack-rd/SKILL.md) | 把要發給 RD team 的 Slack 訊息寫成公告 + thread 論述兩層，預設產出 draft |

#### Archive

[`skills/archive/`](skills/archive/README.md) — 不再用、留著參考。**不進 `plugin.json`，不會載入。**

| Skill | Description |
|-------|-------------|
| [`deep-module`](skills/archive/deep-module/SKILL.md) | Apply the Deep Module principle — human designs the interface outline, AI fills the implementation |

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
