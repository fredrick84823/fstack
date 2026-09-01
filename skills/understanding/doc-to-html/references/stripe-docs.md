# Stripe-inspired Developer Documentation Style

> `style_id: stripe`  
> 適用於：API reference、SDK 文件、整合指南、developer onboarding、CLI、程式碼與步驟導向教學。  
> 此風格只借鑑高品質開發者文件的資訊設計，不複製官方網站、品牌資產或商標。

## 1. 呈現目標

讓開發者能在同一個視野中完成三件事：

1. 理解目前步驟或 API 的目的。
2. 查看必要參數、限制與回應。
3. 直接複製可執行的程式碼或命令。

核心不是「漂亮」，而是降低 integration time、查找成本與上下文切換。

### 最適合

- REST / GraphQL / Webhook / SDK 文件
- Quickstart、installation、authentication、migration guide
- CLI 與 command reference
- Request / response、schema、parameter、error code 為主的文件
- 多語言程式碼範例與逐步整合流程

### 不適合優先使用

- 長篇研究敘事與策略報告
- 一般會議紀錄或知識庫首頁
- 幾乎沒有程式碼、參數或操作步驟的 PRD

---

## 2. Design Tokens

使用中性背景與藍紫系 accent，程式碼區有明顯但不刺眼的深色面板。色彩用於操作狀態與語法層級，不做品牌複製。

```css
:root {
  --bg: #f7f9fc;
  --surface: #ffffff;
  --surface-subtle: #f2f5fa;
  --text: #1f2937;
  --text-strong: #111827;
  --text-muted: #64748b;
  --border: #dbe3ee;
  --border-strong: #cbd5e1;
  --accent: #4f46e5;
  --accent-hover: #4338ca;
  --accent-soft: #eef2ff;
  --info: #2563eb;
  --success: #15803d;
  --warning: #a16207;
  --danger: #b91c1c;

  --code-bg: #111827;
  --code-surface: #172033;
  --code-text: #e5e7eb;
  --code-muted: #94a3b8;

  --radius-sm: 6px;
  --radius-md: 9px;
  --radius-lg: 12px;
  --shadow-panel: 0 14px 40px rgb(15 23 42 / 0.08);

  --font-sans: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  --reading-width: 660px;
}
```

Dark：貼 [theme-toggle.md](theme-toggle.md) 的 `:root[data-theme="dark"]`。

### Typography

| 元件 | 建議 |
|---|---|
| H1 | 2.4–3.5rem；字重 700；不要像行銷 Hero 過大 |
| H2 | 1.55–1.9rem；明顯 section boundary |
| H3 | 1.1–1.3rem；常與 endpoint、step 或 concept 對應 |
| Body | 16–17px；line-height 1.65–1.75 |
| Parameter / code | 13–14px monospace |
| Metadata | 12–13px；muted |

---

## 3. Page Layout

### Reference / Guide 模式

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Product / Docs / Search / Version                                   │
├───────────────┬────────────────────────────┬────────────────────────┤
│ Left nav      │ Explanation / parameters   │ Code / request example │
│ 230–260px     │ 520–680px                  │ 38–44vw                 │
└───────────────┴────────────────────────────┴────────────────────────┘
```

- 左側是產品、版本與章節導覽。
- 中間是概念、步驟、參數與注意事項。
- 右側是 sticky code panel、request builder 或 response example。
- 每一節說明與右側 code example 必須能明確對應。

### 手機

- 左側導覽收合為頂部選單。
- 右側 code panel 移到對應說明下方，不得整頁固定。
- Language tabs 可水平捲動。
- Parameter table 在窄螢幕改成 stacked definition list，或允許水平捲動。

---

## 4. 元件規格

### 4.1 Developer Hero

結構：

```html
<header class="developer-hero">
  <div class="breadcrumb">Docs / Payments / Quickstart</div>
  <h1>Accept your first payment</h1>
  <p class="lede">完成後讀者可以做到什麼，以及需要哪些前置條件。</p>
  <div class="hero-actions">Get started · View API reference</div>
