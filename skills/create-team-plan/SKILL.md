---
name: create-team-plan
description: Read a standard plan and decompose it into a team-plan with task briefs, dependency graph, and model assignments. Use when you want to run a complex plan with agent teams. Outputs a team-plan file for /implement-team-plan to execute. Does NOT spawn teammates — that's implement-team-plan's job.
allowed-tools: Read, Write, Bash, Glob, Grep, Agent
---

# Create Team Plan

讀一份標準 plan，拆解成可被 agent team 平行執行的 team-plan。
遵循 `~/Desktop/01_Work/workspace/symphony/AGENT_TEAM_COLLABORATION_SPEC.zh-TW.md`
（以下簡稱「COLLAB SPEC」）的協作原則。

## Getting Started

If team-plan path provided: read it, check existing content, resume iteration.
If standard plan path provided: read plan fully, begin decomposition.
If no path: ask for one.

```
Tip: /create-team-plan thoughts/shared/plans/2026-04-13-foo.md
```

## 前置判斷：該不該用 team？

讀完 plan 後先判斷：

✅ 適合 team：
- 3 個以上 phase，且 phase 之間有互斥的 write scope
- 含大量研究 / review / 跨層協調工作
- 使用者明確要求

❌ 不適合 team：
- Phase 之間依賴強（後 phase 讀前 phase 輸出）
- Phase 間會動到同檔案
- 小於 3 個 phase

**若判斷不適合** → 明確告知使用者，建議改用 `/implement-plan`，不產出 team-plan。

## Decomposition 流程

**讀 `references/decomposition.md`**，依序執行：

### Step 1. Intake — 理解 plan

完整讀 plan 與所有 referenced files（no limit / offset）。找出：
- 真正的 outcome
- 各 phase 的 write scope（哪些檔案、哪些目錄）
- 明確的 acceptance criteria

### Step 2. Frame — 決定 critical path

列出：
- 必須由 lead 保留在本地的任務（整合、最終驗證、使用者溝通）
- 可安全委派的 sidecar 任務

### Step 3. Decompose — 拆解任務

依 `references/decomposition.md` 的流程：
1. 選拆解維度（phase → layer → module → work-type）
2. 萃取 write_scope（用 Glob/Grep 展開）
3. 比對重疊、判斷可否平行
4. 跨切面歸屬（每個 implementer 負責完整垂直切片：code + unit + integration test）
5. 粒度檢查

### Step 4. Model 分派

每個 teammate 可獨立指定 model。預設策略：

| teammate 類型 | 預設 model | 理由 |
|---|---|---|
| lead（自己） | 繼承使用者當前 session | 不主動降級 |
| `<module>-implementer` | **sonnet** | 平衡成本/速度 |
| `e2e-tester` | **sonnet** | 驗證任務型 |
| 高風險（schema / migration） | 升級到 `opus` | 由使用者指定 |

覆寫方式：
1. 使用者 invocation 明確指定 → 照辦
2. Plan frontmatter `preferred_models:` 欄位 → 照該欄位
3. 都沒有 → 套用預設

### Step 5. 產出 task briefs

對每個 task，照 `references/task-brief.yaml` 填寫 COLLAB SPEC §9 欄位。

### Step 6. 寫 team-plan 檔

**Path**: `thoughts/shared/plans/<original-plan-filename>-team-plan.md`

格式見下方「team-plan 輸出格式」。

### Step 7. Present & Iterate

呈現 team-plan 給使用者 review。使用者可以：
- 合併 / 拆開 task
- 調整 model 分派
- 改 write_scope 邊界
- 新增 / 刪除依賴

Iterate 直到使用者滿意，再告知：

```
Team plan 已寫到 <path>。
準備好後執行：/implement-team-plan <path>
```

## team-plan 輸出格式

```markdown
---
source_plan: <原始 plan 相對路徑>
date: <YYYY-MM-DD>
created_by: create-team-plan
status: ready | iterating
---

# Team Plan：<plan 標題>

## Decomposition Summary
- 拆解維度：<phase / layer / module / work-type>
- 拆解理由：<一句話>
- 不拆的理由（若有 phase 合併回 lead）：<列出>

## Lead 保留
- <整合、文件更新、使用者溝通、最終 accept/reject>

## Tasks

### T-001: <objective>
- **owner_role**: <role name>
- **model**: <sonnet / opus>
- **objective**: <一句話>
- **why_this_task_exists**: <為什麼>
- **expected_output**: [...]
- **scope_in**: [...]
- **scope_out**: [...]
- **dependencies**: [task_id...]
- **write_scope**: [paths...]
- **validation_expectation**: [...]
- **escalation_rule**: <...>

### T-002: <objective>
...

### T-e2e: 跨模組 e2e 驗證
...

## Dependency Graph

\`\`\`
T-types → T-auth, T-parser (parallel)
T-auth, T-parser → T-e2e
\`\`\`

## Risk Notes
- <拆解過程中識別的風險>
```

## 不要做的事

- 不要 spawn teammate — 那是 `/implement-team-plan` 的工作
- 不要開始實作 — 這個 skill 只做規劃
- 不要在使用者沒 review 前就標 status: ready
