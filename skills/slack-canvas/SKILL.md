---
name: slack-canvas
description: |
  當使用者要建立或更新 Slack Canvas 文件時使用此 Skill。
  包含：資安報告、驗證報告、會議記錄、技術說明等任何需要輸出為 Slack Canvas 的內容。
  Trigger: "建立 slack canvas"、"幫我建立 canvas"、"寫成 canvas"、
  "更新 canvas"、"把這份報告放到 slack"、"產出 canvas 格式"。
  Use when: 使用者有結構化內容（報告/摘要/清單）需要在 Slack 中以文件形式呈現。
  Do NOT use for: 只是傳送 Slack 訊息（用 slack_send_message 即可）。
allowed-tools:
  - mcp__claude_ai_Slack__slack_create_canvas
  - mcp__claude_ai_Slack__slack_update_canvas
  - mcp__claude_ai_Slack__slack_read_canvas
---

# Slack Canvas Skill

## 概述

本 Skill 指導如何正確建立與更新 Slack Canvas，避免常見的格式化陷阱。
Slack Canvas 使用 Slack 自家的 Markdown 變體，**與標準 CommonMark 有重要差異**。

---

## 1. Canvas-Specific Markdown 規則（核心禁忌）

### 表格（Tables）

- 欄位內容若包含 `|` 字元，**必須 escape 成 `\|`**
- 撰寫完表格後，**必須自我審查**：逐格確認是否有未 escape 的 `|`
- 表格必須在頂層，不可放在 list item 內

```markdown
# 正確範例
| 欄位 | 說明 |
|------|------|
| A \| B | 包含管道符號 |

# 錯誤範例（會破版）
| 欄位 | 說明 |
|------|------|
| A | B | 未 escape，產生多餘欄位 |
```

### Header 深度限制

- 最多使用 `###`（H3）
- **禁止使用 `####`（H4）及更深層級**，Canvas 不支援

### 區塊元素巢狀限制（重要）

下列元素**必須在頂層**，**不可巢狀在 list item 內**：

| 禁止巢狀的元素 | 後果 |
|---------------|------|
| ` ``` code block ``` ` | 靜默忽略或破版 |
| `# Heading` | 不被解析為標題 |
| `> blockquote` | 顯示為純文字 |

**正確做法**：先結束 list，再在頂層放 code block。

```markdown
# 錯誤範例
- 步驟一
  ```python
  print("hello")
  ```

# 正確範例
- 步驟一

```python
print("hello")
```
```

### Hyperlinks

- 只允許完整 HTTP/HTTPS URL
- 禁止相對路徑或錨點連結

### Images

- `![alt](url)` 必須**獨立一行**，不可 inline 在段落中

---

## 2. Slack-Specific 語法（Canvas 專屬，非標準 Markdown）

| 功能 | 語法 | 說明 |
|------|------|------|
| User mention | `![](@U1234567890)` | 使用 Slack User ID |
| Channel mention | `![](#C1234567890)` | 使用 Slack Channel ID |
| Date heading | `![](slack_date:YYYY-MM-DD)` | 插入日期分隔標題 |
| Callout block | `::: {.callout}` ... `:::` | 高亮提示區塊 |
| 多欄排版（外層） | `::: {.layout}` ... `:::` | 多欄容器 |
| 多欄排版（欄位） | `::: {.column}` ... `:::` | 單欄內容，置於 layout 內 |

### Callout 範例

```markdown
::: {.callout}
這是一個 callout 提示區塊，用於強調重要資訊。
:::
```

### 多欄排版範例

```markdown
::: {.layout}
::: {.column}
**左欄標題**
左欄內容
:::
::: {.column}
**右欄標題**
右欄內容
:::
:::
```

---

## 3. Emoji 對照表（常見錯誤修正）

| 用途 | 正確名稱 | 錯誤名稱（禁用） |
|------|---------|----------------|
| 橙色圓形 | `:large_orange_circle:` | `:orange_circle:` ❌ |
| 黃色圓形 | `:large_yellow_circle:` | `:yellow_circle:` ❌ |
| 藍色圓形 | `:large_blue_circle:` | `:blue_circle:` ❌（顯示不一） |
| 紅色圓形 | `:red_circle:` | `:large_red_circle:` ❌ |
| 綠色打勾 | `:white_check_mark:` | `:check:` ❌ |
| 警告 | `:warning:` | `:alert:` ❌ |
| 資訊 | `:information_source:` | `:info:` ❌ |
| 完成 | `:tada:` 或 `:white_check_mark:` | `:done:` ❌ |

---

## 4. 建立與更新 Canvas 流程

### 新建 Canvas

1. 使用 `slack_create_canvas` 工具
2. 提供 `channel_id`（從使用者提供的 Canvas URL 或 Channel 名稱取得）
3. 回傳 `canvas_url` 給使用者

```
必要參數：
- channel_id: string（Slack Channel ID，如 C1234567890）
- content: string（Markdown 格式的 Canvas 內容）
```

