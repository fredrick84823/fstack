---
name: generate-meeting-notes
description: 把逐字稿、字幕或錄音轉成結構化繁中會議記錄，發佈到 Google Doc 與 Slack。
allowed-tools: Bash, Read, Write, Task
disable-model-invocation: true
---

# Generate Meeting Notes

## 三個詞

貫穿全流程，先讀懂再往下：

- **source artifacts** —— 一個目錄裡的三個檔：`transcript.md`（本次會議的事實）、
  `extract.md`（議題／決策／行動／風險索引）、`meeting-context.md`（會議類型、與會者、
  custom prompt、active glossary terms、來源與日期）。所有 source 流程的產物都是這個，
  **不是正式稿**。目錄位置：`/tmp/meeting_sources/<meeting_key>_<YYYYMMDD>[_<meeting_instance>]`。
- **接地** —— 正式稿的每個事實都指得回 `transcript.md`。`extract.md`、`meeting-context.md`、
  glossary、歷史會議記錄只提升可讀性與連續性，不能長出 transcript 沒講過的決策、
  待辦、數字或時間。無法接地的寫 `[待確認]`。衝突時 `transcript.md` 勝。
- **交棒契約** —— 每段流程結束把 `RESULT_*` 印到 stdout，下一段**只吃這些值**，不重新推導路徑：

  ```
  RESULT_SOURCE_DIR  RESULT_TRANSCRIPT  RESULT_EXTRACT  RESULT_CONTEXT  RESULT_DATE
  ```

## Skill 目錄解析

所有腳本執行前先解析安裝後的 skill 目錄，不要 hardcode `~/.claude`、`~/.codex` 或 `~/.gemini`：

```bash
SKILL_DIR="${CLAUDE_SKILL_DIR:-}"
if [ -z "$SKILL_DIR" ]; then
  SKILL_DIR="$(find \
    "$PWD/.agents/skills" "$PWD/.claude/skills" "$PWD/.codex/skills" "$PWD/.gemini/skills" \
    "$HOME/.agents/skills" "$HOME/.claude/skills" "$HOME/.codex/skills" "$HOME/.gemini/skills" \
    -path '*/generate-meeting-notes/SKILL.md' -print -quit 2>/dev/null | xargs dirname)"
fi
test -n "$SKILL_DIR" || { echo "generate-meeting-notes skill directory not found"; exit 1; }
```

## 版本來源檢查

這個 skill 可能同時存在於安裝目錄與 repo 目錄，兩份是**獨立檔案**（不同 inode）。
啟動前先確認當前 repo 內有沒有 `generate-meeting-notes/SKILL.md`：

- 有 → 以 repo 版本為準，除非使用者明確要求用安裝版
- 只有安裝版 → 用上面解析出的 `SKILL_DIR`
- 兩份在流程上不一致 → **停下來**列出差異，由使用者決定跟哪一份

## 流程選擇

| 流程 | 觸發條件 | 產出 |
|------|---------|------|
| **A · Text Source Preparation** | 有任何可讀文字（逐字稿／字幕／文字紀錄） | source artifacts |
| B · Audio Source Extraction | 只有音訊，或文字品質不足需補充 | source artifacts |
| C · Main Synthesis | 已有 source artifacts | 正式稿 → Google Doc + Slack |
| D · 雙來源合併 | 同時有文字與音訊 | 文字為主，音訊補缺漏 |

**有可讀文字就走 A，不要因為來源工具不熟就跳去 B。** A 與 B 都必須先產出 source
artifacts 再進 C，不可直接出正式稿。

輸入類型與路由：

| 類型 | 副檔名 | 處理 |
|------|--------|------|
| 逐字稿／文字紀錄 | `.txt` `.text` `.md` `.markdown` `.csv` | A |
| 字幕 | `.srt` `.vtt` | A（時間戳可留著定位，正式稿不必逐字輸出） |
| 文件型逐字稿 | `.docx` `.pdf` Google Doc | 先讀取／匯出成文字或 Markdown，再走 A |
| 音訊 | `.m4a` `.mp3` `.wav` `.aac` `.flac` `.ogg` `.opus` | B（需 `ffmpeg`） |
| 含音軌媒體 | `.mp4` `.mov` `.mkv` `.webm` | 先抽音軌轉成音訊檔，再走 B |

## 前提

1. `uv`（`brew install uv`；首次設定會嘗試自動安裝）
2. 已完成首次設定與 Google 認證 → `references/setup.md`
3. 流程 B 另需 `ffmpeg` 與 NotebookLM 認證
4. 流程 A 需要 runtime 支援 spawn subagent／Task；不支援時 main agent 可代行，
   但仍必須先產出 source artifacts

**同一天、同一個 `meeting_key` 有多個檔案或多場次時**，先讀
`references/multi-session.md` 決定 `meeting_instance`，再往下走。不要用預設目錄覆蓋既有
source artifacts。

## 流程 A：Text Source Preparation

