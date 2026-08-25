# Notion-inspired Knowledge Document Style

> `style_id: notion`  
> 適用於：PRD、專案計畫、研究筆記、知識庫、會議紀錄、政策文件、團隊協作與持續更新的工作文件。  
> 此風格只借鑑區塊化知識工具的設計原則，不複製官方網站、品牌資產或商標。

## 1. 呈現目標

讓文件像一個可以持續工作的知識頁面：容易掃描、容易補充、容易追蹤狀態，也適合把背景、決策、任務與附件放在同一頁。

核心不是複雜導覽，而是「自然的內容流 + 可組合的 blocks」。

### 最適合

- PRD、project brief、launch plan
- Meeting notes、decision log、retrospective
- Research notes、competitive analysis、knowledge base
- Policy、playbook、SOP、onboarding handbook
- 包含 checklist、properties、callout、table、timeline 的團隊文件

### 不適合優先使用

- 高密度 API reference
- 需要固定雙欄 code explorer 的 developer docs
- 需要大量全寬 architecture panels 的工程展示頁

---

## 2. Design Tokens

使用偏暖的紙張底色、柔和灰階、低飽和 callout 背景與簡潔 block spacing。避免把每個 block 都做成有陰影的卡片。

```css
:root {
  --bg: #ffffff;
  --page: #ffffff;
  --text: #2f3437;
  --text-muted: #787774;
  --text-faint: #9b9a97;
  --border: #e9e9e7;
  --surface: #f7f7f5;
  --surface-hover: #f1f1ef;

  --gray-soft: #f1f1ef;
  --blue-soft: #e7f3f8;
  --green-soft: #edf3ec;
  --yellow-soft: #fbf3db;
  --orange-soft: #faebdd;
  --red-soft: #fdebec;
  --purple-soft: #f3e8f7;

  --blue-text: #24566f;
  --green-text: #32623f;
  --yellow-text: #7b5b16;
  --red-text: #9b2c2c;

  --radius-sm: 4px;
  --radius-md: 7px;
  --radius-lg: 10px;
  --shadow-menu: 0 8px 24px rgb(15 23 42 / 0.10);

  --font-sans: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  --page-width: 820px;
}
```

### Typography

| 元件 | 建議 |
|---|---|
| Page title | 2.5–3.3rem；字重 700；自然換行 |
| H1 section | 1.85–2.2rem |
| H2 | 1.45–1.7rem |
| H3 | 1.15–1.3rem |
| Body | 16–17px；line-height 1.7–1.8 |
| Caption / property | 12–14px；muted |
| Code | 13–14px monospace |

正文不應過度寬。長篇閱讀維持 680–820px；資料表與 board 可以暫時突破頁寬。

---

## 3. Page Layout

### 預設單頁

```text
┌──────────────────────────────────────────────────┐
│ Breadcrumb / workspace path                      │
│ Page icon (optional)                             │
│ Page title                                       │
│ Description                                      │
│ Properties                                       │
├──────────────────────────────────────────────────┤
│ Content blocks                                   │
│ Callout · headings · tables · toggles · timeline │
└──────────────────────────────────────────────────┘
```

- 主體是單一置中 page，不預設永久左側導覽。
- 大文件可增加可收合 outline sidebar，但不搶過正文。
- 頁面頂端可以有 icon，但預設使用簡單 inline SVG，不使用隨機 emoji。
- Cover 只有使用者明確要求或文件具有 editorial 性質時才使用。

### 手機

- Page padding 降低。
- Properties 由多欄改為 definition list。
- Columns 改成單欄。
- Tables 可捲動；board cards 改垂直列表。
- Floating outline 改為 `<details>`。

---

## 4. 元件規格

### 4.1 Page Header

```html
<header class="page-header">
  <nav class="breadcrumb">Workspace / Product / PRD</nav>
  <div class="page-icon" aria-hidden="true">...</div>
  <h1>Search Quality Improvements</h1>
  <p class="page-description">一句話描述文件目的與目前狀態。</p>
</header>
```

