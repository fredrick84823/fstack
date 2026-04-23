---
name: improve
description: >
  通用 skill 自我進化工具。當任何 skill 執行後使用者有修正、抱怨、或說「少了什麼」，
  立即在 response 末尾輸出 <<IMPROVE_SIGNAL skill="x" type="S2" gap="y">>，
  Stop hook 自動寫入 signal-queue.md。
  主動觸發：「improve」「skill 改進」「improve skill」「修正 skill」「更新 skill 規則」
  「skill 有缺口」「skill 漏掉了」「self-improve」「自我進化」「skill 學習」。
  初始化：「improve init」批量為選定 skill 生成 Signal Collection 區塊（供人工審核）。
---

# Improve — Skill 自我進化工具

讓 skill 生態系持續進化。Skill 在使用中學習，在學習中改善。

**最終目標**：建立不需要人工主動觸發的自我進化迴圈——每次 skill 執行都是一次學習機會，系統在使用過程中自動累積知識並改寫自身規則。

## 參數

| 參數 | 必填 | 說明 |
|------|------|------|
| `TARGET_SKILL` | 否 | 要改寫的 skill 名稱（省略時由 Step 2 歸因決定） |
| `SIGNAL` | 否 | 信號來源路徑（report 檔、git diff、錯誤訊息），省略時讀 signal-queue.md 或互動模式 |
| `SCOPE` | 否 | `user` / `project` / `repo`（省略時自動偵測） |

## Scope 解析

執行時以 Bash 邏輯（或 `~/.claude/skills/improve/scripts/resolve_scope.sh`）自動偵測 scope：

```
IF cwd 底下有 skills/{TARGET_SKILL}/SKILL.md        → scope=repo
ELIF cwd 底下有 .claude/skills/{TARGET_SKILL}/       → scope=project
ELIF ~/.claude/skills/{TARGET_SKILL}/ 存在           → scope=user
ELSE                                                 → 互動詢問
```

各 scope 的寫入路徑：

| scope | SKILL.md 路徑 | signal queue |
|-------|--------------|--------------|
| user | `~/.claude/skills/{target}/SKILL.md` | `~/.claude/skills/improve/signal-queue.md` |
| project | `.claude/skills/{target}/SKILL.md` | `.claude/skills/improve/signal-queue.md`（無則 fallback user） |
| repo | `skills/{target}/SKILL.md` | `skills/improve/signal-queue.md` |

## Signal 類型

| 類型 | 觸發情境 | 範例 |
|------|---------|------|
| **S1: 下游漏接** | Skill A 的產出讓 Skill B 發現缺口 | Skill B 執行後發現 Skill A 遺漏某分類 |
| **S2: 人工修正** | 使用者手動修正 skill 的產出或行為 | 使用者推翻了 skill 的判斷結果 |
| **S3: 執行偏差** | Agent 使用 skill 時傳錯參數、遺漏步驟、誤判分支 | agent 呼叫腳本時格式不符規格 |

## Universal Signal Detection — 無需 Opt-in

**執行任何 skill 的過程中**，若偵測到以下情況，在 response 末尾加入 `<<IMPROVE_SIGNAL>>` 標記，Stop hook 自動捕捉到 signal-queue.md，不需要 skill 本身做任何設定：

| 情況 | 分類 | 辨識關鍵字範例 |
|------|------|--------------|
| 使用者說結果不對、漏掉什麼、不是想要的 | S2 | 「不對」「漏掉了」「少了 X」「這不是我要的」「你忘了 Y」 |
| 使用者對 skill 產出進行實質修正 | S2 | 使用者直接改寫或否定 agent 的輸出 |
| 某 skill 的產出被下一個 skill 處理時格式不符 | S1 | 下游 skill 報錯或提到上游格式問題 |
| Skill 指示的工具呼叫失敗、參數錯誤 | S3 | exit code 非零、工具回傳 schema error |

**標記格式（單行，放 response 末尾）：**

```
<<IMPROVE_SIGNAL skill="skill-name" type="S2" gap="一句話描述缺口">>
```

**若 skill 有 Signal Collection 區塊**：以該區塊的條件為準（比通用偵測更精確），Signal Collection 區塊同時作為 skill-creator eval 的驗證指標，不需 opt-in 才能接收 signal。

**⚠️ Cowork / Subagent 環境（無 Stop hook）**：標記無法被 hook 自動捕捉。偵測到 gap 時，直接用 Bash 工具寫入：

```bash
ts=$(date -Iseconds)
queue="$HOME/.claude/skills/improve/signal-queue.md"
printf '\n## [%s] %s\n\n- **type**: %s\n- **source**: cowork auto-detected\n- **gap**: %s\n- **status**: pending\n' \
  "$ts" "skill-name" "S2" "gap description" >> "$queue"
```

