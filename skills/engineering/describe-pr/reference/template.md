# PR body template

Repo 沒有 `.github/PULL_REQUEST_TEMPLATE.md` 時用這份。沒內容可寫的段落整節刪掉，`Merge danger` 例外：每個 PR 都寫。段落規則見 [`../SKILL.md`](../SKILL.md) 的 `## Questions`。

`<…>` 是要換掉的佔位；引號內的是示範寫法，不是要照抄的內容。

```markdown
## What problem(s) was I solving?

<第一句：什麼壞了。第二句：誰付出代價、怎麼付。>
<例：公開 NDJSON export 帶出了 user_email。任何拿到下載連結的人都看得到客戶 email。>

<背景、cold-reader 註解表、起因 PR（選填）>

## What user-facing changes did I ship?

- **<粗體 lead-in>**：<一句話，使用者或 caller 觀察得到的變化>

<或整節只寫：No user-facing changes.>

## How I implemented it

| 檔案 | 規模 | 角色 |
|---|---|---|
| `<path>` | <+N / −M> | <這次改動裡它負責什麼> |

<逐檔講「為什麼是這個形狀」，附 `file:line`。可能被誤讀成有做的，寫 non-goal。>

## How to verify it

- [x] `<跑過且通過的指令>`
- [ ] `<沒跑的指令>`：<為什麼沒跑>

## Description for the changelog

<一句話，release note 語氣>

## Merge danger

**Door:** <two-way | one-way>｜<例：revert 這個 commit 就回到原狀，沒有資料或外部狀態被改>

**Blast radius:** <無 | 小 | 中 | 大>｜<例：只有 `export.py` 的 NDJSON 輸出，下游唯一 consumer 是 Looker 報表>

<one-way 時：哪一步收不回、merge 前怎麼降風險（選填）>

Fixes #<N>
```
