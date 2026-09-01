# Continuity

跨 session 帶 context。在 context 用完之前寫下來，另一頭再撿起來。

**User-invoked** — reachable only when you type them.

- **[spawn](./spawn/SKILL.md)**: Hand this session's handoff doc to a fresh Claude in a new cmux surface

**Model-invoked** — the model can reach for these when the description matches.

- **[create-handoff](./create-handoff/SKILL.md)**: Create comprehensive handoff documents for transferring work to another agent session
- **[heptabase-task-card](./heptabase-task-card/SKILL.md)**: 在 Heptabase 建立符合 Sprint whiteboard 標準格式的任務卡片
- **[resume-handoff](./resume-handoff/SKILL.md)**: Resume work from a handoff document with context analysis and validation
- **[start-day](./start-day/SKILL.md)**: 每日早晨任務看板：整合 gsheet / GitHub / Heptabase Sprint 三處任務狀態
