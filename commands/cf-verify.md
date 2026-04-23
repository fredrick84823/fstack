---
description: Cloud Function 完整測試與驗證：unit → integration → e2e(local) → deploy → trigger → GCP logs
argument-hint: '[--auto-deploy] [function_name]'
allowed-tools: Bash, mcp__gcp__*
---

## Flags

- `--auto-deploy`：本地三階段測試（Unit → Integration → E2E）全通過後，**不詢問**，直接進入 CI/CD 部署階段

## 自動化原則

除非遇到以下情況，否則**不中斷流程、不詢問使用者**：
1. Codex 提出具體修復建議（讓使用者決定是否套用）
2. 本地三階段測試全通過，且**未帶 `--auto-deploy`**（部署前最終確認）
3. 遇到需要人工判斷的環境問題（如缺少 credentials）

## 你的任務

幫使用者對 Cloud Function 執行完整的測試與驗證流程（Python 專案）。

根據使用者需求，可執行以下任意階段或全部階段：

| 階段 | 說明 | 時機 |
|------|------|------|
| Unit Test | 本地單元測試，mock 外部依賴 | 開發中、PR 前 |
| Integration Test | 整合測試，接真實服務 | 部署前 |
| E2E / Smoke Test | 本地端對端測試，驗證主要流程 | 部署前，CI 前 |
| Deploy 驗證 | 確認 CI/CD 部署完成 | 部署後 |
| CF Trigger | 實際觸發已部署的 function | 部署後 |
| GCP Logs 分析 | 確認 logs 無異常 | 部署後 |

---

### Step 0: 確認範圍

先確認使用者想執行哪些階段：
- 若使用者說「跑測試」→ 執行 Unit + Integration + E2E
- 若使用者說「部署後驗證」→ 執行 Deploy 驗證 + CF Trigger + GCP Logs
- 若使用者說「完整驗證」或「全跑」→ 全部六個階段（本地測試先完成才觸發部署）
- 若 context 不明 → 詢問使用者

---

### Step 0.5: Codex Code Review（自動執行）

在 CF 專案目錄執行 `/codex:review --wait`，review 當前 git diff：

- 強制 foreground（`--wait`），不詢問執行模式
- Claude 自行解讀 review 結果：
  - 無重大問題 → 直接進入 Step 1，不中斷
  - 有明顯 bug 或風險 → 回報給使用者後停止，讓使用者決定是否繼續

---

### Step 1: Unit Tests（本地）

在本地執行單元測試，所有外部依賴皆 mock：

```bash
cd <function_directory>
python -m pytest tests/unit/ -v
```

**判斷結果：**
- ✅ 全部通過 → 直接進入下一步，不中斷
- ❌ 有失敗 → 自動執行 `/codex:rescue --wait` 並帶入失敗的 test output，Claude 解讀結果後繼續流程；若 Codex 提出修復建議則回報使用者

---

### Step 2: Integration Tests（本地）

執行整合測試，連接真實外部服務（確認 `.env` 或環境變數已設置）：

```bash
python -m pytest tests/integration/ -v
```

若需要 GCP 服務，確認已認證：

```bash
gcloud auth application-default login
```

**判斷結果：**
- ✅ 全部通過 → 直接進入下一步，不中斷
- ❌ 有失敗 → 自動執行 `/codex:rescue --wait` 並帶入失敗的 test output，Claude 解讀結果後繼續流程；若 Codex 提出修復建議則回報使用者

---

### Step 3: E2E / Smoke Test（本地）

本地端對端測試，模擬 Cloud Function 實際接受 HTTPS request 的方式。此步驟在部署（CI）之前執行。

**3a. 啟動 local server（另開一個 terminal）：**

```bash
# 方法一（若有 Makefile）
make serve

# 方法二（直接用 functions-framework）
functions-framework --source=main.py --target=FUNCTION_TARGET --port=8080
```

**3b. 確認 server 已就緒後，執行 E2E 測試：**

```bash
python -m pytest tests/e2e/ -v -m e2e
```

測試腳本會對 `http://localhost:8080/` 發送 POST request，驗證各種 payload 的回應行為（200、400 等）。

**判斷結果：**
- ✅ 全部通過 → 直接進入下一步，不中斷
- ❌ 有失敗 → 自動執行 `/codex:rescue --wait` 並帶入失敗的 test output，Claude 解讀結果後繼續流程；若 Codex 提出修復建議則回報使用者

**重要：** E2E 全部通過後，才停下來詢問使用者是否繼續觸發 CI/CD 部署（唯一的人工確認點）。

---

### Step 4: 確認部署狀態

本地測試通過後，確認 CI/CD 是否部署完成：

```bash
gh run list --limit 5
```

- 若部署未完成 → 等待或提示使用者
- 確認目標 function 的最新 commit 已部署

---

### Step 5: 觸發已部署的 CF

部署完成後，實際觸發 Cloud Function 進行最終驗證：

```bash
# 取得 function URL
gcloud functions describe FUNCTION_NAME \
  --region=REGION \
  --project=PROJECT_ID \
  --format="value(httpsTrigger.url)"

# 觸發 function（帶入 JSON payload）
curl -X POST "FUNCTION_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: bearer $(gcloud auth print-identity-token)" \
  -d '{
    "key1": "value1",
    "key2": "value2"
  }'
```

**詢問或從 context 推斷正確的 payload 欄位**（參考 E2E 測試中使用的 payload 結構）。記錄 HTTP 狀態碼、回應內容、執行時間。

---

### Step 6: GCP Logs 分析

查詢該 Cloud Function 最近 10 分鐘的 logs，篩選 WARNING 以上層級：

```bash
gcloud logging read \
  'resource.type="cloud_function" AND resource.labels.function_name="FUNCTION_NAME" AND severity>=WARNING' \
  --project=PROJECT_ID \
  --freshness=10m \
  --format='table(timestamp, severity, textPayload)' \
  --limit=50
```

若使用 Cloud Run（2nd gen）：

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="FUNCTION_NAME" AND severity>=WARNING' \
  --project=PROJECT_ID \
  --freshness=10m \
  --format='table(timestamp, severity, textPayload, jsonPayload.message)' \
  --limit=50
```

確認是否有非預期錯誤，記錄 WARNING / ERROR 數量。

---

### Step 7: 結論回報

整合所有階段結果：

```
════════════════════════════════════════════════
CF VERIFY 結果報告
════════════════════════════════════════════════
Unit Tests      ✅ 12/12 通過
Integration     ✅ 5/5 通過
E2E / Smoke     ✅ 3/3 通過
Deploy Status   ✅ 已部署（commit: abc1234）
CF Trigger      ✅ HTTP 200，回應符合預期
GCP Logs        ⚠️ 1 個 WARNING（非嚴重，見下方）
════════════════════════════════════════════════
整體結論：✅ 行為符合預期，可正式上線
```

---

### 守則

- 若有多個 function 需驗證，依序執行每個
- 429 錯誤視為「instance 不足」的警告，非真實失敗
- 測試路徑（`tests/unit/`、`tests/integration/`、`tests/e2e/`）依實際專案結構調整
- `codex:review` 使用 `--wait`，不詢問執行模式，Claude 自行解讀結果後繼續
- 測試失敗時自動執行 `codex:rescue --wait`，不先詢問使用者；Claude 拿到結果後繼續流程
- Codex rescue 若在背景執行，完成後用 `/codex:result` 取得輸出
- **唯一中斷點**：本地三階段（Unit → Integration → E2E）全通過後，確認是否觸發 CI/CD 部署（帶 `--auto-deploy` 則跳過此確認）
