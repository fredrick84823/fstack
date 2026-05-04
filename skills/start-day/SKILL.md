---
name: start-day
description: |
  每日早晨任務看板：整合 gsheet / GitHub / Heptabase Sprint whiteboard + week tag
  三處任務狀態，自動建卡、合併狀態、寫入 Heptabase 當日 journal。
  觸發詞：「start-day」「每日任務看板」「今日任務」「我要開始工作」
  「daily task board」「整理今日任務」。
allowed-tools:
  - Bash
  - Bash(heptabase *)
  - Bash(gh *)
  - Bash(uv run *)
  - Bash(python *)
  - mcp__heptabase__get_whiteboard_with_objects
model: claude-sonnet-4.6
---

## 任務

幫使用者跑每日任務看板。

### Step 1: Pre-flight
確認在 fstack repo 根目錄，確認 Heptabase desktop 在跑：
```bash
heptabase --version
```
若失敗，請使用者執行 `heptabase start` 後再試。

### Step 2: 讀取 Sprint whiteboard（MCP）

計算當週週號：
```bash
TZ=Asia/Taipei date +%G-W%V
```

使用 `mcp__heptabase__get_whiteboard_with_objects` 讀取 Sprint whiteboard（whiteboard ID: `79f11368-17a3-4263-8cb3-2028c0b4b005`）。

從回傳結果中找到 `section title == 當週週號`（例如 `2026-W18`）的 section，取出其 `objectIds`。

- 若找不到該 section → print `⚠️ Sprint whiteboard 尚無 {week_id} section，略過` 並繼續（不 abort）
- 若找到 → 從 whiteboard cards 中找出這些 objectIds 對應的 card title

將 sprint whiteboard 的卡片轉為 normalized task schema，寫入 `/tmp/sprint_cards.json`：
```json
[
  {
    "name": "<normalized title>",
    "name_raw": "<original card title>",
    "status": "unknown",
    "sources": [{"kind": "heptabase", "id": "<card_id>", "url": null, "status_raw": "sprint_board", "last_updated": ""}],
    "conflict": null,
    "depends_on": [],
    "card_id": "<card_id>",
    "multi_match_warning": null,
    "progress_note": "<從卡片內容 ## Progress / ## Goal section 抽取，無則留空>"
  }
]
```

### Step 3: 跑 orchestrator

```bash
TZ=Asia/Taipei uv run python skills/start-day/scripts/start_day.py --sprint-json /tmp/sprint_cards.json
```

加 `--dry-run` 可預覽 markdown 不寫 journal。

### Step 4: 回報

從 stdout 解析 summary，回 chat：
- 今日 N 個任務（進行中 X / 已完成 Y）
- 新建 Z 張卡片
- W 個衝突（需使用者確認）
- 提醒：衝突任務清單

### 守則
- 任一 fetcher fail → orchestrator 自動 abort，不出部分看板
- 不在使用者確認前修改 gsheet 或 GitHub
- 衝突一律以 PR 為準，但在 Heptabase 卡片中留記錄
- Sprint whiteboard section 不存在 → warning，不 abort
