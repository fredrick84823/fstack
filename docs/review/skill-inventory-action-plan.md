# Skill Inventory Action Plan

Created: 2026-07-08

Source feedback file:
`/Users/fredrick/Desktop/01_Work/workspace/fstack/skill-inventory-review-result.json`

Last updated: 2026-07-10

## Summary

| Decision | Count |
|---|---:|
| keep | 41 |
| maybe | 15 |
| remove | 8 |
| total | 64 |

## Recommended Next Step

Status: done on 2026-07-10. The `remove` items were moved out of active
skills and into quarantine:

`/Users/fredrick/.agents/skills.disabled/2026-07-08-skill-cleanup`

Active local skills after quarantine: 57.

Note: `code-review` is currently active but was not present in the exported
64-row review JSON, so it still needs a separate keep/remove decision.

不要直接刪除。先建立 quarantine 目錄，將 `remove` 項目移出 active skills：

```bash
mkdir -p /Users/fredrick/.agents/skills.disabled/2026-07-08-skill-cleanup
```

移動後觀察一段時間；如果沒有缺口，再永久刪除或從 source repo 移除。

## Quarantine Now

這 8 個是你已明確標成 `remove` 的 skill。

Status: done on 2026-07-10.

| Skill | Source | Reason / Feedback | Note |
|---|---|---|---|
| `codex-brainstorm` | fstack | 之前 Claude Code 就不常用；現在主要用 Codex 後更用不到。 | 若從本機移除但保留在 fstack，之後同步可能會回來。 |
| `codex-cli-review` | fstack | 之前 Claude Code 就不常用；現在主要用 Codex 後更用不到。 | 同上，需決定是否也從 fstack 移除。 |
| `excalidraw-diagram` | local | 無額外回饋。 | 可先 quarantine。 |
| `gcp-debug` | local | 用不到，直接用 `gcloud logging` CLI 即可。 | 可先 quarantine。 |
| `graphify` | local | 無額外回饋。 | 可先 quarantine。 |
| `start-day` | fstack | 用不到，暫時移除。 | 若從本機移除但保留在 fstack，之後同步可能會回來。 |
| `start-standup` | local | 用不到，暫時移除。 | 可先 quarantine。 |
| `startup-ideation` | local | 用不到。 | 可先 quarantine。 |

Suggested quarantine command:

```bash
dest=/Users/fredrick/.agents/skills.disabled/2026-07-08-skill-cleanup
mkdir -p "$dest"
for skill in \
  codex-brainstorm \
  codex-cli-review \
  excalidraw-diagram \
  gcp-debug \
  graphify \
  start-day \
  start-standup \
  startup-ideation
do
  if [ -d "/Users/fredrick/.agents/skills/$skill" ]; then
    mv "/Users/fredrick/.agents/skills/$skill" "$dest/"
  fi
done
```

Executed result:

- moved `codex-brainstorm`
- moved `codex-cli-review`
- moved `excalidraw-diagram`
- moved `gcp-debug`
- moved `graphify`
- moved `start-day`
- moved `start-standup`
- moved `startup-ideation`

## Needs Rename Or Scope Change

這些不是單純刪除，應另外開 rename/migration task。

| Skill | Decision | Feedback | Suggested direction |
|---|---|---|---|
| `digest-agent` | maybe | 改名。 | 找更明確的名稱，例如 journal/digest/reflection 類。 |
| `personal-wiki-mine` | maybe | 想改名。 | 名稱應更貼近 candidate claims / wiki mining。 |
| `tagtoo-create-flow` | maybe | 改名。 | 可改成更泛用的 Tagtoo knowledge-flow 命名。 |
| `tagtoo-cross-repo` | maybe | 改名。 | 可改成更明確的 Tagtoo service-map / cross-service lookup。 |
| `deep-inquiry` | keep | 可能想改名。 | 保留功能，評估名稱是否與實際 research workflow 對齊。 |
| `deep-inquiry-v2` | keep | 想改名，`v2` 很不直覺。 | 避免版本號命名；用能力差異命名。 |
| `research-article` | keep | 改名。 | 可改成 article-research-draft / expert-view-article。 |

## Maybe / Watchlist

這些目前不是 remove，但使用頻率或定位還需要再判斷。

| Skill | Source | Feedback |
|---|---|---|
| `create-team-plan` | fstack | 無額外回饋。 |
| `deep-module` | fstack | 覺得使用頻率不高。 |
| `extract-skill` | fstack | 之後會被 skillify 取代。 |
| `heavyskill` | local | 無額外回饋。 |
| `heptabase-task-card` | fstack | 無額外回饋。 |
| `implement-team-plan` | fstack | 無額外回饋。 |
| `product-lens` | local | 無額外回饋。 |
| `repos-wiki-ingest` | local | 轉移成 career project level skill。 |
| `repos-wiki-lint` | local | 轉移成 career project level skill。 |
| `repos-wiki-query` | local | 轉移成 career project level skill。 |
| `verify-audience-write` | local | 無額外回饋。 |

## Keep

保留 41 個：

`agent-browser`, `ask-codebase-questions`, `beautiful-mermaid`,
`bigquery-cost-control`, `bigquery-labeled-query`, `brainstorming`,
`cf-verify`, `clean-worktree`, `create-handoff`, `create-plan`,
`cross-machine-runtime-sync`, `deep-inquiry`, `deep-inquiry-v2`,
`design-concept`, `find-skills`, `generate-meeting-notes`,
`generate-pm-weekly-doc`, `grill-me`, `gsheet-progress-sync`,
`implement-plan`, `improve`, `job-application-optimizer`,
`personal-llm-wiki`, `personal-wiki-inject`, `personal-wiki-lint`,
`personal-wiki-query`, `plugin-creator`, `research-and-plan`,
`research-article`, `research-codebase`, `resume-handoff`,
`rss-research-digest`, `self-observer`, `skill-memory-reflect`,
`slack-canvas`, `slack-message`, `start-worktree`, `structure-outline`,
`ui-ux-pro-max`, `vercel-deployment`, `work-wrap-up`.

## Important Source Note

Some `remove` items are from `fstack`:

- `codex-brainstorm`
- `codex-cli-review`
- `start-day`

If they are only moved out of `/Users/fredrick/.agents/skills`, future fstack sync may reinstall them. For these, decide separately whether to:

1. keep them in fstack but not active locally;
2. remove them from fstack source;
3. move them to an optional/disabled bundle.
