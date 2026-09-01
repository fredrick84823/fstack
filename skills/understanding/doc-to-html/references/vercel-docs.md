# Vercel-inspired Documentation Style

> `style_id: vercel`  
> 適用於：RFC、系統設計、架構文件、工程提案、技術決策、產品技術概覽。  
> 此風格只借鑑極簡文件產品的設計原則，不複製官方網站、品牌資產或商標。

## 1. 呈現目標

讓讀者在很短時間內掌握：

1. 問題是什麼。
2. 系統如何運作。
3. 做了哪些決策與取捨。
4. 接下來要執行什麼。

視覺語言必須精準、克制、偏工程感。主要靠 typography、spacing、grid、border 與資訊層級建立質感，不依賴裝飾性插圖。

### 最適合

- Architecture design / system design
- RFC / ADR / technical proposal
- Migration、rollout、reliability、performance 文件
- 技術產品概覽與高階工程簡報式文件
- 需要大量 diagram、decision、risk、metrics 的文件

### 不適合優先使用

- 以 API 範例與參數查找為主的 reference
- 長篇逐字會議紀錄
- 需要大量 checklist、database、協作屬性的知識庫頁面

---

## 2. Design Tokens

使用中性色、細邊框、少量高對比 accent。不要使用品牌 logo 或複製官方 token。

```css
:root {
  --bg: #ffffff;
  --surface: #fafafa;
  --surface-elevated: #ffffff;
  --text: #18181b;
  --text-muted: #71717a;
  --text-faint: #a1a1aa;
  --border: #e4e4e7;
  --border-strong: #d4d4d8;
  --accent: #111827;
  --accent-contrast: #ffffff;
  --success: #147d64;
  --warning: #9a6700;
  --danger: #b42318;
  --info: #2563eb;

  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
  --shadow-soft: 0 1px 2px rgb(0 0 0 / 0.04), 0 8px 24px rgb(0 0 0 / 0.04);

  --font-sans: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  --content-width: 760px;
  --page-width: 1440px;
  --left-rail: 220px;
  --right-rail: 210px;
  --rail-gap: 60px;
}
```

Dark：貼 [theme-toggle.md](theme-toggle.md) 的 `:root[data-theme="dark"]`。

### Typography

| 元件 | 建議 |
|---|---|
| H1 | `clamp(2.4rem, 5vw, 4.5rem)`；字重 650–750；緊字距 |
| Lead | 1.15–1.35rem；muted；最大寬度約 65ch |
| H2 | 1.7–2rem；上方保留明顯節奏 |
| H3 | 1.15–1.35rem；搭配短說明 |
| Body | 16–18px；line-height 1.7–1.8 |
| Label | 12–13px；字重 600；適度 uppercase 或 tracking |
| Code | 13–14px；line-height 約 1.6 |

不要用超過三種字重。粗體只用來強調結論與關鍵名詞。

---

## 3. Page Layout

`layout` 是獨立於 `style` 的版面 preset。使用者明確指定
`layout: reading` 或 `layout: wide` 時，以指定值為準；只有
`layout: auto` 才依文件風格與語意自動選擇。

### `layout: wide` — 桌面三欄

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ Top bar / document identity                                               │
├──────────────────┬───────────────────────────────────────┬────────────────┤
│ Sections         │ Main article                          │ On this page   │
│ 220px            │ minmax(0, 1fr)                        │ 210px          │
└──────────────────┴───────────────────────────────────────┴────────────────┘
```

- 適合 architecture、system design、RFC、engineering overview。
- page width 約 `1440px`；左 rail `220px`、右 rail `210px`、rail gap `60px`。
- 左右 rail 靠近 viewport 邊緣；中央欄使用 `minmax(0, 1fr)` 吃掉剩餘空間，
  不固定成 `790px`，因此正文比 `reading` 更寬。
- 只有 `layout: wide` 啟用以下 page-wide grid，不得把它變成所有文件的固定預設：

```css
:root {
  --page-width: 1440px;
  --left-rail: 220px;
  --right-rail: 210px;
  --rail-gap: 60px;
}

