# Signal Queue

各 skill 執行時偵測到缺口，自動 append 到此檔。
`/improve` 讀取 `status: pending` 項目，處理後更新 status。

**Status 值**：`pending` | `resolved` | `rejected` | `deferred`

---

<!-- 範例格式（請勿刪除）：

-->

---

## [2026-04-23] improve / signal routing

- **type**: S3
- **source**: session tagtoo-mcp-servers — gsheet-mcp-apps-demo 部署
- **gap**: 使用者說「記錄 signal」時，agent spawn 了 subagent 把內容寫到 project memory（memory/project_mcp_apps_deployment_signals.md），沒有走 signal-queue.md 標準路徑。`improve` SKILL.md 應明確說明：收到「記錄 signal / save signal」指令時，直接 append 到對應 scope 的 signal-queue.md，不要另起 subagent 或寫 memory 檔
- **status**: pending

---

## [2026-04-23] deploy-ts-mcp-server (future skill) / MCP Apps CSP + document.write

- **type**: S1
- **source**: session tagtoo-mcp-servers — gsheet-mcp-apps-demo 部署
- **gap**: MCP Apps iframe (claudemcpcontent.com) 有嚴格 CSP：外部 CDN script 被封鎖，且用 document.write(html) 注入 content。Inline <script type="module"> + 大型 bundled JS 內含 <"u" 等序列會導致 SyntaxError。解法：build-time Tailwind CSS（不用 CDN）+ IIFE format + base64 data: URL 作為 script src（CSP 允許 data:，且完全繞開 inline script parsing）
- **status**: pending

---

## [2026-04-23] deploy-ts-mcp-server (future skill) / Cloud Run PORT reserved

- **type**: S1
- **source**: session tagtoo-mcp-servers — gsheet-mcp-apps-demo 部署
- **gap**: Cloud Run 自動注入 PORT=8080，Terraform env_vars 裡不能包含 PORT，否則 400 錯誤。deploy skill 應明確排除 PORT
- **status**: pending

---

## [2026-04-23] deploy-ts-mcp-server (future skill) / BASE_URL 雞生蛋

- **type**: S1
- **source**: session tagtoo-mcp-servers — gsheet-mcp-apps-demo 部署
- **gap**: Cloud Run service URL 部署後才知道，但 loadEnv() 強制要求 BASE_URL 非空（否則 crash）。需要兩步流程：(1) placeholder URL → terraform apply → 取得 service URL (2) 更新 tfvars → 再次 apply。skill 應內建此流程引導
- **status**: pending

---

## [2026-04-23] deploy-ts-mcp-server (future skill) / Secret Manager 需先有 version

- **type**: S1
- **source**: session tagtoo-mcp-servers — gsheet-mcp-apps-demo 部署
- **gap**: terraform apply 建立 secret container 後，Cloud Run 啟動時找不到 version（即使 secret 存在也會 SECRETS_ACCESS_CHECK_FAILED）。必須先注入 placeholder：echo -n "placeholder" | gcloud secrets versions add SECRET --data-file=- 才能成功啟動
- **status**: pending

---

## [2026-04-23] deploy-ts-mcp-server (future skill) / OAuth callback 路徑

- **type**: S1
- **source**: session tagtoo-mcp-servers — gsheet-mcp-apps-demo 部署
- **gap**: TS OAuth broker 的 callback endpoint 是 /oauth/google/callback，GCP Console 要填精確路徑。可用 curl -sv "$BASE_URL/authorize?..." 看 Location header 確認實際路徑，不要猜
- **status**: pending