</header>
```

- Hero 應功能導向，不使用大背景圖。
- 可顯示版本、穩定性、預估完成時間與 prerequisite。
- CTA 最多兩個，以 anchor navigation 為主，不做行銷按鈕群。

### 4.2 Step Section

每個步驟使用穩定格式：

```text
Step number
Action-oriented title
Outcome sentence
Explanation
Code / command
Expected result
Troubleshooting note
```

- Step number 以圓形或小型 label 顯示。
- 一個 step 只完成一個可驗證成果。
- Expected result 必須清楚，讓使用者知道自己做對了。
- Error handling 放在該步驟附近，不集中到文件最末端。

### 4.3 Endpoint Header

```html
<section class="endpoint">
  <header class="endpoint-header">
    <span class="method method-post">POST</span>
    <code>/v1/resources</code>
    <span class="auth-badge">Secret key</span>
  </header>
</section>
```

規則：

- HTTP method 使用小型色彩 badge，但文字仍是主要辨識方式。
- Path 使用 monospace，可一鍵複製。
- 同一區塊顯示 authentication、idempotency、rate limit 或版本資訊。
- Endpoint 說明先回答「用來做什麼」，再列參數。

### 4.4 Parameter Table

建議欄位：

```text
Name | Type | Required | Description | Constraints | Example
```

- `required` 不只靠紅色星號；用文字 badge。
- Nested object 可摺疊，但第一層結構預設展開。
- Enum 值使用 inline code chips。
- Deprecated 參數需顯示替代方案與日期。
- 參數說明保持可操作，避免只有同義反覆。

### 4.5 Code Panel

```html
<aside class="code-panel">
  <div class="code-toolbar">
    <div class="language-tabs">curl · Node · Python · Go</div>
    <button>Copy</button>
  </div>
  <pre><code>...</code></pre>
  <div class="code-result">Expected response</div>
