# Skill Candidate Protocol

定義 `<<SKILL_CANDIDATE ...>>` marker 格式與使用規範。
讓 agent 在發現可抽取 skill 的模式時，以標準化方式記錄候選。

---

## Marker 格式

```
<<SKILL_CANDIDATE
name: {suggested-kebab-case-name}
reason: {為何想抽取 — 看到了什麼模式，出現幾次}
steps: {步驟摘要；多行用分號或換行分隔}
invoker: {觸發詞建議，例如：「deploy CF」「部署 cloud function」}
>>
```

- `name` 必填，其他欄位選填
- 用 `<<` / `>>` 包起（罕見符號，不會污染正常輸出）
- 目標 < 100 tokens

---

## 觸發時機

Agent 應在以下情況輸出 marker：

1. **同一個操作在本 session 出現 2+ 次**，且沒有對應的 skill
2. **多步驟的固定序列**，使用者可能在未來重複執行
3. **有明確 before/after 格式的轉換**，且轉換規則可被描述

**不應觸發**：一次性操作、與 context 強綁定的任務、已有 skill 的操作

---

## 自動捕捉（Claude Code）

安裝 Stop hook 後，每次 agent turn 結束時自動 grep marker：

```json
{
  "hooks": {
    "Stop": [
      { "type": "command", "command": "~/.agents/skills/improve/scripts/capture-skill-candidate.sh" }
    ]
  }
}
```

`install.sh` 在安裝 improve 時會詢問是否啟用此 hook。

---

## 手動提交（所有環境）

若無 hook（Codex CLI 等），agent 或使用者可直接呼叫：

```bash
~/.agents/skills/improve/scripts/propose.sh \
  --name "deploy-to-cf" \
  --reason "第三次執行相同的 gcloud build + deploy 流程" \
  --steps "gcloud builds submit; gcloud functions deploy; gcloud functions logs read" \
  --hints "deploy CF, 部署 cloud function"
```

---

## 後續處理

`candidate-queue.md` 不隨 repo 發佈，hook 與 `propose.sh` 在檔案不存在時自行建立。條目格式：

```markdown
## [{ISO 8601 timestamp}] {suggested-kebab-case-name}

- **status**: pending
- **hit_count**: 3
- **first_seen**: {ISO 8601 timestamp}
- **last_seen**: {ISO 8601 timestamp}
- **reason**: 重複執行 gcloud build + deploy + verify 三步驟
- **steps**: |
  1. gcloud builds submit
  2. gcloud functions deploy
  3. gcloud functions logs read
- **invoker_hints**: 「deploy CF」、「部署 cloud function」
```

**Status 值**：`pending` | `created` | `rejected` | `merged` | `duplicate`

累積候選後，執行 `/extract-skill` 批次審核並建立正式 skill。
