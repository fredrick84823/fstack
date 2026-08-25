---
name: doc-to-html
description: Convert RFCs, design docs, API docs, PRDs, research notes, and knowledge-base content into readable, visual, responsive single-page HTML.
disable-model-invocation: true
---

# Documentation HTML Styles

把既有文件轉換為高品質 HTML，而不是只替 Markdown 套一層 CSS。先理解內容的資訊結構，再選擇版面、元件與圖表，盡可能用互動與視覺化呈現，輸出可閱讀、可導覽、可列印、桌機與手機都能用的單頁文件。

## 選風格

載入對應風格檔，完整遵守其 design tokens、layout rules、component recipes、diagram treatment、responsive behavior 與 anti-patterns。不得只換色彩——三種風格的資訊密度、元件結構與互動方式也必須明顯不同。

| 風格 | 觸發條件 | 風格檔 |
|---|---|---|
| `stripe` | API endpoint / SDK / CLI / 整合與安裝教學；程式碼、schema 與參數表約占 1/3 以上，讀者需邊看說明邊複製程式碼 | [references/stripe-docs.md](references/stripe-docs.md) |
| `vercel` | 系統架構、技術決策、設計原則、方案比較、風險分析、RFC；需要 diagram、decision card、metric、timeline 建立全貌 | [references/vercel-docs.md](references/vercel-docs.md) |
| `notion` | PRD、專案狀態、會議紀錄、研究筆記、知識庫、政策；需要 Checklist、Properties、Callout、Toggle、可摺疊補充資料 | [references/notion-docs.md](references/notion-docs.md) |

不明確時：工程決策 → `vercel`；開發者操作 → `stripe`；團隊協作與知識管理 → `notion`。不要混用三種視覺語言；只有使用者明確要求 `hybrid` 才混合，且仍須選一個主風格。

可覆寫的參數：`style`、`layout`、`theme`（預設 `auto` / `auto` / `light`）。

## 版面

使用者指定 `layout: reading | wide` 時直接採用，優先於任何自動判斷。自動時 `vercel` + 架構／系統設計／RFC → `wide`，其餘 → `reading`（單欄 720–780px 或風格檔既有的 `--content-width`）。

`wide` = 桌面三欄 grid（左 Sections / 正文 / 右 On this page）：page `1440px`、left rail `220px`、right rail `210px`、gap `60px`，中央用 `minmax(0, 1fr)` 吃掉剩餘寬度，不得固定成 `790px`。約 `1050px` 收掉右側 TOC，`720px` 以下轉單欄，不得水平 overflow。

## 目標

- **不創造事實**：保留原文的主張、數字、名稱、日期、程式碼與限制。可重排以提升閱讀性，但不改變原意；不確定的標「待確認」。
- **資訊架構由內容決定**：只呈現實際存在的區塊，不要為了模板完整而生出空章節。
- **有語意關係才畫圖**，一張圖只回答一個主要問題，節點標籤保持短句、細節放圖後。流程、sequence、state、class、ER、XY chart 與簡單架構優先使用 Mermaid；只有 Mermaid 無法表達的高度客製 infographic 才用 inline SVG/CSS，並在產出紀錄說明例外原因。

## Diagram interaction contract

Mermaid family 可表達時 **MUST** 載入並使用 `beautiful-mermaid` 渲染，不得手寫等價
inline SVG。單檔 HTML 中的 diagram 預設為 embedded interactive viewer；只有使用者明確
要求 static、產出專供 print/PDF，或禁止 JavaScript 時才靜態化。

唯一互動實作是 `../beautiful-mermaid/scripts/lib/html.js` 的 `embeddedFigure()`、
`embeddedViewerCSS()`、`embeddedViewerScript()`；完整組頁可用 `embeddedDocument()`。
不得在本 skill、產出頁或風格檔複製／改寫 viewer JS。需要組頁時先載入
[`beautiful-mermaid` integration guide](../beautiful-mermaid/references/integration-guide.md#embedded-multi-instance-viewer)。
三個 style reference 只決定 figure 的外觀與文件資訊層級，不改變互動行為。

每張圖保留 package-rendered inline SVG、caption/accessible label 與 Mermaid source/failure
文字（可放相鄰 `<details>`）；JS 關閉及 print 時 SVG 仍須可讀。

### C4 架構圖

依來源證據選擇最少必要層級：

- **C1 Context**：person、目標 system、external system 與關係。
- **C2 Container**：system boundary 內的 deployable runtime、store 與連線。
- **C3 Component**：單一 container 內有來源證據的責任與關係。
- **C4 Code**：僅在文件主要討論 class / module / function 的結構、依賴或呼叫時使用；code snippet 或 SDK call 不算。

一張圖只呈現一個 level，同一文件可用多張圖；缺少證據就省略，不得創造節點或關係。各圖只回答一個問題，跨層沿用相同命名，置中呈現；桌面寬度 720–900px，手機可水平捲動。

## 產出語意化 HTML

MUST：

- 語意標籤（`header` / `nav` / `main` / `article` / `section` / `aside` / `footer`）與正確的 `h1`–`h4` 階層，不用字級假裝標題。
- 圖表與 diagram 都要有標題、caption 或 accessible label，並附上下文與結論。
- 互動元件可鍵盤操作且有清楚 focus state；支援 `prefers-reduced-motion`；表格窄螢幕可水平捲動；文字對比符合 WCAG AA；預設 system font。
- 自動目錄、目前章節提示、anchor links、複製程式碼按鈕。
- `@media print` 隱藏導覽與互動控制；設計 token 集中在 CSS variables。
- JS 不是閱讀的必要條件；關閉 JS 仍能讀完核心內容。

MUST NOT：

- 使用 Vercel / Stripe / Notion 的 logo、商標，或宣稱官方模板；逐像素複製任何網站。
- 無意義的漸層、玻璃擬態、3D 動畫或浮動裝飾。
- 把關鍵資訊藏在預設關閉的互動元件內，或只在 hover 時才看得到。
- 捏造數字、引用或不存在的連結；同頁混用衝突的 radius、shadow、色彩與圖表語言。

## 輸出契約

單檔模式，CSS、icon SVG 與輕量 JS 全部內嵌：

```text
rules: xxxx-xx-xx_page-name.html
example: 2026-07-16_bigquery-mcp-architecture-design.html
```

beautiful-mermaid runtime、CSS 與 SVG 全部內嵌，不依賴 CDN。

## 驗證 completion criteria

用 browser automation 執行後才算完成，不以目視代替：

- [ ] `window.__mermaidViewers.length` 等於圖數，document IDs 無重複。
- [ ] 操作 A 的 zoom/pan/toolbar/keyboard 後，B 的 `state()` 完全不變。
- [ ] 普通 wheel 未被 `preventDefault` 且頁面可捲；Ctrl/Cmd+wheel 或 pinch 會 zoom。
- [ ] 每圖 `Fit`、`1:1`、拖曳 pan 與 focused keyboard 均可操作。
- [ ] 390px viewport 無全頁水平 overflow；單指 touch 未被 viewer 永久攔截。
- [ ] 禁用 JS 後 SVG、caption、fallback 可讀；print 隱藏 controls 且保留靜態 SVG。
- [ ] 無 remote dependency、console error；每張圖均由 beautiful-mermaid renderer 產出。
