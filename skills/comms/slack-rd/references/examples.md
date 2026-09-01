# 改寫對照

## 母訊息 —— 改前 16 行，改後 6 行

改前有 `1️⃣2️⃣3️⃣` 編號、TL;DR 第二項附三行 why、一句「*要你做的只有第 2 點。*」、以及一整段 `*為什麼要談 prod/staging 分離*`（三段解釋 + 兩個方案）。

改後：

```
📢 RD sync — CI 開始跑測試了 + 部署現況盤點完成

*TL;DR*
> • PR 開到 main 會自動跑 pytest（只跑你改到的那台，約 1 分鐘）
> • ⚠️ 動過 `pyproject.toml` 一定要 `uv lock`，不然 CI 會紅
> • 部署現況盤點完成，三個 GCP project / 22 個 service → ADR 0002
細節都在 PR：CI ｜ #137 → #149 ・部署 ｜ #150

prod/staging 分離之後某次 RD 會議討論，日期未定。ADR 裡有三件不必等會議的事，其中 staging 環境的 ingress 設定優先度最高。
```

被刪掉的整段 why，論述版活在 thread 裡。

改動對應：

- `1️⃣2️⃣3️⃣` → `•`
- TL;DR 第二項的三行 why → 搬進 thread
- 「要你做的只有第 2 點」→ 刪（閱讀指令）
- `*為什麼要談 prod/staging 分離*` 整段 → 搬進 thread
- 保留最後一段落地資訊：時間、地點、誰先動

## thread —— 行數幾乎沒變，改的是結構

- PR 清單從內嵌一行抽成 code block
- `*這正好帶出要討論的東西*` 當小標題
- 最關鍵的一句進 blockquote
- 因果鏈的句號改逗號，串成長句