## improve init — 批量初始化 Signal Collection

使用者輸入 `/improve init` 或 `improve init` 時，執行以下流程：

1. 列出 user scope 下所有 skill（`~/.claude/skills/`）
2. 詢問使用者：「要為哪些 skill 加入 Signal Collection 區塊？」（可複選，或輸入 `all`）
3. 對每個選定的 skill，**spawn 獨立 subagent**：
   - 讀取該 skill 的完整 SKILL.md
   - 理解 skill 的目的、步驟、以及可能的失敗模式
   - 提出 2-4 個具體的 Signal Collection 條件（IF situation → THEN emit S1/S2/S3 signal）
   - 產出完整的 Signal Collection markdown 區塊，包含要 append 到 signal-queue.md 的格式範例
4. 逐一展示每個 skill 的 proposal（**不自動寫入**）：

```
## Signal Collection Proposal: {skill-name}

### 建議新增條件：
- IF {具體情境} → S2: {gap 描述}
- IF {具體情境} → S3: {gap 描述}

### 建議 Signal Collection 區塊：
[完整 markdown 內容]

[A] Approve 寫入  [R] Skip  [M] Modify
```

5. 收集所有確認的 skill，批量 append Signal Collection 區塊到各自的 SKILL.md

## Workflow

### Step 0: Scope 偵測

1. 若使用者提供了 `SCOPE=user/project/repo`，直接使用
2. 否則執行 `~/.claude/skills/improve/scripts/resolve_scope.sh` 自動推斷
3. 顯示偵測結果：`scope={value}, skill_path={path}, queue_path={path}`

### Step 1: 收集信號 (Collect Signal)

依以下優先順序確定信號來源：

1. **指定 SIGNAL 路徑**：直接讀取指定檔案（report、diff、log）
2. **讀取 signal queue**：讀取 scope 對應的 `signal-queue.md`，取出所有 `status: pending` 項目
3. **互動模式**：若無任何輸入，詢問使用者描述遇到的缺口

將每個缺口結構化為：
```
gap = {
  現象: <觀察到什麼>,
  預期行為: <skill 應該做什麼>,
  實際行為: <skill 實際做了什麼>,
  signal_type: <S1 / S2 / S3>,
  source_skill: <哪個 skill 觸發這個 gap>
}
```

若 queue 為空且無輸入，輸出「目前無待處理的缺口信號」並結束。

若有多個 pending 信號，優先處理 **S1 > S2 > S3**，每次只處理一個 skill 的改寫。

### Step 2: 歸因分析 (Root Cause Attribution)

對每個 gap：

1. 若已指定 `TARGET_SKILL` → 直接讀取目標 skill 的 SKILL.md
2. 否則 → 執行 `~/.claude/skills/improve/scripts/list_candidate_downstream.sh` 動態推斷候選，逐一讀取 SKILL.md
3. 定位缺口對應的具體段落（Step N、判斷規則、對照表的某行）

**動態下游推斷**（取代手動維護的 dependency map）：
- 在當前 scope 下 glob 所有 SKILL.md
- grep 它們的 body 是否提及 `{TARGET_SKILL}`（提及 = 潛在下游）
- 將命中列表納入 `downstream_impact` 欄位

**歸因輸出格式**：
```
target_skill: <skill 名稱>
section: <Step N / 表格名 / 判斷規則名>
root_cause: <為什麼這段規則會產生這個缺口>
downstream_impact: <動態推斷出的下游 skill，若無則填「無」>
```

⚠️ **Scope Guard（嚴格執行）**：
- `scope=user`：只能改 `~/.claude/skills/` 下的檔案
- `scope=project`：只能改 `.claude/skills/` 下的檔案
- `scope=repo`：只能改 `skills/` 下的檔案
- 禁止修改 CLAUDE.md、settings.json、或任何非 skill 檔案

### Step 3: 模式萃取 (Pattern Extraction)

將 gap 歸納為可操作規則，格式固定：

```
IF <condition> THEN <action>
```

例：
- `IF skill 預期回傳結構化資料但回傳自然語言 → THEN 加入輸出格式範本`
- `IF agent 呼叫腳本時 label 包含空格 → THEN 提醒 label 需用底線`
- `IF 參數含路徑且路徑有空格 → THEN 自動加引號`

每條規則同時識別：
- 需要改寫的 SKILL.md 段落（哪一個 Step、哪一個判斷分支）
- 需要同步新增或修改的測試案例（若該 skill 有 tests/）

### Step 4: 建立候選版本 (Build Candidate)

