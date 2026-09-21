# 首次設定與 Google 認證

## 安裝

```bash
cd "$SKILL_DIR" && uv run scripts/setup.py              # 文字輸入 + main synthesis
cd "$SKILL_DIR" && uv run scripts/setup.py --with-audio # 再加上 Audio Source Extraction
```

`setup.py` 先偵測 `~/.config/generate-meeting-notes/credentials.json`；沒有就引導放置，
只有在使用者明確選擇時才走 ADC fallback。驗證走 `get_google_credentials()`，
與正式流程同一條路徑。

設定重置：重跑同樣的指令即可。

## `config.json`

```json
{
  "meetings": {
    "team週會": {
      "notebook_name": "Team 會議記錄",
      "folder_id": "1EXAMPLE_FOLDER_ID...",
      "folder_name": "team-meetings",
      "series_name": "Data內會",
      "slack_channel": "C0XXXXXXXXX",
      "attendees": ["Alice", "Bob", "Carol", "PM-Name"],
      "custom_prompt": "本次會議報告順序固定如下：Alice → Bob → Carol，皆向 PM-Name（PM）報告。"
    }
  },
  "prompt_path": "~/.config/generate-meeting-notes/prompt.md",
  "glossary_path": "~/.config/generate-meeting-notes/glossary.json"
}
```

| 欄位 | 說明 |
|---|---|
| `attendees` | 固定與會者，腳本自動填進 Google Doc 的「與會者」欄位 |
| `notebook_name` | 只有流程 B 用得到 |
| `custom_prompt` | 給 agent 的補充（報告順序、人名對照），提升格式一致性與講者推斷品質 |
| `folder_name` | Slack 通知裡顯示的雲端路徑名稱 |
| `series_name` | Google Doc 名稱裡的系列名 |
| `slack_channel` | 三態：欄位不存在／`null` = 還沒設定（記錄照產，DM 提醒補上）；`""` = 刻意不發通知；`"C0…"` = 發那個 channel。改用 `scripts/channel.py --meeting <key> --channel <id>` 寫回（會先備份設定檔） |
| `slack_dm_user` | 你的 Slack Member ID；會議還沒設 channel 時 DM 提醒你。沒設就只印在 stdout |
| `glossary_path` | 本機詞彙表，見 `glossary.md` |
| `shared_glossary` | 可選，團隊共用詞彙表，見 `glossary.md` |

新增會議類型：直接在 `meetings` 下加一個 key。

自定義 prompt：`prompt_path` 指向的檔（安裝時從 `references/default-prompt.md` 複製），
直接編輯即可調整會議記錄格式與重點。

## 認證檔案的角色

`~/.config/generate-meeting-notes/` 下有兩個容易混淆的檔案。**一個可以發給同事，一個絕對不能。**

```
credentials.json   輸入。GCP Console 下載的「app 身分」
                   client_id / client_secret / auth_uri / token_uri
                   redirect_uris / project_id
                   不含任何 token。所有人拿到同一份 → 可以發給同事
        │
        │  OAuth flow（開瀏覽器 → 本人按「同意」）
        ▼
google_token.json  輸出。「誰」把權限給了那個 app
                   refresh_token（不過期）/ token / expiry（1hr）/ scopes
                   每人不同 → 絕不可分享
                   refresh_token = 該人的 Drive 存取權
```

1. `credentials.json` 是 **app 身分**，可分享。缺了它整條自有 client 路徑走不通，會降級到 ADC
2. `google_token.json` 是 **個人授權**，絕不可分享。刪掉的代價只是重跑一次瀏覽器同意
3. **client 不決定你能碰到什麼檔案** —— 它只決定「用哪個 app 去要權限」。
   能不能讀某個共用雲端硬碟資料夾由該資料夾的 ACL 決定，換 client 不會改變

因此 `404` / permission denied 通常是**不是那個資料夾的成員**，不是 scope 問題；
只有 `403 ACCESS_TOKEN_SCOPE_INSUFFICIENT` 才是 scope 問題。見 `troubleshooting.md`。

## 排程

每小時一輪，讓 `reconcile_drive.py` 自己消化積壓。

macOS 走 launchd —— cron 拿不到登入 session 的 keychain，而刷新 Google 憑證要它。
`~/Library/LaunchAgents/com.generate-meeting-notes.reconcile.plist`（label 只要在這台
機器上唯一就好，**不要放公司或專案的內部識別字** —— 這份文件是會散佈出去的）：

```xml
<key>ProgramArguments</key>
<array><string><UV_PATH></string><string>run</string><string>scripts/reconcile_drive.py</string></array>
<key>WorkingDirectory</key><string><SKILL_DIR></string>
<key>EnvironmentVariables</key>
<dict>
  <!-- launchd 給的 PATH 只有 /usr/bin:/bin:/usr/sbin:/sbin —— uv／claude／ffmpeg 一個都不在裡面 -->
  <key>PATH</key><string><UV_BIN_DIR>:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  <key>HOME</key><string><HOME></string>
</dict>
<!-- StartInterval 是唯一的觸發器。`WatchPaths` 是 SKILL.md 已經否決的那個事件觸發形狀 -->
<key>StartInterval</key><integer>3600</integer>
<key>RunAtLoad</key><false/>
<key>StandardOutPath</key><string><HOME>/Library/Logs/gmn-reconcile.log</string>
<key>StandardErrorPath</key><string><HOME>/Library/Logs/gmn-reconcile.log</string>
```

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.generate-meeting-notes.reconcile.plist
launchctl kickstart -p gui/$(id -u)/com.generate-meeting-notes.reconcile   # 首次執行本來就是強制 dry-run
```

其他平台走 cron，每小時 5 分：

```
5 * * * * cd <SKILL_DIR> && uv run scripts/reconcile_drive.py >> /tmp/gmn-reconcile.log 2>&1
```
