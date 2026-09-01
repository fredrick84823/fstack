---
name: writing-great-issues
description: 把一個問題、提案或工作項寫成顆粒度適中、一目瞭然的 GitHub issue，預設產出 draft 審過才用 gh 建立。當使用者要開 issue、回報 bug、提功能提案，或要把討論結論記成 issue 時使用。
---

# Writing Great Issues

**一張 issue = 一個 PR 能收掉的量。** 超過就升級成 epic + 子 issue；小於一個 PR 的雜項，併進最相關的既有 issue 當 checkbox。

一目瞭然的定義：接手的人讀完不用追問第二句就能動手。標題決定這張會不會被點開，第一段決定讀的人要不要繼續。

## 流程

1. **判型**：bug / feature / task / epic。一句話說不出這張要解決什麼，就先問使用者，不要硬寫。
2. **查重複**：`gh issue list --repo <repo> --search "<關鍵字>" --state all`。已有同題 issue，改成在那張補留言，不開新的。
3. **取材**：從對話、code、PR 蒐集。已寫在 PR、ADR、code comment 的內容一律用連結，不重複貼。
4. **套骨架**：用下方對應類型的 section，空的 section 直接刪，不留 N/A。
5. **過判準表**：逐項檢查，中一項就改。
6. **交付 draft**：把完整 title + body 貼在回覆裡給使用者審。使用者明說要建立，才執行
   `gh issue create --repo <repo> --title "<title>" --body-file <file>`；
   類型 label（`gh label list` 查得到的才帶）用 `--label` 附上。
   完成條件：使用者手上有 title + body 全文，且尚未有任何 issue 被建立。

## 骨架

跟 describe-pr 同一條規則：**每個 `##` / `###` heading 與 `<summary>` 用英文，內文繁體中文**。

### Bug

```
## What happened        一段，含觸發情境
## Expected behavior    和上面分開，各自獨立成段
## Steps to reproduce   最小化、編號列表，從乾淨狀態開始
## Environment / Logs   <details> 收摺；沒有就刪
```

### Feature / 提案

```
## Problem / Use case   先講痛，不先講解法
## Proposed solution
## Alternatives         考慮過但不採用的，一行一個附理由；沒有就刪
```

### Task / Chore

```
## What
## Why                  一行 + 連結
## Done when            一行，可驗證
```

### Epic / Tracking

```
## Goal                 一句話
## Sub-issues           - [ ] #123 checklist，一行一張
```

Epic 本身不寫重現步驟或驗收條件——那些屬於子 issue。

大型設計提案（跨 service、要團隊討論的）套 RFC 骨架：Summary / Motivation / Detailed design / Drawbacks / Alternatives / Unresolved questions。

## 標題

格式 `type(scope): 描述`，與 commit / PR title 同一套詞彙，一張 issue 從開票到 merge 名字連貫。

- type ∈ `fix / feat / spec / chore / test / security / rfc / decision`
- scope 是 server 或模組名；跨多個模組用 repo 慣用的整體 scope（如 `all-servers`），沒有明確 scope 就省略括號
- 描述講行為或結果，不講動作過程：`fix(gsheet-mcp): sheet 名稱沒 quote 進 A1 notation`
- 版本、環境、error code 留在 body

## 視覺化

GitHub 原生渲染 mermaid。三行文字講得清就不畫；講不清才用：

| 內容 | 形式 |
|---|---|
| 流程、狀態、時序 | ```mermaid 圖 |
| 對照、選項取捨 | table |
| 長 log、環境 dump、stack trace | `<details><summary>` + code fence |
| UI 問題 | 截圖直接拖進 body |

## 判準

| 徵狀 | 修法 |
|---|---|
| 標題出現「和」「以及」或兩個動詞 | 拆兩張 |
| Task 寫不出一行 Done when | 範圍太大或還沒想清楚——縮小範圍，或先開成 bug/feature 描述問題 |
| 子任務 checkbox 超過 5 項 | 升級 epic，子項各開 issue |
| What happened 和 Expected behavior 混在同一段 | 拆成兩個 section |
| body 超過一屏 | log 與環境收 `<details>`，論述留主文 |
| 內文貼了 PR / code 已有的段落 | 刪掉換連結 |
| Feature 第一段就是解法 | 補回 use case，解法往後移 |
| 同一張講兩個 bug | 拆 |