在 working memory 中（**不寫入正式檔案**）產出：
- 改寫後的完整段落內容
- 測試更新內容（若有）

清楚標記：哪些是新增的規則（`[NEW]`），哪些是修改（`[MODIFIED]`）。

### Step 5: skill-creator Eval（Eval on Candidate）⚡

**目的**：在人工審核前先驗證改寫品質，讓 human review 拿到的是「改寫 + 驗證結果」的完整包。

**若 target skill 有 eval set**（目標 skill 目錄下有 `evals/evals.json`）：
1. 觸發 `/skill-creator` 對候選版本跑 eval
2. 收集：
   - Trigger precision score（描述改寫後的觸發精度）
   - Output quality pass_rate + delta（改寫前後對比）
3. 判定：
   - `trigger_score >= 0.8` AND `pass_rate delta >= 0` → ✅ 品質通過
   - `trigger_score < 0.8` → ⛔ 觸發精度退化，回 Step 3 調整 description
   - `pass_rate delta < 0` → ⛔ 產出品質退化，回 Step 3 調整規則

**若無 eval set**：
- 標記 `eval_status: skipped（無 eval set）`
- 在 Step 6 的 review 包中提示建議建立 eval cases

### Step 6: Human Review Gate ⚠️ STOP — 等待人工審核

一次展示完整包（diff + eval 結果同時呈現）：

```
## Skill Improvement Proposal

**Target**: {target_skill} — {section}
**Signal**: {S1/S2/S3} — {來源}
**Scope**: {scope} → {skill_path}

### 改寫規則
IF {condition}
THEN {action}

### Diff Preview

**改寫前：**
{原始段落完整引用}

**改寫後：**
{新段落（含新規則，[NEW]/[MODIFIED] 標記）}

### Eval 結果
| 維度 | 結果 |
|------|------|
| Trigger precision | {score} {✅/⛔/⏭️} |
| Output quality | {pass_rate} (delta: {+/-}) {✅/⛔/⏭️} |
| 狀態 | ✅ 通過 / ⛔ 退化 / ⏭️ 跳過（無 eval set） |

### 影響範圍
- 直接改寫：{target_skill}/{section}
- 下游可能受影響：{動態推斷的下游 skill，若無則填「無」}

---
**請選擇**：[A] Approve  [R] Reject  [M] Modify（提供修改意見後回 Step 3）
```

處理結果：
- `A (Approve)` → 進入 Step 7
- `R (Reject)` → signal-queue.md 對應項目標記 `status: rejected`，結束
- `M (Modify)` → 使用者提供修改意見，回 Step 3 重新萃取規則

### Step 7: 寫入 + Changelog (Apply & Log)

1. **寫入正式 SKILL.md**：用 Edit 工具修改對應段落（路徑由 Step 0 的 scope 決定）
2. **更新測試檔**（若有變動）
3. **更新 signal-queue.md**：處理過的項目標記 `status: resolved`
4. **Append changelog.md**：

```markdown
## {YYYY-MM-DD} — {target_skill} / {section}

- **Signal**: {S1/S2/S3} — {來源描述}
- **Gap**: {現象一句話描述}
- **Rule**: `IF {condition} THEN {action}`
- **Eval**: trigger={score}, quality={pass_rate} (delta: {delta})
- **Decision**: approved by human
```

5. **提示使用者考慮 commit**：
   ```
   建議 commit message：[skill] improve {target_skill}：{改寫規則一句話摘要}
   ```

6. **若 scope=repo**（在 skills 源碼 repo 內），額外輸出 PR 提示：
   ```
   📦 Repo 模式：建議 PR 流程
     git checkout -b skill/improve-{target}-{yyyymmdd}
     git add skills/{target}/
     git commit -m "skill({target}): {rule 一句話}"
     gh pr create --title "improve({target}): ..." --body "改寫理由 + eval 結果"
   ```

## Signal Collection Protocol

Auto-trigger 機制：signal 產生時，skill **在當下輸出提示**，不依賴 Stop hook。

其他 skill 若要 opt-in，參考 `~/.claude/skills/improve/references/signal-collection-protocol.md` 在 SKILL.md 末尾加入 Signal Collection 區塊。

## Notes

- 每次只處理一個 skill 的改寫，避免批量改寫產生難以追蹤的影響
- Scope guard 嚴格：只改對應 scope 下的 skill 檔案，不例外
- changelog.md 只 append，永不修改歷史記錄
- Eval 失敗（⛔）時不進入 Step 6，直接回 Step 3；三次仍失敗則報告 blocker 並請人工介入
- 若 skill-creator plugin 未安裝，eval 步驟自動跳過並標記 skipped