</aside>
```

規則：

- 使用深色背景、清楚 toolbar、語言 tabs 與 copy feedback。
- 程式碼必須可直接使用；placeholder 要清楚標示。
- Secret、token、個資不得放入範例。
- 重要行可 highlight，但不得造成其他文字難以閱讀。
- 若同一範例包含 request 與 response，使用明確標籤分區。

### 4.6 Language Tabs

- Tabs 使用 ARIA tab pattern 或簡化為可鍵盤操作的按鈕群。
- 預設語言可由文件設定；不要根據不可靠的 browser guess 自動改變。
- 所有語言內容應語意等價；若某 SDK 不支援某功能，明確標示。
- 列印時顯示預設語言，並在附錄提供其他語言或連結。

### 4.7 Request / Response Pair

- Request 與 response 可上下或左右排列。
- 顯示 status code、headers、body 與 latency 僅限來源有提供。
- Error response 必須附上原因、修正方式與 retry 建議。
- JSON 中敏感值使用明確 placeholder，例如 `sk_test_...`、`USER_ID`。

### 4.8 Callout

| 類型 | 用途 |
|---|---|
| Note | 背景知識、版本差異 |
| Tip | 更快或更安全的做法 |
| Important | 不做會失敗的必要條件 |
| Warning | 破壞性操作、金流、資料遺失、production 風險 |
| Deprecated | 舊版 API 與 migration path |

- Callout 緊鄰相關步驟或參數。
- Warning 不得被摺疊。
- Production / test mode 差異應使用明確 label。

### 4.9 Authentication Block

包含：

- 所需 credential 類型。
- 放置位置，例如 header、query 或 environment variable。
- 最小權限建議。
- Test / production 差異。
- 安全提醒；不要把 secret 寫進 client-side code。

### 4.10 Error Reference

表格欄位：

```text
Code | Meaning | Likely cause | What to do | Retryable
```

- 依常見度或流程順序排列，不只按字母排序。
- Retryable 需要文字 `Yes / No / Conditional`。
- 有 backoff 規則時直接附上公式或範例。

### 4.11 Version / Deprecated Banner

- 頁首或相關 endpoint 附近顯示版本。
- Deprecated banner 包含 sunset date、替代 endpoint、migration guide。
- 不用巨大的紅色區塊；資訊要醒目但不阻礙閱讀。

### 4.12 Search / In-page Find

- 文件規模大時可提供 client-side 搜尋。
- 搜尋索引至少包含 heading、endpoint path、parameter、error code。
- 沒有 JS 時仍有完整左側導覽與瀏覽能力。

---

## 5. Diagram Treatment

此風格的 diagrams 必須服務於「整合與除錯」，而不是抽象展示。

### 優先使用

- Sequence diagram：authentication、webhook、payment flow、callback。
- Flowchart：quickstart、error recovery、branching setup。
- State diagram：resource lifecycle。
- Compact architecture：client、API、service、webhook endpoint 的責任邊界。

### 視覺規則

- 說明側使用淺底，code 側使用深底；diagram 本身以淺底、藍紫 accent 為主。
- 節點名稱對應文件中的實際資源、endpoint 或服務。
- 每條箭頭標記 request、event、response 或 retry。
- Sequence diagram 過長時拆成「happy path」與「failure path」。

### 外觀方向

Figure 使用淺色 surface、清楚邊框與單一藍紫 accent；節點名稱對應實際資源。
Mermaid source 只寫語意，不放顏色。

---

## 6. Interaction

可使用：

- Language tabs。
- Copy code、copy endpoint、copy response。
- Sticky synchronized code panel。
- Collapsible nested parameters。
- Search、version selector、endpoint filter。
- 「Try it」模擬區只有在不送出真實敏感請求時使用。

必須：

- 深淺 toggle：見 [theme-toggle.md](theme-toggle.md)（預設必帶）。
- Copy 後提供文字 feedback。
- Tab 與 accordion 可鍵盤操作。
- 不依賴 hover 才顯示參數必要資訊。
- 所有互動錯誤要有可讀訊息。

避免：

- 自動執行 API call。
- 把 secret 寫入 localStorage。
- 為了模仿 API console 而產生無功能的假控制項。
- 讓 sticky code panel 在小螢幕遮住正文。

---

## 7. 一鍵呼叫 Prompt

```text
請將提供的內容轉成 Stripe-inspired 的 developer documentation HTML。這不是品牌官網複製，而是採用清楚的開發者工作流、說明與程式碼並排、藍紫 accent、深色 code panel 與高可查找性的資訊設計。

請特別做到：
1. 依使用者任務整理 Quickstart、Prerequisites、Authentication、Steps、Endpoints、Parameters、Examples、Errors、Webhooks、Versioning 與 Troubleshooting；只保留來源中存在的資訊。
2. 桌面版使用左側導覽、中間說明、右側 sticky code panel；手機版把程式碼移到對應步驟下方。
3. 為程式碼加入語言 tabs、檔名或用途標籤、copy button、expected result 與錯誤處理。
4. API endpoint 顯示 method、path、authentication、parameters、request、response 與 error cases；不得補造不存在的 endpoint 或欄位。
5. 使用 sequence diagram、resource lifecycle 或 integration flow 幫助理解；每張圖都必須對應實際操作。
6. 預設輸出單一 index.html，支援鍵盤操作、列印、responsive tables、reduced motion 與深淺 toggle。
7. 不使用品牌 logo、不逐像素複製網站、不加入無功能的假 API console，也不得在範例中暴露真實 secret。
```

---

## 8. 驗收標準

- [ ] 開發者能快速找到第一個可執行步驟。
- [ ] 每個步驟都有可驗證的 expected result。
- [ ] 說明、參數與程式碼在視覺上可以明確配對。
- [ ] Endpoint、parameter、error code 可掃描與搜尋。
- [ ] 多語言 tabs、copy、accordion 可鍵盤操作。
- [ ] 手機版沒有固定 code panel 遮擋。
- [ ] 範例沒有真實 credentials、個資或危險預設值。
- [ ] 不捏造 API 行為、版本、限制或 response。