.layout {
  width: min(var(--page-width), calc(100% - 40px));
  display: grid;
  grid-template-columns: var(--left-rail) minmax(0, 1fr) var(--right-rail);
  gap: var(--rail-gap);
}
```

- 左側 Sections navigation 與右側 On this page TOC 在桌面 sticky；print 時
  必須退回一般文件流或隱藏，不得留下大面積空白。

### `layout: reading` — 窄版閱讀

- 保留目前約 `720–780px` 的正文閱讀寬度（`--content-width`）。
- 適合一般 PRD、研究筆記與長篇敘事文件；不顯示 wide 的三欄 rail。
- `layout: reading` 不得被自動判斷改成 `wide`。

### `layout: auto`

- `vercel` + architecture／system design／RFC／engineering 文件 → `wide`。
- `stripe` 文件 → `reading`。
- `notion` 文件 → `reading`。
- 其他情況 → `reading`。

### Responsive behavior

- 約 `1050px`：隱藏右側 TOC 或切換成兩欄，保留左側 Sections 與中央正文。
- `720px` 以下：改成單欄；左側導覽收進 drawer 或 `<details>`，右側 TOC
  移到正文前成為「本頁目錄」。
- Card、metric、comparison 一律單欄。
- 不保留會遮住內容的 fixed floating controls。
- 所有 breakpoint 都必須避免水平 overflow；sticky rail 可在單欄時改成
  一般文件流。

## 3.1 Anti-patterns

- 把 `wide` 當成所有文件的全域固定預設；`layout: auto` 仍須讓一般文件
  使用 `reading`。
- 將中央欄固定成 `790px`，或用固定三欄寬度導致正文被擠窄；中央欄必須是
  `minmax(0, 1fr)`。
- 以 JavaScript-only layout、外部 font 或新 dependency 取代 CSS grid 與
  現有 responsive/print/accessibility 能力。
- 為了 wide 版面引入水平捲動、破壞 keyboard focus、
  `prefers-reduced-motion` 或 print CSS。

---

## 4. 元件規格

### 4.1 Document Hero

**用途：** 讓讀者立即理解文件主題、狀態與閱讀價值。

結構：

```html
<header class="doc-hero">
  <p class="eyebrow">System Design · RFC-024</p>
  <h1>Event Processing Architecture</h1>
  <p class="lede">說明問題、提案與影響範圍，控制在 2–3 行。</p>
  <div class="meta-row">Status · Owner · Updated · Reading time</div>
</header>
```

呈現規則：

- 標題大但不使用背景圖。
- Eyebrow、metadata 使用 muted 色。
- 可放 2–4 個狀態 badge，但不要做成彩色標籤牆。
- Hero 下方可接「核心結論」或 3 個 metric cards。

### 4.2 Section Header

- H2 左側可有短小 section index，例如 `01`、`02`。
- 標題下方最多一段 section intro。
- 章節間以大留白分隔，不要每段都加粗橫線。
- Anchor link 在 hover/focus 顯示，但鍵盤可達。

### 4.3 Summary / Key Takeaways

使用 2–4 張低裝飾卡片：

- 1px border
- 10–14px radius
- 幾乎無 shadow
- 數字或結論為主，說明最多 2–3 行

適合呈現：目標、影響、SLO、成本、時程、決策結果。

### 4.4 Architecture Card

```html
<figure class="architecture-card">
  <div class="diagram-toolbar">Architecture · Copy source</div>
  <div class="diagram-canvas">...</div>
  <figcaption>圖中只描述的主要責任與資料流。</figcaption>
