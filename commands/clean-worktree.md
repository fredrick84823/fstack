---
description: Safely clean up a merged git worktree — sync output/, remove JSON raw files, delete worktree and branch
allowed-tools: [Bash, AskUserQuestion]
---

## Context

開發完成、PR 已 merge 後執行此 command，安全清理 worktree。
`output/` 目錄被 `.gitignore` 忽略，因此需要先把分析結果複製回主 repo 再刪除 worktree。

## Your Task

按照以下步驟執行 worktree 清理流程。

---

### Step 1：確認當前環境

```bash
git worktree list
git branch --show-current
```

- 識別要清理的 worktree 路徑（`WORKTREE_PATH`）和 branch name（`BRANCH`）
- 找出主 repo 路徑（`git worktree list` 第一行）

如果使用者沒有指定要清理的 worktree，詢問 `AskUserQuestion`。
如果目前已在要清理的 worktree 內，自動偵測當前路徑與 branch。

---

### Step 2：確認 PR 已 merge（硬性前置條件）

```bash
gh pr list --head {BRANCH} --state merged --json number,title,mergedAt
```

- 若結果為空（PR 尚未 merge 或不存在），**停止執行**並告知使用者。
- 若 PR 已 merge，顯示 PR 編號、標題、merge 時間，再繼續。

---

### Step 3：Dry-run — 預覽要同步的 output 檔案

```bash
rsync -av --update --dry-run {WORKTREE_PATH}/output/ {MAIN_REPO_PATH}/output/
```

- 列出哪些檔案會被新增或更新到主 repo。
- 如果沒有差異（0 files），告知使用者並跳過 Step 4。
- 如有差異，**顯示檔案清單後暫停，詢問使用者是否繼續**。

---

### Step 4：同步 output/

```bash
rsync -av --update {WORKTREE_PATH}/output/ {MAIN_REPO_PATH}/output/
```

使用 `--update`：
- 只複製「worktree 比 main repo 新」的檔案
- main repo 已有且較新的檔案保持不變

---

### Step 5：清理 JSON raw files

同步完成後，刪除主 repo output 中對應 project 目錄的 `.json` 檔案（保留 `.csv` 和 `.md`）。

偵測本次同步的 client/project 目錄（從 worktree output/ 內容判斷），例如：
```bash
# 找出同步的頂層目錄（client 層級）
ls {WORKTREE_PATH}/output/
# e.g. bettermilk → output/bettermilk/

# 刪除該 client 目錄下的所有 .json
find {MAIN_REPO_PATH}/output/{CLIENT}/ -name "*.json" -type f -delete
echo "Removed JSON raw files"
```

---

### Step 6：移除 Worktree

從主 repo 執行：
```bash
cd {MAIN_REPO_PATH}
git worktree remove {WORKTREE_PATH}
```

若出現 "worktree has modifications" 錯誤（uncommitted changes），詢問使用者是否強制移除（`--force`）。

---

### Step 7：刪除 Local Branch

```bash
git branch -d {BRANCH}
```

- 若 `-d` 失敗（branch 未完全 merge 至 local），告知使用者並詢問是否強制 `-D`。

---

### Step 8：確認 Remote Branch 狀態並刪除

```bash
git ls-remote --heads origin {BRANCH}
```

- 若 remote branch 仍存在（通常 PR merge 後 GitHub 不一定自動刪），詢問使用者是否刪除：

```bash
git push origin --delete {BRANCH}
```

- 若 remote branch 已不存在，告知「Remote branch 已由 GitHub 自動刪除」。

---

### Step 9：最終確認

```bash
cd {MAIN_REPO_PATH}
git worktree list
git branch -a | grep {BRANCH}
```

- 確認 worktree 已從清單移除
- 確認 local & remote branch 都已清理
- 顯示最終摘要：

```
✅ Worktree 清理完成
   Branch:     {BRANCH}
   Output 同步: {N} 個檔案複製到 {MAIN_REPO_PATH}/output/
   JSON 清理:   {N} 個 raw JSON 已刪除
   Worktree:   已移除
   Local branch: 已刪除
   Remote branch: 已刪除 / 已由 GitHub 自動清理
```

---

### Guardrails

- **Step 2 是硬性條件**：PR 未 merge 絕對不執行後續步驟
- **Step 3 dry-run 必須執行**：讓使用者確認再繼續
- output 同步只用 `--update`，永不無條件覆蓋
- JSON 清理只針對本次同步的 client 目錄，不做全域清理
- 所有破壞性操作（worktree remove、branch delete）前確認一次
