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
- **排序**：`morning`／`am`／`noon`／`afternoon`／`pm`／`evening` 這幾個排得出一天之中
  的先後，歷史索引照它們排（`local_archive.INSTANCE_ORDER`）。表外的短名稱
  （`project-x`）排在同日已知場次**之後**，並在 `history_index` 印一行說是哪幾份 ——
  排序有退化但不會靜靜地照字母序（`afternoon` < `am` 那種）

## 目錄

```bash
/tmp/meeting_sources/<meeting_key>_<YYYYMMDD>_<meeting_instance>   # source artifacts
{Shared Drive}/<系列資料夾>/<YYYYMMDD>_<meeting_instance>/          # Doc、音訊、artifacts
{local_archive_root}/<系列資料夾>/<YYYYMMDD>/會議記錄_…_<meeting_instance>.md
```

只有確定當天該 `meeting_key` 只有一場會議時，才可省略 `_<meeting_instance>`。

**Drive 的日期資料夾帶場次後綴，本機歸檔的不帶** —— 本機一律是 8 位數的日期資料夾，
場次在檔名裡。Drive 那邊是掃描層認人的地方（`reconcile_drive.py` 靠資料夾名認出這是
哪一場，同一個資料夾兩個音檔就停手），本機那邊是歷史索引按日期走訪的地方。

同事把錄音丟進 Drive 時也照這個形狀：一天兩場就 `20260916_am` 與 `20260916_pm`，
各放各的錄音，reconcile 會各產一份。丟成一個資料夾兩個音檔、或丟進一個名字認不得的
資料夾，都會收到帶下一步的提醒。

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