### Step 1：確認來源與會議類型

詢問：
> 逐字稿、字幕檔或文字紀錄路徑是什麼？（例：`~/Downloads/2026-05-14 11_03_01-transcript.txt`）
> 這是哪種會議？

日期優先由使用者提供，其次從檔名推斷（`YYYYMMDD` 或 `YYYY-MM-DD`）。
**推不出來就問，不要用今天日期猜。**

### Step 2：建立 source artifact 目錄

```bash
mkdir -p /tmp/meeting_sources/<meeting_key>_<YYYYMMDD>[_<meeting_instance>]
```

### Step 3：spawn subagent 產出 transcript.md 與 extract.md

透過 local coding agent 的 subagent／Task 能力啟動一個 source-preparation subagent。
它只產這兩個檔，不做正式稿、不建 Google Doc、不發 Slack。

`transcript.md`：
- 保留原始事實內容、Speaker 標籤、時間戳與語意順序
- 可做輕量格式整理（統一 heading、移除平台雜訊、整理明顯斷行）
- 不改寫會議事實；不確定的保留原文或標 `[待確認]`

`extract.md`：
- 只從 `transcript.md` 產議題、決策、行動項目、風險、open questions、待確認索引
- 每項保留可追溯線索（Speaker 標籤、時間戳或原文短語）—— 這就是**接地**
- NotebookLM 產的 `extract.md` 要先驗內容：若回覆是「我已生成索引」這類 meta 文字，
  或不含至少兩類核心欄位，`extract_audio_sources.py` 會自動重試一次更嚴格的提問；
  重試仍失敗就報錯，不寫入壞的 extract

### Step 4：main agent 產出 meeting-context.md

讀 `~/.config/generate-meeting-notes/config.json` 的 `custom_prompt`、`attendees`
與 glossary，產出 `meeting-context.md`。只放脈絡，不放 transcript 沒支持的本次會議事實。

完成後印出**交棒契約**的五行，進流程 C。

## 流程 B：Audio Source Extraction

**四個問題全部確認完才執行腳本。**

### Step 1：音訊檔路徑

沒提供就問：
> 請提供音訊檔路徑（例：`~/Desktop/data_meeting_20260311.m4a`）

檔名**必須含連續 8 位數字**當日期（`data_meeting_20260309.m4a` → `20260309`）。

### Step 2：會議類型

```bash
cat ~/.config/generate-meeting-notes/config.json
```

列出 `meetings` 的所有 key 讓使用者選。

### Step 3：Slack channel

- 該會議類型有 `slack_channel` → 告知「完成後自動通知 channel `{id}`，要改請說」
- 為空 → 提醒「此類型未設 channel，不會自動通知；要設請重跑 `setup.py`」

### Step 4：NotebookLM 認證

**切音訊前先驗**，別讓 40+ 段切完才報錯：

```bash
cd "$SKILL_DIR" && uv run notebooklm auth check --test
```

失敗就 `uv run notebooklm login`，通過後才往下。（舊的 `whoami` preflight 已停用。）

### Step 5：執行 source extraction

```bash
cd "$SKILL_DIR" && uv run scripts/extract_audio_sources.py <audio_file> \
  --meeting <meeting_key> --delete-segments --segment-count 20
```

- `--delete-segments`：完成後自動清暫存片段，不必再問使用者
- `--segment-count N` 或 `--segment-minutes N`：調切分方式
- 多場次時必須加 `--output-dir /tmp/meeting_sources/<key>_<date>_<instance>`

腳本自動把該 `meeting_key` 相關且 `status=active` 的 glossary entries 寫進
`meeting-context.md`，用途只有人名／專案名正規化、縮寫展開與錯字修正
（例 `NCP` → `MCP`）、口語別名對齊 canonical name。glossary 不是會議事實來源。

從 stdout 解析**交棒契約**（另有 `RESULT_SERIES_NAME`），進流程 C。
不要拿 NotebookLM 內容直接當正式稿。

## 流程 C：Main Synthesis

A 與 B 都收在這裡。main agent 讀：

| 來源 | 用途 |
|---|---|
| `RESULT_TRANSCRIPT` | 主事實來源 |
| `RESULT_EXTRACT` | 議題／決策／行動／風險 checklist |
| `RESULT_CONTEXT` | 人名、專案名、縮寫、會議類型脈絡 |
| `references/default-prompt.md` 或 config 指定的 prompt | 格式 |
| 同類型歷史會議記錄 | 連續性：前次決策的延續、未完成待辦、術語演進、已知命名 |

證據優先序：`transcript.md` > `extract.md` > `meeting-context.md` > 歷史會議記錄。
歷史記錄與 glossary 都受**接地**約束。

輸出規則：
- 完整繁體中文 Markdown
- Speaker 標籤維持原格式（`Speaker 1`、`SPEAKER_00`、人名、平台標籤）。
  除非使用者給明確對照，不自行替換姓名
