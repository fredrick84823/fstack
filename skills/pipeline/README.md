# Pipeline

有序階段 + 中間產物 + 人類 gate。跟 [`engineering/`](../engineering/README.md) 的單次工具相對 —— 這裡的每一步都留下一份可 review 的文件，所以一個功能可以跨好幾個 session、換 agent 也接得起來。

兩套 dev workflow，同樣的四個階段，不同的產物形狀。**粗體 = 這個 repo 有**；其餘留在各自的上游 plugin，另外安裝。

| 階段 | Matt Pocock | HumanLayer |
|---|---|---|
| **1 · plan** | wayfinder · grill-with-docs / **`grill-me`** · **`ask-codebase-questions`** | **`design-concept`** · **`structure-outline`** |
| **1.5 · spec** | to-spec · to-ticket | **`create-plan`** |
| **2 · implement** | implement | **`implement-plan`** |
| **3 · review** | code-review | — |

跨階段餵進來的（不屬於任一套）：

| 餵進 | skill |
|---|---|
| plan | **`research-codebase`** · **[`doc-to-html`](../understanding/doc-to-html/SKILL.md)** |
| review | explain-diff |

## Intake

本 repo 自創，不屬於任一套 —— 需求還在腦子裡、連要問什麼都不確定時的入口。談出方向後才進兩條鏈之一。

**Model-invoked** — the model can reach for these when the description matches.

- **[brainstorming](./brainstorming/SKILL.md)**: 個人腦力激盪教練。用結構化技巧逼出你自己的想法，而非替你產生點子

## HumanLayer

[ACE-FCA](https://github.com/humanlayer/advanced-context-engineering-for-coding-agents) 的 research → plan → implement。每段留下一份 artifact 落在 `thoughts/shared/plans/`，段與段之間是人類 review 點，context 使用率壓在 40–60%。跨 session 的功能走這條。

`research-and-plan` 是 research + plan 的融合捷徑，小改動用。`create-team-plan` / `implement-team-plan` 是同一條鏈的多 agent 變體。

**Model-invoked** — the model can reach for these when the description matches.

- **[create-plan](./humanlayer/create-plan/SKILL.md)**: Create a detailed, phased implementation plan through interactive research
- **[create-team-plan](./humanlayer/create-team-plan/SKILL.md)**: Decompose a plan into a team-plan with task briefs, dependency graph, model assignments
- **[design-concept](./humanlayer/design-concept/SKILL.md)**: Turn current-state research into a small, human-reviewable proposed shape
- **[implement-plan](./humanlayer/implement-plan/SKILL.md)**: Execute an approved plan phase by phase, pausing for human verification
- **[implement-team-plan](./humanlayer/implement-team-plan/SKILL.md)**: Execute a team-plan using native agent teams — one teammate per task brief
- **[research-and-plan](./humanlayer/research-and-plan/SKILL.md)**: Research + plan in one pass — the shortcut for small, focused changes
- **[research-codebase](./humanlayer/research-codebase/SKILL.md)**: Document a codebase as-is via parallel sub-agents
- **[structure-outline](./humanlayer/structure-outline/SKILL.md)**: Turn an accepted design into an interface-first outline — closer to a header file than a plan

## Matt Pocock

逼問優先：先把未知與想法拷問成具體的東西，再談實作。

這個 repo 只有其中兩支 —— `to-spec` / `to-ticket` / `implement` / `code-review` / `wayfinder` / `grill-with-docs` 在 [mattpocock/skills](https://github.com/mattpocock/skills)，另外安裝。`grill-me` 是本 repo 的改編版，產出 PRD 後交棒給 `create-plan`，也就是接到 HumanLayer 那條鏈上。

**Model-invoked** — the model can reach for these when the description matches.

- **[ask-codebase-questions](./matt-pocock/ask-codebase-questions/SKILL.md)**: Create the Questions artifact: define the unknowns before researching or planning
- **[grill-me](./matt-pocock/grill-me/SKILL.md)**: 把模糊的功能想法逼成具體的 PRD，迭代到對齊後交給 create-plan
