# Skill Candidate Queue

Agent 在執行過程中發現可抽取為 skill 的重複模式，自動 append 到此檔。
`/extract-skill` 讀取 `status: pending` 項目，審核後建立正式 skill。

**Status 值**：`pending` | `created` | `rejected` | `merged` | `duplicate`

---

<!-- 範例格式（請勿刪除）：

## [2026-04-21T21:15+08:00] deploy-to-cf

- **status**: pending
- **hit_count**: 3
- **first_seen**: 2026-04-21T14:00+08:00
- **last_seen**: 2026-04-21T21:15+08:00
- **reason**: 重複執行 gcloud build + deploy + verify 三步驟
- **steps**: |
  1. gcloud builds submit
  2. gcloud functions deploy
  3. gcloud functions logs read
- **invoker_hints**: 「deploy CF」、「部署 cloud function」

-->