- 正式稿只放會議內容。NotebookLM、`extract.md`、source artifact 路徑、腳本步驟、
  驗證狀態、pipeline／debug 備註、agent 操作說明一律只出現在 agent 回報裡

### Step 1：儲存 Markdown + 發佈

先把 Markdown 寫到暫存檔（例 `/tmp/meeting_notes_team週會_20260514.md`），然後：

```bash
cd "$SKILL_DIR" && uv run scripts/create_gdoc_from_md.py \
  --meeting <meeting_key> \
  --date <YYYYMMDD> \
  --content-file /tmp/meeting_notes_<key>_<date>.md \
  --source-dir <RESULT_SOURCE_DIR> \
  --audio-file <原始音訊檔路徑> \
  --delete-local-audio
```

| 參數 | 何時加 |
|---|---|
| `--audio-file` `--delete-local-audio` | **輸入是音訊時一律加**。純文字來源省略 |
| `--title-suffix <meeting_instance>` | 同日同類型要分開多份 Doc 時，讓 Doc 名可區分 |

腳本輸出：

```
RESULT_URL: https://docs.google.com/document/d/<doc_id>/edit
RESULT_DRIVE_PATH: <folder_name>/<YYYYMMDD>
RESULT_SERIES_NAME / RESULT_DATE
RESULT_AUDIO_FILE: <drive_file_id>     # 只在有 --audio-file 時
RESULT_LOCAL_AUDIO: deleted | kept     # kept 要告知使用者原因
```

Doc 名稱 `會議記錄_{series_name}_{YYYYMMDD}`，多場次加 `_{meeting_instance}`。
Doc、source artifacts 與原始音訊都落在 `{Shared Drive}/{系列資料夾}/{YYYYMMDD}/`。

### 原始音訊歸檔

錄音檔動輒上百 MB，堆在 `~/Downloads` 沒有意義。刪本機檔的三個條件，**全部成立才刪**：

1. 指定了 `--delete-local-audio`
2. 上傳後另外向 Drive 查一次該檔實際位元數
3. 該位元數與本機 `stat().st_size` 完全相同

任一項不成立就印原因、保留本機檔、回報 `RESULT_LOCAL_AUDIO: kept`。
同名同大小的檔已在該資料夾 → 跳過上傳沿用既有 file_id，不產生重複。

**Agent 不要自己 `rm` 音訊檔。** 交給腳本才有「上傳已驗證」這道保險。

## 發佈後

### 解析匿名發言者（Doc 裡還有 `[Speaker N]` 時）

沒有佔位符就跳過整節。

1. 讀 config 取該會議類型的 `attendees`、`custom_prompt`、glossary 人名 alias
2. **請使用者開啟 `RESULT_URL` 並把 Doc 前 30 行貼回對話**（agent 開不了 URL）
3. 依報告順序 + attendees + alias 推斷對應，**向使用者確認**
4. 確認後批次替換：

```bash
cd "$SKILL_DIR" && uv run scripts/replace_speakers.py \
  --doc-id <RESULT_URL 裡的 doc id> \
  --mapping "Speaker 1=Alice" "Speaker 2=Bob"
```

### Slack 通知

`create_gdoc_from_md.py` 結束時自動呼叫 `send_slack_notification.py`，**agent 不介入**。
只在腳本印警告時處理：

- `未設定 slack_channel` → 重跑 `setup.py` 填 Channel ID
- `Slack 通知失敗` → 確認 Bot Token 正確且 Bot 已加入該 channel

## 流程 D：雙來源合併

文字為主軸，音訊補細節。人工整理或專用轉錄工具的逐字稿通常比 NotebookLM
音訊辨識穩定，所以措辭優先保留文字版。

1. 先跑 **A + C** 產出主要會議記錄，記下 `RESULT_URL`
2. 判斷是否需要音訊補充：
   - 逐字稿完整 → **結束**，A + C 的 Doc 就是最終版
   - 逐字稿有缺漏（某段無法辨識）→ 繼續
3. 跑 **B** 對音訊產 source artifacts
4. 合併：以文字 artifacts 與 C 初稿為主，只補入逐字稿缺漏而音訊**接地**支持的段落。
   **更新**（不是新建）同一份 Google Doc
5. Slack：補入顯著新內容 → 補發一則到同 channel，說明已補充音訊分析並附 URL；
   只是細節修正（例如人名）→ 不必補發

## 延伸參考

| 需要時 | 讀 |
|---|---|
| 首次設定、`config.json` 結構、Google 認證檔案的角色 | `references/setup.md` |
| glossary 格式、共用 glossary 的合併與降級 | `references/glossary.md` |
| 同日同類型多檔／多場次、`meeting_instance` 命名 | `references/multi-session.md` |
| 403 / `This app is blocked` / scope 診斷 / NotebookLM 重跑 | `references/troubleshooting.md` |
| 預設 prompt 內容 | `references/default-prompt.md` |
