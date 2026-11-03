---
name: extract-skill
description: >
  審核每週 skill miner 寫進 candidate-queue.md 的候選：新 skill 候選批准後在 fstack 建立並安裝，
  「既有 skill 被繞過」的條目改既有 skill 的觸發描述。人工 review gate 永遠在，不自動建立。
  觸發詞：「extract-skill」「處理 skill 候選」「審 skill 候選」「把候選做成 skill」
  「digest 裡的 skill 候選」「bypass 候選」
---

# Extract Skill：審核 skill 候選

候選來源是每週批次 `~/.agents/skills/improve/scripts/skill_miner.py`：它把一週的真人 session
分群，同一件事 ≥3 個不同 session 才成群，再用 transcript 的 skill 叫用紀錄過第一關。
每日 digest 會列出 pending 條目；這支 skill 負責把它們審完。

## Queue

`~/.agents/skills/improve/candidate-queue.md`（symlink 到 personal-knowledge 私有 repo）。
只處理 `status: pending`。HTML 註解裡的範例不是條目。

```markdown
## [2026-11-10T09:00:00+08:00] bypass:report-to-pm

- **status**: pending
- **kind**: bypassed              # new | bypassed
- **existing_skill**: report-to-pm  # 只有 bypassed 有
- **hit_count**: 4                # 符合的不同 session 數
- **first_seen**: 2026-11-03
- **last_seen**: 2026-11-09
- **task**: 使用者一直要求的那件事
- **reason**: 這些 session 為什麼是同一個程序
- **steps**: |
  1. …
- **invoker_hints**: 「回報 PM」、「跟 PM 說」
- **sessions**: <project 目錄>/<session id 前 8 碼>, …
- **source**: skill-miner 2026-11-10
```

**Status**：`pending` | `created` | `rejected` | `merged` | `duplicate`。舊格式條目（沒有 `kind`）當 `new` 處理。

## Workflow

### 1. 讀 pending、查證

對每筆 pending：

1. 抽一兩個 `sessions` 回原 transcript 看（`~/.claude/projects/<project 目錄>/<id>*.jsonl`），
   確認那幾個 session 真的在做 `task`，不是模型硬湊。湊的 → 建議 Reject。
2. `kind: new`：在 `~/.agents/skills` 與 fstack `skills/*/*` 找名稱或用途相近的 skill。
   找到了 → 改成建議 Merge（其實是 bypass 或 GAP），不建新的。

### 2. 展示 review 包

一筆一包，等使用者選：

```
## {name}（{kind}，{hit_count} 個 session，{first_seen}–{last_seen}）

Task：{task}
Reason：{reason}
Steps：{steps}
使用者說法：{invoker_hints}
查證：{第 1 步看到什麼}

new      → [A] 建立  [M] 併入既有 skill  [R] Reject  [S] 下次再看
bypassed → [T] 改 {existing_skill} 的觸發描述  [R] Reject（繞過是對的）  [S] 下次再看
```

### 3. 執行

| 選擇 | 動作 | status |
|---|---|---|
| A 建立 | 見下方「建立」 | `created` |
| T 改觸發 | 在 fstack 該 skill 的 `description` 補進 `invoker_hints` 裡使用者真的說的話，走同一套 PR 流程 | `merged` |
| M 併入 | 指給使用者 `/improve`，或同 T 改那支 skill | `merged` |
| R | 不動 skill | `rejected` |
| 名稱撞到既有 skill | 不動 skill | `duplicate` |
| S | 不動 | 保持 `pending` |

改 status：只改該條目的 `- **status**:` 那一行，其餘不動。queue 是 append-only。

### 4. 建立（A）

canonical 在 fstack，不在安裝版。

1. fstack 開 worktree + branch（`feat/<name>-skill`），skill 放 `skills/<分類>/<name>/SKILL.md`，
   分類照 `skills/` 現有目錄挑。
2. 寫 SKILL.md：用 `writing-great-skills` 或 `skill-creator`。description 的觸發詞取自
   `invoker_hints`（使用者的原話），步驟取自 `steps`，再用第 1 步看過的 transcript 補細節。
3. 開 PR（`describe-pr`）。**合併前不安裝**：安裝版所有 worktree 共用，裝未合併的碼會弄紅 parity。
4. 合併後安裝新 skill：
   ```bash
   npm exec --yes --package=skills -- skills add https://github.com/fredrick84823/fstack -s <name> -g
   ```
   `bin/sync-to-installed.sh` 只處理**已安裝**的 skill（DST 沒有 SKILL.md 會 exit 1），不適用新 skill。
   之後改既有 skill（T／M）才用它；若它在產 base 時 exit 2，是 fstack#86（guard 命中被當成失敗），
   照 issue 記錄、手動 `cp`，不要改 guard。

### 5. 收尾

```
處理 {N} 筆：created {…} · merged {…} · rejected {…} · duplicate {…} · 保留 pending {…}
```

## 規則

- 不自動建立、不自動改 skill：每筆都要使用者選。
- 「既有 skill 不夠用」不是這條線：那是 GAP，走 `/improve`。
- 30 天未叫用的 skill 清單（`memory/stale-skills.md`）只供參考，這支 skill 不刪 skill。
