---
name: extract-skill
description: >
  從 candidate-queue.md 讀取待審候選 skill，進行去重、合併、review，
  使用者批准後呼叫 skill-creator 實際建立。
  觸發詞：「extract-skill」「抽取 skill」「建立 skill 從 queue」「處理 skill 候選」
  「有 skill 候選待建立」「extract skills from queue」「把候選做成 skill」
---

# Extract Skill — Skill 候選審核與建立

將 agent 在執行過程中發現的重複模式，從候選 queue 整理後建立為正式 skill。

## 前提條件

需要 `/Users/fredrick/.gemini/skills/extract-skill/../improve/candidate-queue.md`（由 capture-skill-candidate hook 或 propose.sh 寫入）。

## Workflow

### Step 1: 讀取 Candidate Queue

讀取以下位置的 `candidate-queue.md`（優先順序）：
1. `{cwd}/.claude/skills/improve/candidate-queue.md`（project-level）
2. `~/.claude/skills/improve/candidate-queue.md`（user-level）

取出所有 `status: pending` 的項目。

若無 pending 項目，輸出「candidate-queue.md 目前無待處理候選」並結束。

### Step 2: 去重 + 合併

對 pending 候選執行：

1. **名稱碰撞檢查**：在當前 scope 的 skills 目錄下，grep 是否有同名 skill 已存在
   - 若已存在 → 標記 `status: duplicate`，建議改為呼叫 `/improve` 增強既有 skill
2. **相似候選合併**：若多個候選描述相同模式（名稱相似 or reason 高度重疊），合併為一個候選，`hit_count` 累加
3. **低品質過濾**：`hit_count < 2` 的候選降優先級（顯示但標記為 low-confidence）

### Step 3: 展示 Review 包

對每個高品質候選（`hit_count >= 2` 或使用者明確要求處理），顯示：

```
## Skill Candidate: {name}

**Hit count**: {hit_count}（首見 {first_seen}，最近 {last_seen}）
**Reason**: {reason}
**Steps**:
{steps（逐行展開）}
**Suggested trigger phrases**: {invoker_hints}

---
**建議的 SKILL.md description 草稿**：
{根據 reason + steps 生成的 description 段落}

**請選擇**：[A] Approve  [S] Skip  [R] Reject  [M] Merge to existing skill
```

- `A (Approve)` → 進入 Step 4
- `S (Skip)` → 跳過本候選，保留 pending 狀態
- `R (Reject)` → 標記 `status: rejected`
- `M (Merge)` → 詢問要合併到哪個既有 skill，提示使用者改用 `/improve`

### Step 4: 建立 Skill

呼叫 `/skill-creator` 建立 skill，或引導使用者提供以下資訊：
- skill 名稱（kebab-case）
- description（含觸發詞）
- SKILL.md 主體（從 candidate 的 steps 展開）
- allowed-tools（根據 steps 推斷）

建立完成後：
- 更新 `candidate-queue.md` 該項目 `status: created`
- 輸出：`✅ {skill-name} 已建立 → {skill_path}`

### Step 5: 收尾報告

```
## Extract Skill 執行摘要

- 處理候選：{N} 個
- 已建立：{list}
- Rejected：{list}
- Skipped（待下次）：{list}
- Duplicate（建議 /improve）：{list}
```

## Notes

- human review gate 永遠存在：不允許自動建立 skill，必須人工 Approve
- 每次 `/extract-skill` 只推薦 `hit_count >= 2` 的高品質候選；低品質候選在報告末尾列出
- Candidate queue 是 append-only，status 欄位記錄處理結果
