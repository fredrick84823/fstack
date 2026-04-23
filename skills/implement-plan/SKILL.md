---
name: implement-plan
description: Implement an approved technical plan from thoughts/shared/plans/. Use when executing a plan that was created with create-plan. Follows phases, updates checkboxes, and pauses for human verification between phases. Reports a structured walkthrough summary inline at the end.
allowed-tools: Read, Write, Edit, Bash, Agent
---

# Implement Plan

Implement an approved technical plan phase by phase.

## Getting Started

If plan path provided: read the plan completely, check for existing checkmarks (`- [x]`), read all referenced files, then begin.

If no plan path: ask for one.

## Implementation Philosophy

- Follow the plan's intent while adapting to what you find
- Implement each phase fully before moving to the next
- Update checkboxes (`- [x]`) in the plan as you complete sections
- If something doesn't match the plan, STOP and communicate clearly

## Mismatch Format

```
Issue in Phase [N]:
Expected: [what the plan says]
Found: [actual situation]
Why this matters: [explanation]

How should I proceed?
```

## Verification After Each Phase

```bash
make check test   # or project-specific verification commands
```

Then pause for human verification:

```
Phase [N] Complete - Ready for Manual Verification

Automated verification passed:
- [checks that passed]

Please perform manual verification:
- [manual items from plan]

Let me know when manual testing is complete to proceed to Phase [N+1].
```

Do NOT check off manual testing items until confirmed by the user.
If instructed to run multiple phases consecutively, skip pauses until the last phase.

## Final Walkthrough（整份計畫收尾時必做）

所有 phase 完成（含手動驗證確認）後，**不要直接回報「done」**。
改為：

1. 讀取 `~/.claude/skills/implement-plan/references/walkthrough.md`
2. 照各 section 的提示，在對話中**直接輸出 walkthrough 內容**（不寫入任何檔案）

### 為什麼必做

plan 變大後，口頭摘要會遺漏「與計畫差異」「未驗證風險」「後續 follow-up」等對使用者
最有價值的資訊。Walkthrough 是以穩定格式回報這些資訊的唯一機制。

### 不要做的事

- 不要把 walkthrough 寫得和 plan 一樣詳細 — 它是完工報告，不是重寫計畫
- 不要把 walkthrough 寫到任何檔案 — 直接在對話輸出即可
- 不要編造驗證結果 — 沒跑的就寫「未驗證」
- 不要把「和計畫差異」欄位留白 — 若真的完全照計畫，明確寫「無差異」

## If Stuck

- Use codex:review SKILL to review current status
- Consider if codebase has evolved since the plan was written
- Present the mismatch clearly and ask for guidance

## Resuming Work

If plan has existing checkmarks:
- Trust that completed work is done
- Pick up from first unchecked item
- Verify previous work only if something seems off

If plan already has a walkthrough file, the previous run completed fully.
Check the walkthrough for any unfinished sections before continuing.
