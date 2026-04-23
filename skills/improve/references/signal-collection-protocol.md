# Signal Collection Protocol

給其他 skill 參考的 opt-in 範本。當你的 skill 想在執行過程中自動通知 `/improve` 時，在 SKILL.md 末尾加入以下區塊（替換尖括號的內容）。

---

## 範本

在目標 skill 的 `SKILL.md` 末尾加入：

```markdown
## Signal Collection

偵測到以下情況時，自動 append 到對應的 `signal-queue.md`：
- <具體情況描述，例如：若有 ❌ 未覆蓋項目>
- <另一個情況>

格式：
\`\`\`
## [{ISO 8601 timestamp}] {this-skill-name}

- **type**: S1/S2/S3
- **source**: {觸發來源路徑或描述}
- **gap**: {一句話描述缺口}
- **status**: pending
\`\`\`

執行後輸出：`⚠️ 已新增 N 個 pending signal，建議執行 /improve`

**Cowork 即時處理**：若在 cowork session 中偵測到 signal，
輸出格式改為：

```
⚠️ [IMPROVE_SIGNAL] {skill-name}: {gap 一句話}
已 append 到 signal-queue.md。建議在本 session 中立即執行 /improve。
```

Cowork 協調者看到 `[IMPROVE_SIGNAL]` 標記時，應在當前 task 完成後
立即 spawn 一個 /improve agent 處理，而不是等待下次 SessionStart。
```

---

## Signal 類型速查

| 類型 | 適用情境 |
|------|---------|
| **S1** | 本 skill 的產出被下游 skill 驗證發現缺口 |
| **S2** | 使用者手動修正了本 skill 的判斷 |
| **S3** | 本 skill 執行時偵測到自身規則的邊界案例 |

---

## Queue 路徑規則

Signal 應 append 到以下路徑（優先順序）：

1. 若 cwd 有 `.claude/skills/improve/signal-queue.md` → 寫入此處
2. 否則 → 寫入 `~/.claude/skills/improve/signal-queue.md`

若兩者都不存在，建立 user-level 檔案後再 append。