- Title 前可以有 icon，但保持克制。
- Description 以 muted 色呈現，最多 2–3 行。
- 若有 owner、status、date、team，在 title 後直接放 Properties。

### 4.2 Properties

建議欄位：

```text
Status | Owner | Team | Last updated | Target date | Priority | Related docs
```

- 使用兩欄或三欄 definition grid。
- Status 與 priority 使用低飽和 pill。
- 缺少資料就省略，不產生 `TBD` 牆；只有原文真的待定時才顯示。
- Properties 是 metadata，不要放長段落。

### 4.3 Callout

```html
<aside class="callout callout-blue">
  <div class="callout-icon">...</div>
  <div>
    <strong>Context</strong>
    <p>簡短重點。</p>
  </div>
</aside>
```

建議映射：

| 類型 | 背景 |
|---|---|
| Context / Info | 淡藍 |
| Success / Decision | 淡綠 |
| Caution / Pending | 淡黃 |
| Risk / Blocker | 淡紅 |
| Note / Definition | 淡灰 |
| Research / Insight | 淡紫 |

- Callout 可以有 1–3 段，但不要放整個章節。
- 一頁最多約 5–7 個醒目色 Callout，避免失去重點。
- Icon 必須有意義；裝飾性 icon 設 `aria-hidden="true"`。

### 4.4 Toggle / Details

適合：

- 補充研究資料
- FAQ
- Glossary
- Meeting transcript
- Alternative options
- Appendix

使用原生：

```html
<details class="toggle-block">
  <summary>查看替代方案與未採用原因</summary>
  <div class="toggle-content">...</div>
</details>
```

核心決策、風險、deadline 與 action items 不得預設收合。

### 4.5 Checklist

```html
<ul class="task-list">
  <li><input type="checkbox" disabled checked> 已完成事項</li>
  <li><input type="checkbox" disabled> 待辦事項</li>
</ul>
```

- 文件是靜態輸出時 checkbox 使用 disabled，避免讓使用者誤以為狀態會被儲存。
- 每項可附 owner、due date、status，但不要把一句任務塞成多行卡片。
- 需要排序與篩選時改用 task table。

### 4.6 Decision Log

建議表格：

```text
Date | Decision | Rationale | Owner | Status | Revisit trigger
```

- 重要決策可使用淡綠 callout 做摘要。
- 被推翻的決策保留歷史，標示 superseded 與新決策 anchor。
- 不把每個小偏好都列成 decision log。

### 4.7 Meeting Notes

固定節奏：

```text
Meeting metadata
Purpose
Discussion highlights
Decisions
Action items
Parking lot
References
```

- Discussion 只保留摘要，不模擬逐字稿。
- Action items 必須包含 owner；日期只在來源有提供時顯示。
- Parking lot 放尚未處理但值得保留的議題。

### 4.8 Table / Database-like View

- 表格使用輕量 row divider，不做厚重 dashboard table。
- 第一列可 sticky。
- Select / multi-select 以低飽和 pills 呈現。
- 長內容欄位可截斷並提供展開，但列印時顯示完整內容。
- 靜態 HTML 不呈現假的 filter、sort、edit UI；只有真的實作時才顯示控制項。

### 4.9 Kanban / Status Board

適用於項目數約 6–20、狀態明確的工作。

- 欄位通常為 `Backlog / In progress / Review / Done`，但必須依來源命名。
- 卡片包含 title、owner、priority、due date；避免放長說明。
- 手機版改為按狀態分組的垂直列表。
- 超過 20–30 張卡片時改用 table，不要造成無限橫向捲動。

### 4.10 Timeline

- 研究、專案或 launch 以垂直 timeline 呈現最自然。
- 每個節點包含日期／期間、事件、結果或 next step。
- Past / current / future 使用實心度或邊框差異，不只靠顏色。
- 沒有確切日期時使用 phase，不捏造日期。

### 4.11 Columns

- 兩欄適合 Pros/Cons、Problem/Solution、Now/Next。
- 三欄只適合短內容，例如三個目標或角色。
- 長正文不要硬塞多欄。
- 手機一律單欄，並保留合理閱讀順序。

