---
name: work-wrap-up
description: |
  功能完成後的收尾三連發：commit+PR → gsheet 進度同步 → (選配) Slack 通知。
  觸發詞：「work-wrap-up」、「收尾」、「功能做完了」、「幫我收尾」、「wrap up」、
  「wrap」、「做完了」、「push 完了」、「收工」。
  依序執行：commit-commands:commit-push-pr → gsheet-progress-sync → (選配) slack-message。
allowed-tools:
  - Bash
  - mcp__slack__*
  - mcp__google_sheets__*
model: claude-opus-4-6
---

## 你的任務

幫使用者完成功能開發後的標準收尾流程，步驟固定，依序執行：

### Step 1: Commit + Push + PR

使用 `/commit-commands:commit-push-pr` 執行：
- 確認目前 git 狀態
- 提交所有相關變更 (commit 格式完全根據之前的格式)
- Push 到 origin
- 建立 PR（若尚未存在）

若使用者已有 PR 或已 merge，跳過此步驟直接進行 Step 2。

### Step 2: Gsheet 進度同步

使用 `/gsheet-progress-sync` 更新工作進度：
- 詢問使用者目前任務狀態（進行中 / 完成）
- 根據本次變更摘要更新 Google Sheet

### Step 3: Slack 通知（選配）

詢問使用者是否要發送 Slack 通知。
- 若是：使用 `/slack-message` 撰寫並預覽訊息後發送
- 若否：跳過

---

### 守則

- 每個步驟完成後才進行下一步，不要跳步
- Slack 訊息符合 `/brief-mode` 規範，並控制在 20 秒內可讀完
- 若使用者提供任務說明，摘要時直接沿用
- 所有說明內容的語言一律使用繁體中文

### 相依 Skills

此 skill 需要以下 skills 已安裝：
- `commit-commands`（本 repo 提供）
- `gsheet-progress-sync`（本 repo 提供）
- `slack-message`（本 repo 提供）
