---
name: viz-it
description: Turn any content into a visual-first single-page HTML where every diagram is a pan/zoom canvas.
argument-hint: "<content / file / topic> [style: vercel|notion|stripe] [theme: light|dark]"
disable-model-invocation: true
---

# Viz It

輸入可以是任何東西：文件、對話、逐字稿、程式碼、一堆散亂筆記。輸出是一份單檔 HTML，**圖是主體、文字是註解**。需要 pan/zoom 的圖用 [beautiful-mermaid](../beautiful-mermaid/SKILL.md) 在建置時渲染成 inline SVG，包在可縮放、可拖拉的 canvas 裡。

與 [doc-to-html](../doc-to-html/SKILL.md) 的差別只有兩點，其餘（風格、語意化、輸出契約）全部沿用它：

| | doc-to-html | viz-it |
|---|---|---|
| 主體 | 文章，圖是輔助 | 圖是 spine，文字是 caption 與 annotation |
| Mermaid | CDN 執行期渲染 + 文字 fallback | 建置期渲染成 inline SVG，pan/zoom canvas，無 CDN、無 fallback 需求 |

## 1. 定 spine

先列出這份內容的 **spine**：一串有序的視覺單元，每個回答一個問題，串起來就是完整論述。

一行一個：`問題 → 形式 → 需要的節點／行`。挑能講清楚的**最小形式**，不是最花的：

| 要說的事 | 形式 |
|---|---|
| 流程、狀態機、時序、資料模型、架構 | Mermaid canvas |
| 判斷邏輯或演算法 | pseudocode 區塊 |
| 執行期呼叫路徑 | call tree |
| 檔案責任分工 | 淺層 file tree |
| UI 結構與 state 邊界 | component tree（含檔案路徑） |
| 「改了什麼」 | `diff`，形狀對齊主題（component / file tree / call tree / state） |
| 太密、Mermaid 畫不動的資訊圖 | inline SVG 或 CSS |

非 Mermaid 的形式在頁面上就是等寬字區塊，不進 canvas、零 runtime 成本，spine 可以混用。標籤一律用真實的檔名、函式名、欄位名與數據，不用 Foo／Bar。

完成條件：內容裡每個主要主張都掛在 spine 的某個單元上，或明確標記為「只能用文字」（數字、引用、限制條件）。spine 裡若沒有任何一個需要 pan/zoom 的圖，改用 doc-to-html。

## 2. 寫 .mmd

放在 HTML 旁的 `diagrams/`，一張圖一個檔。遵守 [beautiful-mermaid](../beautiful-mermaid/SKILL.md) 的 authoring rules：6–10 節點、短標籤、細節放 edge label、單色為主、header 必須是第一行、檔案內不寫顏色。

C4 架構圖的分層規則沿用 [doc-to-html](../doc-to-html/SKILL.md#c4-架構圖)。

完成條件：每個 .mmd 單獨渲染成功（`node ../beautiful-mermaid/scripts/render_mermaid.js -i x.mmd -f ascii`）。

## 3. 寫頁面骨架

版面、風格檔、語意化 HTML、MUST / MUST NOT 全部照 [doc-to-html](../doc-to-html/SKILL.md) 執行。差別是圖的位置改成佔位 figure，內容留空：

```html
<figure class="viz" data-mmd="diagrams/ingest.mmd" data-h="460" data-alt="ingest pipeline">
  <figcaption>圖 1 — 從原始事件到報表的四個階段</figcaption>
</figure>
```

| 屬性 | 作用 |
|---|---|
| `data-mmd` | 必填，相對 HTML 檔的 .mmd 路徑 |
| `data-h` | canvas 高度 px，預設 420；sequence 或高瘦的圖給 520–640 |
| `data-alt` | SVG 的 `aria-label` |
| `data-preset` | 單張圖覆寫 preset（`craft` / `craft-dark`） |

每張圖後面接一句「這張圖說明什麼」的 caption 與必要的圖後洞察——圖只承載結構，數字與結論仍要寫成文字。

## 4. Inline

```bash
node ~/.agents/skills/viz-it/scripts/inline_diagrams.mjs <file.html> [--preset=craft-dark]
```

渲染每個 figure、把 SVG 塞進 `.viz-stage > .viz-canvas`、注入一次 viewer runtime（CSS + JS，`id="viz-runtime"`）。可重複執行：改完 .mmd 直接再跑一次會覆蓋舊 SVG。

完成條件：輸出的 `N diagram(s) inlined` 等於 figure 數，且沒有 `!` 開頭的錯誤行。

## 5. 驗收

```bash
agent-browser open "file:///abs/path/file.html"
agent-browser eval "JSON.stringify({figs:document.querySelectorAll('figure.viz').length, mounted:[...document.querySelectorAll('figure.viz')].filter(f=>f.__viz).length, overflow:document.documentElement.scrollWidth>document.documentElement.clientWidth})"
agent-browser console
agent-browser set viewport 390 844
agent-browser screenshot /tmp/check.png
```

完成條件：`mounted === figs`、console 無錯誤、桌機與 390px 都無水平溢出、截圖上每張圖初始狀態完整可讀（fit 後不需捲動就看得到全貌）。

通過後 `open <file.html>`，回覆只留一行路徑與 spine 的一句話摘要。

## Canvas 行為

runtime 已內建，不要自己再寫一套 pan/zoom：

| 操作 | 行為 |
|---|---|
| 拖曳 | pan |
| ⌘/ctrl + 滾輪、觸控板 pinch | 以游標為錨點縮放 0.1x–8x（單純滾輪保留給頁面捲動） |
| 雙擊 | fit |
| HUD | `−` / 百分比 / `+` / `Fit` / `1:1` / 全螢幕 |
| focus 後鍵盤 | `+` `-` `0` `f` |
| 容器右下角 | 可垂直拉伸改變 canvas 高度 |

縮放是 bake 進 SVG 的實際尺寸（非只有 CSS transform），所以放大後文字仍銳利。列印時 canvas 自動攤平成完整圖。

`figure.__viz`（`state()` / `fit()` / `reset()` / `zoomAt()`）供驗收腳本呼叫。

## 輸出

檔名與單檔內嵌規則同 doc-to-html：`xxxx-xx-xx_page-name.html`。`diagrams/*.mmd` 留在旁邊當可再生的原始碼，不影響 HTML 自足性。文件放置位置依你 repo 或 notes 系統自己的慣例（若有 `CLAUDE.md` / `AGENTS.md` 規定輸出目錄，以那個為準）。
