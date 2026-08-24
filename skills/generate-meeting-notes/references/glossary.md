# Glossary

只用於 naming、縮寫展開、人名／專案辨識與明顯口誤修正。**受「接地」約束 ——
不是會議事實來源。** 腳本只讀 `status=active` 的 `global_terms`
與符合當次 `meeting_key` 的 `meeting_terms`。

## 格式

`glossary_path` 是可選檔案。`setup.py` 會把路徑寫進 config，檔案不存在時建立空範本
（`{"global_terms": [], "meeting_terms": {}}`），並詢問是否立刻新增 terms。

```json
{
  "global_terms": [
    {
      "id": "mcp",
      "canonical": "MCP",
      "aliases": ["NCP", "Model Context Protocol"],
      "type": "technical_term",
      "status": "active",
      "render_hint": "保留大寫 MCP",
      "disambiguation": "只作為術語修正，不補充會議事實"
    }
  ],
  "meeting_terms": {
    "team週會": [
      { "id": "project-x", "canonical": "Project X", "aliases": ["PX"],
        "type": "project", "status": "active" }
    ]
  }
}
```

新增條目時**不要複製通用防護語到每筆 `disambiguation`** ——
那段話 `build_glossary_prompt()` 的 header 已經講過一次。
100 筆 glossary 約佔 `meeting-context.md` 6,000 tokens，複製防護語會膨脹到 9,000。

## 共用 glossary

同事各自維護本機檔的話，詞彙經驗無法累加。共用檔放 **Google Drive**
（`20_會議紀錄/glossary.shared.json`），每次產會議記錄時與本機合併。

```json
"shared_glossary": {
  "file_id": "<Drive 檔案 ID>",
  "cache_ttl_hours": 24
}
```

**為什麼是 Drive 而不是 GCS**：現有 OAuth token 已涵蓋 `drive` scope，零新增 scope、
零重新授權。放 GCS 要加 `devstorage.read_only` 或 `cloud-platform` 到 `GOOGLE_SCOPES`，
代價是每個人都得重新授權一次。順帶好處是 Drive 自帶版本歷史與編輯者記錄。

合併規則：

```
本機 glossary.json  ─┐
                     ├─ 同 id 時「本機」勝出 → 本機是個人微調／尚未上游的實驗
共用 glossary.shared ┘   共用檔是團隊累積的基準
```

讀取行為（**任何失敗都不會讓會議記錄跑不出來**）：

| 情況 | 行為 |
|---|---|
| cache 在 TTL 內 | 用 cache，不打 Drive |
| cache 過期或不存在 | 抓 Drive，寫入 `~/.config/generate-meeting-notes/glossary.shared.cache.json` |
| Drive 失敗但有 cache | 用過期 cache，印警告 |
| Drive 失敗且無 cache | 只用本機，印警告 |
| `shared_glossary` 未設定 | 只用本機（等同舊行為） |

每次執行印一行來源統計，例如
`📚 glossary：共 100 筆進 context（共用 101 筆／Drive + 本機 101 筆，其中 101 筆覆寫共用）`。
**若「覆寫共用」接近本機總數**，代表本機是共用檔的完整複本 ——
別人改進共用檔既有條目時你收不到（只有新增的 id 收得到）。
要完全跟上共用檔，把本機 glossary 縮成只放個人 delta。

寫回共用檔請用明確指令，不要在產會議記錄的流程裡順手 push ——
共用詞彙表被無聲改動比詞彙錯誤更難查。
