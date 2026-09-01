# Walkthrough Template

此文件是 `/implement-plan` 和 `/implement-team-plan` 收尾時使用的完工報告 spec。
Agent 讀取此 spec，照各 section 填寫內容，**直接在對話中輸出**，不寫入任何檔案。

---

## 填寫規則

- 每個 section 都要填，不能省略
- Section 5「關鍵決策」若真的完全照計畫，明確寫「無差異」，不要留空
- Section 7「自動驗證」只列實際跑過的，沒跑的不要虛報
- Section 9「Out of Scope」若有 plan 列的項目本次沒做，必須列出並說明理由

---

## 輸出格式

```markdown
---
plan: <相對路徑到 plan 檔>
implemented_by: <agent/session 標記>
date: <YYYY-MM-DD>
status: <complete | partial | blocked>
---

# Walkthrough：<plan 標題>

## 1. 目標回顧
<1-2 句話說明 plan 的 What & Why>

## 2. 最終結果一句話
<使用者最關心的 bottom line：做完了什麼、能用嗎>

## 3. Phase 執行狀態

| Phase | 狀態 | 備註 |
|---|---|---|
| Phase 1: <name> | ✅ done / ⚠️ partial / ❌ blocked | <1 行> |
| Phase 2: ... | | |

## 4. 檔案變更
每個檔案一行，標明新增 / 修改 / 刪除與一句話作用。

- `path/to/file.py` — 新增：<做什麼>
- `path/to/file.py:L23-L45` — 修改：<做什麼>
- `path/to/old.py` — 刪除：<原因>

## 5. 關鍵決策 & 與計畫差異
- <決策 1>：plan 說 A，實作選 B，因為 <原因>
- <決策 2>：...
（若完全照計畫，明確寫「無差異」）

## 6. 過程中遇到的問題 & 解法
- **問題**：<症狀> → **根因**：<為什麼> → **解法**：<怎麼做> → 參考：<commit / file:line>
（若無問題，寫「無」）

## 7. 驗證結果

### 自動驗證（已跑）
- [x] `<command>` — <結果>
- [ ] `<command>` — <跳過原因>

### 手動驗證（請使用者執行）
- [ ] <步驟 1>
- [ ] <步驟 2>

### 已知未驗證的風險
- <風險 1：什麼情況下可能壞，怎麼監控>
（若無，寫「無」）

## 8. Follow-ups / 後續建議
- <下一步 1：what + why>
- <下一步 2>
（若無，寫「無」）

## 9. Out of Scope（刻意沒做）
- <原 plan 標的，但本次沒做，理由>
（若完全按計畫執行，寫「無」）
```
