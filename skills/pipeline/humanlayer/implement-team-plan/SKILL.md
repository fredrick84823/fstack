---
name: implement-team-plan
description: "Execute a team-plan (produced by /create-team-plan) using Claude Code's native agent teams. Spawns teammates per task brief, manages execution, and produces a walkthrough artifact. Requires CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 and Claude Code v2.1.32+. Use after /create-team-plan has produced a team-plan with status: ready."
allowed-tools: Read, Write, Edit, Bash, Agent, TeamCreate, SendMessage, TaskCreate, TaskUpdate, TaskList, TaskGet
---

# Implement Team Plan

讀 team-plan，spawn agent team，平行執行，產出 walkthrough。
遵循 `~/Desktop/01_Work/workspace/symphony/AGENT_TEAM_COLLABORATION_SPEC.zh-TW.md`
（以下簡稱「COLLAB SPEC」）定義的協作協議。

## Getting Started

If team-plan path provided: read it completely, verify status = `ready`, begin.
If no path: ask for one.

```
Tip: /implement-team-plan thoughts/shared/plans/2026-04-13-foo-team-plan.md
```

## 前置檢查（必跑）

```bash
claude --version        # >= 2.1.32
echo $CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS   # 必須是 1
```

若任一不符合：停下來請使用者設定，不自行 fallback。

然後驗證 team-plan：
- `status` 是否為 `ready`（非 `iterating`）？
- 所有 task 的 `write_scope` 互斥？
- `source_plan` 指向的原始 plan 還存在？

任一不符合 → 停下來請使用者先回 `/create-team-plan` 調整。

## 執行流程（對應 COLLAB SPEC §8.4–8.8）

### Step 1. Assign — 建立 team 並派發

1. 用 `TeamCreate` 建立 team，命名 `implement-<plan-slug>`。
2. 依 team-plan 的 Tasks 區塊，逐一 spawn teammate：
   - 用 team-plan 指定的 `model`（預設 sonnet）
   - Spawn prompt = 該 task 的完整 brief 欄位
   - Spawn prompt 末尾**必須加上**：
     > 完成所有工作後，在標記 task 為 review 之前，先照
     > `~/.claude/skills/implement-team-plan/references/task-completion.yaml`
     > 的欄位填寫完工報告，寫到
     > `thoughts/shared/task-completions/<task_id>-completion.yaml`，
     > 再用 `SendMessage` 通知 lead「completion 已寫到 <路徑>」。
   - 高風險 task（team-plan 標記的）**require plan approval**
3. Task dependencies 用 TaskUpdate 的 addBlockedBy 建立。

**不要做的事**：
- 不要重新做 decomposition — team-plan 已經定義好了
- 不要修改 task brief 內容 — 若有問題，停下來請使用者回 `/create-team-plan`
- 不要把 lead 的對話歷史灌給 teammate

### Step 2. Execute — Lead 保持本地工作

Lead 同時：
- 處理 critical-path 任務（team-plan「Lead 保留」列的項目）
- 監看 `TaskList` 狀態
- 回應 teammate 的 plan approval 請求與 blocker

若 lead 開始「替 teammate 做事」，立刻停下並 `SendMessage` 提醒 teammate。

### Step 3. Verify — 任務層驗證

每個 teammate 用 `SendMessage` 通知「completion 已寫到 <路徑>」時：
1. **讀 task-completion**，對照 team-plan 裡該 task 的 brief：
   - `actual_output` 覆蓋所有 `expected_output`？
   - `deviations` 超出 `scope_out`？
   - `validations_run` 覆蓋 `validation_expectation`？
2. 補跑 completion 未涵蓋的 `validation_expectation`。
3. `risks` 記錄到 integration context。
4. 不符合 → 修 brief 退回 owner（COLLAB SPEC §14.3）；新一輪須產出新 completion。

### Step 4. Integrate — 合併輸出

1. 只接受 status=`accepted` 的 task 產出。
2. 合併後跑 run-level 驗證（`make check test` 或 plan 指定指令）。
3. 更新原始 plan 的 checkbox `- [x]`。

### Step 5. Close — Walkthrough

1. **清隊**：確認所有 teammate idle → lead 執行 "clean up the team"。
   ⚠️ 絕對不要讓 teammate 自己跑 cleanup。
2. **彙整 task-completions**：讀所有 `thoughts/shared/task-completions/<task_id>-completion.yaml`，
   提取 `summary`、`deviations`、`risks`、`decisions_made`。
3. **輸出 walkthrough**：讀 `~/.claude/skills/implement-plan/references/walkthrough.md`（共用 spec），
   照各 section 在對話中**直接輸出 walkthrough 內容**，不寫入任何檔案。
4. Walkthrough Section 3 對應每位 teammate + owner_role，取自 task-completion 的 `status` 與 `summary`。
5. Section 5 彙整 `decisions_made` + 補記：為什麼選 team 模式、哪些退回序列、retry 幾次、每位 teammate 的 model。
6. Section 7 彙整 `risks`。

## 失敗與降級

以下情況**立即中止**，轉告使用者：

- 兩個 teammate 改到同檔案 → team-plan 的 write_scope 有誤，請回 `/create-team-plan`
- 某 teammate 連續 2 次 retry 失敗（brief 改了仍不過）→ 停下來請使用者介入
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` 中途被關

## 可選：quality-gate hooks

若專案有 `.claude/settings.json`，可設定：
- `TaskCompleted` hook：`make check` 失敗 → exit 2 擋下完成
- `TeammateIdle` hook：completion 還沒寫 → exit 2 要求補寫

## Resuming Work

Team mode 的 `/resume` 目前有已知限制：in-process teammate 不會復活。
恢復時：
1. 讀 team-plan + 原始 plan 看已打勾的 phase
2. 讀已有的 task-completions 看哪些 task 已 done
3. 重新 TeamCreate + 只 spawn 尚未完成的 task
