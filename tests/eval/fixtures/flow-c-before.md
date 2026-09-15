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

