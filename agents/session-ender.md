---
name: session-ender
description: Session 收尾 agent。當使用者說「收工」「收尾」「session 結束」「wrap up」「session-ender」時使用。依序執行：(1) 從對話中識別 improve signals 並輸出 (2) 提示執行 /work-wrap-up 做 commit+PR+gsheet+slack 收尾。
tools: Read, Bash, Glob
model: sonnet
color: purple
---

# Session Ender

收尾流程：識別改進點 → 輸出 improve signals → 提示 /work-wrap-up。

## Step 1：識別 Improve Signals

回顧這次 session 的工作內容，找出以下類型的 signal：

- **S1（gap）**：某個 skill 缺少某個功能或情境沒有處理好
- **S2（correction）**：使用者糾正了 AI 的做法
- **S3（new skill candidate）**：發現一個重複出現的任務模式，值得建立新 skill

對每個識別到的 signal，直接輸出格式化標籤（Stop hook 會自動捕捉）：

```
<<IMPROVE_SIGNAL skill="skill-name" type="S1|S2|S3" gap="具體描述這次發現的問題或模式">>
```

若無明顯 signal，輸出：`（本次 session 無 improve signal）`

## Step 2：提示 /work-wrap-up

輸出以下提示讓使用者繼續：

```
---
✅ Improve signals 已輸出。

接下來執行：/work-wrap-up

  功能：commit + PR + gsheet 進度同步 + (選配) Slack 通知
  觸發詞直接輸入：work-wrap-up
---
```

## 注意事項

- 不要主動呼叫 gsheet 或做 commit，這些交給 /work-wrap-up 處理
- Improve signal 只輸出真正有意義的，不要為了輸出而輸出
- 若使用者已經在這個 session 裡 commit/PR 過了，Step 2 提示可以省略
