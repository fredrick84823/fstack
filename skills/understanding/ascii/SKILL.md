---
name: ascii
description: 畫對齊的終端圖 —— 先定 grid 再落字，最後用 CJK 寬度稽核判紅綠。
disable-model-invocation: true
---

Monospace 圖歪掉，通常不是字元挑錯，是**先落了字才想欄位**。這裡把順序反過來：grid 先定死，字元後填，稽核判紅綠。

中文是主因。`中` 在等寬字型佔 **2 欄**，`len()` 卻回 1。靠數字元對齊的圖必歪，而且看不出來 —— 腦中的字元格線與終端的顯示格線不是同一套。

## 1. Grid

落任何字元前先算欄位：

- 每欄寬度 = 該欄最長內容的**顯示寬度**。CJK、全形標點、`（）「」→` 算 2 欄
- 整張圖 ≤ 80 欄，終端才不折行

完成條件：講得出每條垂直線在第幾欄。

## 2. Draw

盤面定了才落字。`┌ ─ │ ├ ┼ ┐ ┘ └ ┤ ┬ ┴` 與 ASCII `+ - | > < ^ v / \` 兩套都可以，一張圖只用一套。

挑圖型：flow / hierarchy / comparison / state / sequence 看 [`references/shapes.md`](references/shapes.md)；memory layout、網路拓樸、資料結構、時間軸看 [`references/engineering.md`](references/engineering.md)。挑最小的那種 —— 三個節點的流程不需要泳道。

**比較類不要畫框。** TUI 的 markdown 表格 CJK 欄寬算得正確，畫 ASCII 表是白做工。框留給表格表達不了的：流程、階層、拓樸、時間軸。TUI 還有哪些語法會被吃掉（`- [x]`、`---`、`&amp;`、標題階層），以及 emoji 為什麼別放進框線，看 [`references/tui-render.md`](references/tui-render.md)。

## 3. Verify

heredoc 直接餵，不必先落檔：

```bash
python3 scripts/verify.py - <<'EOF'
<你剛畫好的圖>
EOF
```

要反覆改同一張大圖時才落檔（改一行比重打整段便宜），這時吃檔名：`verify.py <file>...`

回報長這樣，座標可以直接動手：

```
CLAUDE.md:19: 右框線該在第 59 欄，第 21, 22 行落在第 60 欄（往右移 1 欄）
```

照著改，重跑到綠。

完成條件：exit 0。
