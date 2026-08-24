# 疑難排解

## 環境

| 症狀 | 處理 |
|---|---|
| `uv` 找不到 | `brew install uv` |
| `ffmpeg` 找不到 | 只有流程 B 需要。`uv run scripts/setup.py --with-audio`，或 `brew install ffmpeg` / `sudo apt install ffmpeg` |
| NotebookLM 認證失敗 | `uv run notebooklm auth check --test` → 失敗再 `uv run notebooklm login` |
| 找不到 Notebook | `config.json` 的 `notebook_name` 要與 NotebookLM 上完全一致 |
| 找不到會議類型 | `--meeting` 的值要與 `config.json` 裡 `meetings` 的 key 完全一致 |
| NotebookLM run 失敗後重跑 | 前次可能已上傳部分 source。目前沒有自動 cleanup，先到 NotebookLM 網頁刪掉該 Notebook 裡前次失敗的 source 再重跑 |

## Google 認證

檔案角色（`credentials.json` vs `google_token.json`）見 `setup.md`。

### `403 ACCESS_TOKEN_SCOPE_INSUFFICIENT`

> **2026-08-21 起這件事應該不會再發生。** 自有 OAuth client 已就位：
> `~/.config/generate-meeting-notes/credentials.json`
> （`<your-oauth-client-name>`，Desktop app，project `<your-gcp-project>`），
> 走 `get_google_credentials()` 的**來源 1**，token 存 `google_token.json`。
> 已驗證授到 `drive` + `documents`，Docs `batchUpdate` 可寫入，`quota_project` 為 None。
> **ADC 整條路不再被觸及** —— 別人怎麼跑 `gcloud auth application-default login` 都影響不到。
> 背景與決策脈絡請記錄在你自己的團隊文件中。

先確認 `credentials.json` 在不在。**在 → 不要碰 gcloud**，重跑授權即可
（會開瀏覽器；同意畫面顯示「你的 consent screen 名稱」是正常的，那是該 GCP project 的 consent screen 名稱）：

```bash
rm ~/.config/generate-meeting-notes/google_token.json   # 只在 token 壞掉時才刪
# 之後任何一次正常執行都會重新走授權流程
```

### ADC fallback（只在 `credentials.json` 不存在時才會走到）

```bash
gcloud auth login --enable-gdrive-access --update-adc
```

- **`--update-adc` 不可省略。** 少了它只更新 gcloud 自己那份 credential，
  `google.auth.default()` 讀的 ADC 檔（`~/.config/gcloud/application_default_credentials.json`）
  不動，403 依舊
- Docs API 接受 `drive` scope，不需要另外索取 `documents`
- 這條是 legacy 旗標、受 reauth session policy 影響，決策文件已列為排除選項。
  **只適合互動式一次性救急，排程用它會週期性失敗**

診斷 ADC 實際拿到什麼 scope：

```bash
cd "$SKILL_DIR" && uv run python -c "
import google.auth, google.auth.transport.requests as tr, json, urllib.request
c, _ = google.auth.default(); c.refresh(tr.Request())
print(json.load(urllib.request.urlopen(
    'https://oauth2.googleapis.com/tokeninfo?access_token=' + c.token))['scope'])"
```

### `This app is blocked`

只發生在借用 gcloud 內建 OAuth client 時（它不允許直接索取 drive / documents
這類 sensitive scope）。自有 client 是 Internal user type，**免 Google app verification**，
實測不會被擋。

若自有 client 授權時仍被擋 → Google Workspace 管理主控台 → Security → Access and data control →
API controls → Manage Third-Party App Access → Internal apps → **Trust internal apps**。
只需 Service Settings administrator，不需 super admin，開一次涵蓋所有未來的內部 client。

### 原本可以寫入，突然變成 403

只在走 ADC fallback 時才會遇到。任何人／任何程序跑過**不帶 scopes** 的
`gcloud auth application-default login`，都會把帶 drive 的 ADC 覆寫成窄 scope 版
（用 ADC 檔的 mtime 可以確認）。用 `credentials.json` 就沒有這個共用狀態問題。

### 「請求什麼」≠「授到什麼」

**沒報錯不等於 scope 拿到了。** 用
`https://oauth2.googleapis.com/tokeninfo?access_token=<token>` 反查實際授到的 scope。

**user credential 無法自我提權** —— 傳給 `google.auth.default(scopes=...)` 的 scopes
對它無效，scope 在授權當下就固定了。