</figure>
```

規則：

- 容器使用淡灰 surface 與細邊框。
- 節點以白底卡片、6–10px radius、深色標籤呈現。
- 線條多用灰階；只用一種 accent 標示 critical path。
- 把 trust boundary、sync/async、read/write 以線型或小標籤表達，不用多色。
- Diagram 前說明「要看什麼」，圖後整理 2–4 個洞察。

### 4.5 Decision Card

每個決策包含：

```text
Decision
Chosen option
Why
Trade-offs
Revisit trigger
```

- 左側可用 3px 深色 accent bar。
- `Chosen`、`Rejected`、`Deferred` 只使用低飽和狀態色。
- 多方案時先用 comparison table，再用單張 decision card 收斂結論。

### 4.6 Callout

| 類型 | 視覺 |
|---|---|
| Note | 灰底、info icon、無強烈色塊 |
| Important | 淡藍底或左側藍線 |
| Warning | 淡黃底、深黃文字 |
| Risk | 淡紅底、深紅文字 |
| Success | 淡綠底、深綠文字 |

Callout 應包含簡短標題。正文超過兩段時應改成一般 section，而不是巨大 Callout。

### 4.7 Code Block

- 預設淺色頁面可使用近黑 code panel，與正文形成清晰層次。
- 上方 toolbar 顯示語言、檔名、copy。
- 長程式碼可摺疊，但首段與關鍵行需預設可見。
- Line highlighting 只標示本段解釋的行。
- Inline code 使用淡灰底，不使用高飽和色。

### 4.8 Tables

- 表頭 sticky，背景接近頁面底色。
- 欄線最小化，主要使用 row divider。
- 第一欄可 sticky，但只在寬表使用。
- 數字右對齊；狀態使用小型 badge。
- 方案比較表應把選定方案放第一欄或明確標示，不以顏色作唯一線索。

### 4.9 Metrics

- 大數字 + 單位 + 一句解釋。
- 沒有時間序列資料時不要生成折線圖。
- 有趨勢才使用 sparkline，且提供文字趨勢，例如「近 30 天下降 18%」。
- 重要指標最多 4 個；其餘放入表格。

### 4.10 Timeline / Rollout

- 水平 timeline 用於 3–6 個階段；更長時改垂直。
- 每個節點只保留日期、階段名、exit criteria。
- 目前階段使用實心節點；未來階段使用空心節點。
- Rollback 與 gate 必須以清楚標籤呈現。

### 4.11 Risk Matrix

- 嚴重度與可能性使用 3×3 或 4×4 即可。
- 不使用彩虹色；採低飽和綠／黃／紅。
- 每個風險都連回 mitigation table 的對應 anchor。

### 4.12 Accordion / Appendix

- 僅用於補充資料、長 logs、替代方案細節或 glossary。
- 核心決策、限制與風險不得預設收合。
- 使用原生 `<details><summary>`，確保無 JS 仍可用。

---

## 5. Diagram Treatment

### 外觀方向

Figure 使用淡灰 surface、細邊框與黑白節點；critical path 最多一種低飽和 accent。
Mermaid source 只寫語意，不放顏色。

### 圖表選擇

- Architecture：flowchart 或 C4-like block layout。
- Request lifecycle：sequence diagram。
- State transition：state diagram。
- Data model：ER diagram；若欄位很多，只顯示關鍵欄位。
- Rollout：timeline 或 CSS milestone rail。

### 禁止事項

- 每個節點不同顏色。
- 以漸層或 neon 製造「科技感」。
- 節點內放完整段落。
- 無 caption、無圖後解釋。

---

## 6. Interaction

可使用：

- Sticky TOC 與 active section。
- Copy code / copy Mermaid source。
- `<details>` appendix。
- 深淺 toggle：見 [theme-toggle.md](theme-toggle.md)（預設必帶）。

避免：

- 滾動觸發的大量動畫。
- 卡片 3D tilt。
- 無實質作用的 cursor effect。
- 進場動畫延遲正文閱讀。

所有動畫遵守 `prefers-reduced-motion`。

---

## 7. 一鍵呼叫 Prompt

```text
請將提供的內容轉成 Vercel-inspired 的技術文件 HTML。這不是品牌官網複製，而是採用極簡、黑白中性色、細邊框、清楚 typography 與工程文件資訊層級。

請特別做到：
1. 先整理 Executive summary、Context、Architecture、Decisions、Trade-offs、Risks、Rollout 與 Open questions；只保留來源中存在的內容。
2. 使用寬版 Hero、左側章節導覽、中央閱讀欄與右側 sticky TOC；手機版改成單欄。
3. 使用低裝飾的 metric cards、decision cards、comparison matrix、risk table 與 timeline。
4. Architecture、request flow、state 或 rollout 有明確關係時使用 Mermaid；圖前說明閱讀重點，圖後列出洞察。
5. 預設輸出單一 index.html，內嵌 CSS 與少量 JS，支援列印、鍵盤操作、reduced motion 與深淺 toggle。
6. 不使用品牌 logo、不逐像素複製網站、不加入無意義漸層或動畫，也不得補造原文件沒有的事實。
```

---

## 8. 驗收標準

- [ ] 首屏能在 10 秒內傳達問題、方案與狀態。
- [ ] 至少一個核心視覺元件直接幫助理解，而不是裝飾。
- [ ] Architecture 與 decision 的層級比一般正文更突出。
- [ ] 色彩克制；主要靠 spacing、border、type 建立風格。
- [ ] 長表格、程式碼與 diagram 在手機不破版。
- [ ] 核心資訊不依賴 hover 或 JS。
- [ ] 沒有官方品牌資產與誤導性聲明。
