# Scope Resolution 詳細規則

`/improve` 的三種執行模式，及各模式的路徑對應。

---

## 三種 Scope

### `repo` 模式

**偵測條件**：cwd 下有 `skills/` 目錄，且該目錄內有至少一個 `SKILL.md`

**典型場景**：在 `tagtoo-skills` 這類 skills 源碼 repo 裡執行 `/improve`

**路徑對應**：
- Target skill：`{cwd}/skills/{target}/SKILL.md`
- Signal queue：`{cwd}/skills/improve/signal-queue.md`
- Changelog：`{cwd}/skills/improve/changelog.md`

**特殊行為**：Step 7 結束後輸出 PR 提示，建議走 PR 流程

---

### `project` 模式

**偵測條件**：cwd 下有 `.claude/skills/` 目錄

**典型場景**：在有自己 `.claude/skills/` 的專案 repo 裡執行 `/improve`

**路徑對應**：
- Target skill：`{cwd}/.claude/skills/{target}/SKILL.md`
- Signal queue：`{cwd}/.claude/skills/improve/signal-queue.md`（不存在則 fallback 到 user queue）
- Changelog：`{cwd}/.claude/skills/improve/changelog.md`

---

### `user` 模式（預設）

**偵測條件**：以上皆不符，且 `~/.claude/skills/` 存在

**典型場景**：在任意 cwd 執行 `/improve`，操作的是 user-level skills

**路徑對應**：
- Target skill：`~/.claude/skills/{target}/SKILL.md`
- Signal queue：`~/.claude/skills/improve/signal-queue.md`
- Changelog：`~/.claude/skills/improve/changelog.md`

---

## 優先順序

若 `repo` 和 `project` 條件同時成立（例如 skills repo 本身也有 `.claude/skills/`），以 `repo` 為準。

若使用者明確傳入 `SCOPE=user/project/repo`，覆蓋自動偵測。

---

## Signal Queue 雙層設計

- **Primary**：`~/.claude/skills/improve/signal-queue.md`（user-level）
- **Project override**：若 cwd 有 `.claude/skills/improve/signal-queue.md` 就優先讀它

這樣多個 repo 並行時，各自的 queue 不會互相干擾。
