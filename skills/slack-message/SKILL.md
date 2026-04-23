---
name: slack-message
description: |
  當使用者要透過 MCP 傳送 Slack 訊息時使用此 Skill。
  確保訊息格式正確渲染（粗體、連結、列表、code block）。
  Trigger: "發 slack 訊息"、"傳訊息到 channel"、"公告"、"通知同事"、
  "slack_send_message"、"slack_send_message_draft"。
  Use when: 使用者要透過 MCP Slack 工具發送或草擬訊息。
  Do NOT use for: 建立或更新 Slack Canvas（改用 slack-canvas skill）。
allowed-tools:
  - mcp__claude_ai_Slack__slack_send_message
  - mcp__claude_ai_Slack__slack_send_message_draft
  - mcp__claude_ai_Slack__slack_search_channels
  - mcp__claude_ai_Slack__slack_search_users
---

# Slack Message Skill

## 概述

本 Skill 指導如何透過 MCP Slack 工具正確發送訊息，避免格式渲染失敗。
核心發現：MCP 工具使用 **standard markdown**，不是 Slack 原生 mrkdwn。

---

## 1. 格式規則（最重要）

MCP Slack 工具（`slack_send_message`、`slack_send_message_draft`）接受 **standard markdown**。

| 功能 | 正確語法（standard markdown） | 錯誤語法（Slack mrkdwn） | 說明 |
|------|------|------|------|
| 粗體 | `**text**` | `*text*` | 雙星號，非單星號 |
| 斜體 | `_text_` | `_text_` | 兩者相同 |
| 刪除線 | `~text~` | `~text~` | 兩者相同 |
| 連結 | `[顯示文字](https://url)` | `<https://url\|顯示文字>` | 兩者皆可，但建議統一用 standard markdown |
| Inline code | `` `code` `` | `` `code` `` | 兩者相同 |
| Code block | ` ``` ` | ` ``` ` | 兩者相同 |
| 列表 | `- item` | `- item` | 兩者相同 |
| 引用 | `> text` | `> text` | 兩者相同 |

### 關鍵差異

**粗體是最容易踩的坑**：Slack 原生用單星號 `*bold*`，但 MCP 工具用雙星號 `**bold**`。
如果用單星號，文字會被當成斜體或完全不渲染。

### Tilde (`~`) 刪除線陷阱（重要）

`~text~` 單波浪號在 MCP 工具下會觸發刪除線（GFM-style）。
**常見的中文文案陷阱**：使用 `~` 表示「約」（例如 `~3,200 萬筆`），若同一行後面再出現另一個 `~`，兩個 `~` 之間的文字全部變成刪除線。

```
❌ 錯誤範例（產生刪除線）：
每日 ~3,200 萬筆，年度估算~ 120 億筆
→ "3,200 萬筆，年度估算" 被渲染為刪除線

✅ 正確做法（使用中文「約」替代 ~）：
每日約 3,200 萬筆，年度估算約 120 億筆
```

**修正原則**：中文訊息中應以「約」或「≈」替代 `~` 作為近似符號，**禁止**用 `~` 表示約數。

---

## 2. `slack_send_message` vs `slack_send_message_draft`

### 格式渲染差異（重要）

| 工具 | 格式渲染 | 適用場景 |
|------|---------|---------|
| `slack_send_message` | ✅ 完整支援所有 markdown | 正式發送 |
| `slack_send_message_draft` | ❌ 所有 markdown 被轉為純文字 | **不建議用於需要格式的訊息** |

**已知問題**：`slack_send_message_draft` 儲存草稿時會將 markdown 轉為純文字，
送出後粗體、連結、列表、code block 全部消失。這是 Slack Draft API 的限制，非格式問題。

### 使用建議

- **需要格式的訊息**：一律使用 `slack_send_message`
- **純文字訊息**：兩者皆可
- **重要公告**：先用 `slack_send_message` 發到自己的 DM 確認格式，再發到目標頻道

### 發送前預覽格式（替代 Draft 的做法）

由於 `slack_send_message_draft` 無法正確渲染格式，若想在正式發送前確認訊息排版，
應改用 `slack_send_message` **先私訊給自己**：

1. 用 `slack_send_message` 發送到自己的 DM（以自己的 User ID 作為 `channel_id`）
2. 到 Slack 確認格式是否正確（粗體、連結、列表、code block）
3. 確認無誤後，再用相同內容發送到目標頻道

這等同於「preview → confirm → send」的流程，比 draft 更可靠。

---

## 3. 中文訊息排版規範

遵循[中文文案排版指北](https://github.com/sparanoid/chinese-copywriting-guidelines)：

| 規則 | 正確 | 錯誤 |
|------|------|------|
| 中英文之間加空格 | `搭配 Claude 使用` | `搭配Claude使用` |
| 中文與數字之間加空格 | `共 5 個項目` | `共5個項目` |
| 專有名詞正確大寫 | `GitHub`、`Claude`、`MCP`、`Slack` | `github`、`claude`、`mcp`、`slack` |
| 全形標點 | `說明：這是範例，請參考。` | `说明:这是范例,请参考.` |
| 半形括號用於技術內容 | `使用 `slack_send_message` (推薦)` | — |

---

## 4. 訊息撰寫最佳實踐

### 結構建議

1. **開場**：一句話說明主題
2. **背景**：為什麼需要這件事（一句話）
3. **內容**：用 bullet list 列出重點，粗體小標 + 說明
4. **行動**：安裝步驟或操作方式（用 code block）
5. **連結**：相關資源

### 範例

```markdown
大家好 :wave:

剛在 [tagtoo-skills](https://github.com/Tagtoo/tagtoo-skills) 新增了 `example-skill` :sparkles:，
搭配 Claude Code 使用，可以自動完成 XXX。

**為什麼需要？**
一句話說明動機。

**整理了什麼**

- **功能 A** — 說明
- **功能 B** — 說明
- **功能 C** — 說明

**安裝**

\`\`\`
cd tagtoo-skills
./install.sh
\`\`\`

[tagtoo-skills repo](https://github.com/Tagtoo/tagtoo-skills)
```

---

## 5. 發送前檢查清單

1. **粗體用雙星號** `**text**`，不是單星號
2. **連結用 standard markdown** `[text](url)`
3. **中英文之間有空格**
4. **專有名詞正確大寫**
5. **使用 `slack_send_message`**，避免 `slack_send_message_draft`（格式會消失）
6. **先發 DM 給自己測試**，確認格式正確後再發到公開頻道
7. **掃描訊息中的 `~` 字元**：若訊息中有偶數個 `~`，確認是否誤觸刪除線；中文近似值改用「約」

---

## 6. Guardrails

1. **禁止** 使用 `slack_send_message_draft` 發送需要格式的訊息
2. **禁止** 使用 Slack mrkdwn 的單星號粗體 `*text*`
3. **禁止** 未經使用者確認就直接發送到公開頻道
4. **禁止** 在中文訊息中用 `~` 表示「約」（改用「約」或「≈」）
5. **必須** 重要訊息先 DM 自測格式
6. **必須** 中文訊息遵循排版規範（中英文空格、全形標點、正確大寫）