### 更新 Canvas（重要流程）

**禁止**直接進行無 `section_id` 的全域 replace。

正確流程：

1. **先** `slack_read_canvas` 取得完整 `section_id_mapping`
2. 確認目標元素（如特定表格）的 `section_id`
3. 用 `section_id` 精準 replace **目標元素本身**

#### 常見錯誤：target 錯誤的 section_id

**問題**：以 header 的 `section_id` 做 replace，Canvas API 會插入新 block，但原有子元素（表格）被清空後殘留為空表格，造成「先顯示空表格、再顯示正確表格」的雙重元素問題。

**正確做法**：

```
# 錯誤流程
1. 讀取 canvas，找到 "## 查詢結果" header 的 section_id = "s1"
2. 用 section_id "s1" replace → 產生雙重表格

# 正確流程
1. 讀取 canvas，找到 "## 查詢結果" 下方「表格元素本身」的 section_id = "s2"
2. 用 section_id "s2" replace → 精準更新表格
```

---

## 5. 常用報告模板

### 資安審查報告

```markdown
# :shield: 資安審查報告

![](slack_date:YYYY-MM-DD)

## 審查範圍

- 專案名稱：XXX
- 審查日期：YYYY-MM-DD
- 審查人員：![](@UXXX)

## 發現彙整

| 嚴重程度 | 項目 | 說明 | 建議處置 |
|---------|------|------|---------|
| :red_circle: 高 | XXX | 說明 | 建議 |
| :large_yellow_circle: 中 | XXX | 說明 | 建議 |
| :large_blue_circle: 低 | XXX | 說明 | 建議 |

## 整體評估

::: {.callout}
整體風險評估結論與後續行動建議。
:::
```

### 驗證報告

```markdown
# :white_check_mark: 驗證報告

## Context

- 驗證目標：XXX
- 執行時間：YYYY-MM-DD HH:MM

## 查詢結果

| 指標 | 預期值 | 實際值 | 狀態 |
|------|--------|--------|------|
| 資料筆數 | > 0 | 1234 | :white_check_mark: |

## 驗證結論

::: {.callout}
通過 / 失敗 + 原因說明
:::

## 數據洞察

- 洞察一
- 洞察二
```

### 技術說明文件

```markdown
# :books: 技術說明文件

## 背景

說明此技術決策的背景與動機。

## 架構說明

說明整體架構設計。

## 設定選項

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| param_a | string | "default" | 說明 |

## 使用範例

```python
# 範例程式碼（注意：不可巢狀在 list 內）
example_code()
```
```

---

## 6. 內容可讀性指引

### 何時使用 Bullet List

Canvas API 預設建議使用段落式寫作，但以下情境使用 bullet list **可讀性更佳**：

- **分類列舉**：列出多個類型/分類的定義與說明（如整合方式、資料來源分類）
- **分佈/佔比**：列出多個項目各自的數據（如 partner 月均量、佔比）
- **狀態清單**：列出多個項目各自的運行狀態

**原則**：當一個段落包含 3 個以上並列的獨立項目時，改用 bullet list。

**範例**：
```markdown
❌ 段落式（難以快速掃描）：
reurl 佔 93%，月均 5,030 萬筆。carrefour_offline 佔 5.5%，月均 310 萬筆。shopify 已停止。

✅ Bullet list（清楚易讀）：
- **reurl**：佔 93%，月均約 5,030 萬筆
- **carrefour_offline**：佔 5.5%，月均約 310 萬筆
- **shopify**：已幾乎停止，月均 ~300 筆
```

---

## 7. Guardrails（禁止事項）

1. **禁止** list item 內放 code block（Canvas 靜默忽略或破版）
2. **禁止** 無 `section_id` 的全域 replace（會覆蓋整個 canvas）
3. **禁止** 使用 `####` 或更深層 header
4. **禁止** 使用未確認的 emoji 名稱（參照第 3 節對照表）
5. **必須** 在寫完表格後自我審查所有 `|` 是否正確 escape
6. **必須** 更新特定元素時 target 該元素本身的 `section_id`，不可 target 其上方 header 的 `section_id`
7. **禁止** 並行呼叫多個 `slack_update_canvas`（見下方說明）

### 並行更新導致 Canvas 清空（Critical）

**問題**：同時對同一份 Canvas 發起多個 `slack_update_canvas` 呼叫會觸發 race condition，
導致整份 Canvas 內容被清空，僅剩標題。

**根因**：Slack Canvas API 不支援並行寫入。多個 replace 操作同時執行時，
後續操作可能基於過期的 section_id_mapping，造成不可預期的覆寫。

**正確做法**：

- Canvas update **必須逐一串列執行**，等待上一個回傳後再呼叫下一個
- 如果需要大幅修改多個 section，直接用 `action=replace`（不帶 `section_id`）**整份重寫**更安全
- **禁止**用空格或空字串 replace section 來「刪除」內容，改為整份重寫
