# 同日同類型多檔／多場次

**不要只用「同一天 + 同會議類型」判斷要不要合併。** 同一天、同一個 `meeting_key`
有多個音訊檔、逐字稿或文字來源時，先判斷是同一場會議的多段來源，還是不同場會議。

| 情況 | 例 | 做法 |
|---|---|---|
| 同一場的多段來源 | 錄音分段、補錄、同場的逐字稿 + 音訊 | 合併成一份 Google Doc，共用同一個 `meeting_instance` 與同一個 source artifact 目錄。逐字稿 + 音訊走流程 D |
| 不同場會議 | 上午／下午兩場同類型、不同專案但 meeting key 相同 | 分開成多份 Doc，每場一個不同的 `meeting_instance`，**不可共用** source artifact 目錄 |
| 判斷不出來 | —— | 問使用者「這些檔案是同一場會議的多段，還是要分成多份 Doc？」 |

## `meeting_instance` 命名

- 優先用使用者提供的短名稱：`am`、`pm`、`project-x`、`part1-combined`
- 沒提供 → 從檔名的時間或主題推斷短 slug；仍不明確就問
- 只用小寫英數、中文、底線或短橫線。避免空白與路徑特殊字元

## 目錄

```bash
/tmp/meeting_sources/<meeting_key>_<YYYYMMDD>_<meeting_instance>
```

只有確定當天該 `meeting_key` 只有一場會議時，才可省略 `_<meeting_instance>`。

**目標目錄已存在且不屬於本次這場會議 → 換一個 `meeting_instance` 或問使用者。**
不要覆寫既有的 source artifacts。

發佈時對應加 `create_gdoc_from_md.py --title-suffix <meeting_instance>`，
流程 B 對應加 `extract_audio_sources.py --output-dir <上面那個目錄>`。

## 日期來源

| 腳本 | 規則 |
|---|---|
| `extract_audio_sources.py` | 音訊檔名**必須**含連續 8 位數字（`YYYYMMDD`） |
| `create_gdoc_from_md.py` | `--date` 可手動指定；省略時從 `--content-file` 檔名推斷 `YYYYMMDD` 或 `YYYY-MM-DD` |

`data_meeting_20260309.m4a` → `20260309`、`2026-05-14 11_03_01-transcript.txt` → `20260514`。
