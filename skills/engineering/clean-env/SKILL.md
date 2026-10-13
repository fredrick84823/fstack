---
name: clean-env
description: 把用不到的 herdr 與 git 環境收乾淨：worktree、herdr workspace／tab、本地與遠端分支、lavish session，先列清單等確認才刪。Use when the user asks to clean up the environment, says「把用不到的環境清掉」「herdr／git 環境很亂」, or wants merged branches deleted locally and on origin.
---

# clean-env

一次 sweep 收掉一個 repo（或一個 session）留下的開發環境。核心是 **manifest**：先唯讀盤點，每個對象一列、標好處置，使用者點頭後才動手。

## 1. 定範圍

| 使用者說 | 範圍 |
|---|---|
| 「這個 session 開的」「我開的 reviewer」 | 只收本 session 建的 worktree／分支／tab（從對話中的 `herdr worktree create`、`git worktree add`、`herdr tab create` 找） |
| 「用不到的都清掉」「環境很亂」 | 目前 repo 全部；多個 repo 時每個 repo 各一份 manifest |

永遠不在範圍內：

- 自己所在的 `$HERDR_WORKSPACE_ID`、`$HERDR_TAB_ID`、`$HERDR_PANE_ID`
- 主 checkout（`git worktree list` 第一行）
- 使用者說過要保留的（查 memory 與對話，例如 `exp-19-openwiki-init`）
- locked worktree、其他 session 正在用的分支

## 2. 盤點（唯讀）

在主 checkout 跑。這一步不刪任何東西。

```bash
git fetch -q --prune origin
git worktree list --porcelain
herdr workspace list   # agent_status、worktree.checkout_path
herdr worktree list
for w in $(herdr workspace list | jq -r '.result.workspaces[].workspace_id'); do herdr tab list --workspace $w; done
lavish-axi             # 列出 open 的 lavish session
```

每個 worktree（含 `~/.herdr/worktrees/`、`/private/tmp/claude-501/*/scratchpad/`、`.claude/worktrees/`、`~/conductor/workspaces/` 底下的）查：

```bash
git -C $WT status --porcelain                       # 未 commit 的改動
git -C $WT status --porcelain --ignored | grep '^!!' | grep -vE '\.venv|node_modules|__pycache__|\.pytest_cache|\.mypy_cache|dist/|build/'
                                                    # gitignored 但不可重建的資料（output/、salt、錄製檔）
git rev-list --count origin/main..$BRANCH           # 有沒有不在 main 的 commit
git rev-parse $BRANCH origin/$BRANCH                # 本地與遠端是否一致
gh pr list --head $BRANCH --state all --json number,state
```

本地分支：`git for-each-ref --format='%(refname:short) %(upstream:track)' refs/heads`，每條查 PR 狀態。遠端分支：`git ls-remote --heads origin`。

**完成條件**：範圍內每個 worktree、本地分支、遠端分支、herdr workspace／tab、lavish session 都在 manifest 有一列。

## 3. 分類

每列歸進一個 bucket：

| bucket | 判準 | 預設處置 |
|---|---|---|
| **安全** | 乾淨、沒有 ignored 資料、PR MERGED／CLOSED 或 commit 全在 origin/main | 刪 |
| **會遺失** | 有未 commit 改動、不可重建的 ignored 資料、沒推上去的 commit、detached HEAD 帶改動 | 問：封存後刪／commit 推上去後刪／保留／直接刪 |
| **保留** | PR OPEN 還在改、locked、其他 session 佔用、使用者說保留、不在範圍 | 不動，寫原因 |

封存做法（選「封存後刪」時）：

```bash
A=~/.local/share/worktree-archive/$(date +%F); mkdir -p $A
git -C $WT diff HEAD > $A/$NAME.tracked.patch
git -C $WT ls-files --others --exclude-standard -z | tar -czf $A/$NAME.untracked.tgz -C $WT --null -T -
echo "$(git -C $WT rev-parse HEAD)" > $A/$NAME.base
```

gitignored 的 `output/`（分析結果）用 `rsync -av --update $WT/output/ $MAIN/output/` 同步回主 checkout，先加 `--dry-run` 給使用者看清單。

其他不可重建的 ignored 資料（salt、錄製檔）搬到長期位置，用 `cmp`／`diff -rq` 比對一致後才刪原檔。

## 4. 確認

把 manifest 用表格給使用者看：對象、狀態、bucket、處置。遠端分支刪除另列一區，因為推上去的刪除不好回頭。用 `AskUserQuestion` 收決定；「會遺失」每一列都要有明確選擇。

**完成條件**：使用者對每個要刪的對象都點過頭。沒點頭的一律當保留。

## 5. 執行

順序有依賴，照這個走：

1. **worktree**：herdr 管的用 `herdr worktree remove --workspace $W --force`（同時收掉 checkout 與 workspace）；其他用 `git worktree remove $WT`。
2. `git worktree prune`
3. **本地分支**：PR 已 MERGED 的用 `git branch -D`（squash merge 後 `-d` 會說 not fully merged）；其他用 `-d`，失敗就回報、不升級成 `-D`。
4. **遠端分支**：只刪 `ls-remote` 還看得到的，`git push origin --delete $B1 $B2 …`。
5. **herdr tab／pane**：`herdr tab close $T`；沒有 worktree 的孤兒 workspace 用 `herdr workspace close $W`。
6. **lavish**：`lavish-axi end $HTML`。

指令被 auto mode classifier 擋下時不換寫法繞過，把指令列給使用者用 `! herdr workspace close w3A` 自己跑。

## 6. 驗證

重跑第 2 步的盤點，回報：

| 項目 | 清掉 | 保留（原因） | 待使用者手動 |
|---|---|---|---|

**完成條件**：manifest 每一列都落在這三欄之一；`git worktree list`、`git branch`、`herdr workspace list` 的實際輸出跟回報一致。

## 踩過的雷

| 現象 | 原因 | 做法 |
|---|---|---|
| `cannot delete branch … used by worktree` | 只關了 herdr workspace，worktree 還在 | 用 `herdr worktree remove`，或先 `git worktree remove` 再刪分支 |
| `is not a working tree` | `herdr worktree remove` 已經順手移除了 | 先看 `git worktree list`，再決定要不要補 `git worktree remove` |
| `not fully merged` | squash merge，分支 commit 不在 main 歷史裡 | 確認 PR MERGED 後用 `-D` |
| `remote ref does not exist` | `gh pr merge --delete-branch` 已刪過 | 刪前先 `git ls-remote --heads origin` |
| 刪完才知道要留（`exp-19-openwiki-init`） | 沒問就 `--force` 掉有改動的 worktree | 「會遺失」一律先問；選刪也先封存 |
| scratchpad 裡的 salt、錄製檔差點跟著刪 | 不在 git 裡，`status` 看不到 | 盤點時查 `--ignored` 與本 session 的 scratchpad |
| `herdr workspace close` 被 classifier 擋 | auto mode 權限 | 列給使用者手動跑 |