### 4.12 Quote / Insight

- Quote block 只用於來源中存在的引述或明確 insight。
- 不使用大型裝飾引號占據半頁。
- 有來源時附上 attribution；無來源不要偽造。

### 4.13 Code / Formula

- Inline code 使用淡灰背景。
- Block code 使用淺色或中深色皆可，但要保持整體紙張感。
- 公式以 KaTeX/MathJax 只有在來源包含數學內容且允許外部依賴時使用。
- 程式碼很多時應考慮改用 `stripe` 風格，而不是強行塞進此版型。

### 4.14 Embedded Diagram Block

```html
<figure class="diagram-block">
  <div class="diagram-title">User research synthesis flow</div>
  <div class="diagram-canvas">...</div>
  <figcaption>一句話說明圖的結論。</figcaption>
</figure>
```

- 視覺像內容 block，不做大型 dashboard panel。
- 背景可使用淡灰，邊框極淡。
- 線條與節點使用柔和灰階，加一種語意 accent。
- Diagram 後方可接「What this means」callout。

---

## 5. Diagram Treatment

### 優先使用

- Project timeline / launch phases
- User journey / service flow
- Research synthesis map
- Decision tree
- Simple architecture overview
- Status flow

### 視覺規則

- 圖表看起來像文件中的一個 block，而不是獨立控制台。
- Mermaid 節點採柔和 surface 與 4–8px radius。
- 標籤可稍長於 Vercel 風格，但仍避免完整段落。
- 一張圖後附上摘要、決策或 action items。

### 外觀方向

Figure 像內容 block：暖白／淡灰 surface、極淡邊框與一種柔和 accent，不做控制台感。
Mermaid source 只寫語意，不放顏色。

---

## 6. Interaction

可使用：

- `<details>` toggles。
- Floating outline（大文件）。
- Copy anchor / copy code。
- 簡單 table filter（只有真的實作）。
- Expand full row / full note。
- Theme switch（使用者要求時）。

避免：

- 模擬可編輯但實際不會儲存的內容區。
- 拖曳卡片但無 persistence。
- 大量 hover-only controls。
- 過度動畫與卡片陰影。
- 隨機 emoji 作為所有 section icon。

---

## 7. 一鍵呼叫 Prompt

```text
請將提供的內容轉成 Notion-inspired 的知識文件 HTML。這不是品牌官網複製，而是採用單頁紙張感、自然內容流、柔和灰階、properties、callouts、toggles、checklists、database-like tables 與可持續更新的區塊化資訊設計。

請特別做到：
1. 依內容整理 Page description、Properties、Context、Goals、Requirements、Research、Decisions、Action items、Timeline、Open questions 與 Appendix；只建立來源中有實際內容的章節。
2. 以 680–820px 置中閱讀欄為主；資料表、board 或 diagram 才可暫時加寬。手機版改為單欄。
3. 適度使用淡色 Callout、原生 details/summary、disabled checklist、decision log、properties grid 與垂直 timeline。
4. PRD 顯示目標、non-goals、requirements、success metrics、risks 與 launch plan；會議文件顯示 decisions、action items 與 parking lot。
5. Diagram 要像一個文件 block，使用柔和灰階與單一 accent；圖後整理 What this means 或 next actions。
6. 預設輸出單一 index.html，支援列印、鍵盤操作、responsive tables 與 reduced motion。
7. 不使用品牌 logo、不逐像素複製網站、不模擬無法儲存的編輯功能，也不得補造 owner、日期、狀態或其他事實。
```

---

## 8. 驗收標準

- [ ] 頁首清楚顯示文件目的與有效 metadata。
- [ ] 內容像自然可讀的知識頁，而不是一堆有陰影卡片。
- [ ] Callout 色彩有語意且數量克制。
- [ ] 核心決策、風險與 action items 預設可見。
- [ ] Toggle 只承載補充內容。
- [ ] 靜態 UI 不冒充可儲存的編輯器或資料庫。
- [ ] Properties、columns、tables 與 board 在手機可讀。
- [ ] 不捏造日期、owner、status、引用或研究結果。
