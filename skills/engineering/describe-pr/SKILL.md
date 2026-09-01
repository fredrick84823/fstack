---
name: describe-pr
description: >
  Write a pull request description a reviewer can digest without opening
  the diff. Use when drafting or rewriting a PR body, filling a PR
  template, or deciding which parts of a change deserve a diagram.
---

# Describe PR

Reviewer *digests* **problem → observable change → how → proof** without opening the diff.

Repo has `.github/PULL_REQUEST_TEMPLATE.md`? Fill that. Else the five questions below. Section rules apply either way.

Presentation (fold, alerts, details, ship markdown): load the [`scannable-pr`](../scannable-pr/SKILL.md) skill **after the body exists** — start at **Pack bulk**. Keep these headings.

## Title & headings

Title: **繁體中文**. Every `##` / `###` heading and every `<summary>` line: **English**. Prose, tables, bullets, checklists, code comments: 繁體中文.

The split is about who reads what. A title answers *what changed* to a teammate scrolling `gh pr list` — their own language reads fastest. Headings are structure, not content: they become anchor links (`#how-i-implemented-it`), they are what a reviewer greps across PRs, and they stay stable while the prose under them is rewritten. Keeping them English makes the skeleton comparable across every PR the team opens; the sentences inside carry the meaning.

Title: 一句話講可觀察的變化, ≤72 chars — `修正公開 NDJSON 外洩 user_email`, not `修好了` and not `更新 export.py`. Match the repo's existing title convention (check `gh pr list`); adopt a `fix(scope):` prefix only if the repo already uses one — the prefix stays English, the sentence after it does not.

## Steps

1. **Read** — full diff, commits, files the diff references but does not show. Split every hunk: *user-facing* vs internal.

   **Done when:** every file in the diff is accounted for; the *problem* is one sentence the diff actually solves.

2. **Frame** — answer each kept question from the change, not from session memory. Drop a question with nothing to say. Structural content → [**Visual first**](#visual-first).

   **Done when:** a reader who stops after *problem* + *user-facing* knows whether to care; implementation cites `file:line`; *verify* is commands you ran or marked manual; multi-file roles, boundaries and forked consequences are tables or diagrams — and a diff with no structure has no diagram.

3. **Present** — load scannable-pr at Pack bulk. Ship `gh pr create` / `gh pr edit --body-file` markdown.

   **Done when:** paste-ready body; title is 繁中, headings and `<summary>` lines are English; linked issues use `Fixes`/`Closes`/`Resolves` when merge should close them.

Section's shape unclear — alternative table, boundary table, ship-fact, cost-of-choice, three-way deviation split? [`reference/examples.md`](reference/examples.md) quotes a real PR for each.

## Visual first

Structural content — 多檔案各自的角色、邊界、分岔的後果、方案比較、前後數字 — 預設畫成表或圖，散文只留給「為什麼是這個形狀」。但**多數 PR 不需要任何圖**：小改動的正確形狀就是幾行散文加一張表。

| 內容形狀 | 用 |
|---|---|
| 多個檔案各自的角色 | 表：檔案 / 規模 / 角色 |
| 同一個起點分岔成兩種後果（選 A 會怎樣、選 B 會怎樣） | `flowchart` |
| 多條路徑撞同一個失敗，或幾個元件互相守護 | `flowchart` |
| 誰在改動邊界內 / 外 | `flowchart` + `subgraph` |
| 呼叫往返、誰先誰後 | `sequenceDiagram` |
| 前後數字、方案比較、不修的理由 | 表 |

### 什麼時候不要畫

圖的成本是 reviewer 的一次視線跳躍，很多內容付不起：

- **線性鏈不畫。** `A → B → C` 沒有分岔也沒有匯流，一句話就講完了 —— 真要保留節奏就寫成一行 `無上界 → 解析到 2.x → fastmcp 消失 → import 失敗`。幾乎每個 bugfix 都有一條因果鏈，那不是畫圖的理由。
- **只改一個常數、一個版本號、一個過濾條件 → 不會有圖。** 這種 PR 的正確形狀是三行散文加一張前後對照表。
- **不畫既有系統的運作流程。** 圖只呈現「這次改動造成的結構」。為了說明「單價 6.25 改成 7.1875」而畫一張成本閘門怎麼運作的圖，是把 reviewer 的注意力帶離 diff。
- **散文兩句話講得完 → 那兩句話就是答案。**

刪圖測試比「寫不寫得出結論」可靠：**把圖拿掉，這段還讀得懂嗎？** 讀得懂就別畫。

### 畫的時候

- **一張圖只回答一個問題。** 邊的語意混了（驅動 / 守護 / 指向）就是兩張圖。
- **節點標籤是短句**；清單、數字、檔名全展開放圖後。
- **圖後 1–2 條洞察，不是圖說。** 圖給機制，洞察給結論。
- **先畫邊界。** 哪些檔案在新目錄外 = 回歸風險在哪，reviewer 第一個想知道的事。
- **只畫有來源證據的層。** 沒有 runtime 的 PR 不畫部署圖；層級不足就省略，不為了完整補節點。
- 圖 + 表仍塞不下 → `<details>`，實測數字放裡面，圖留在外面。

Mermaid 語法與 fold 機制歸 [`scannable-pr`](../scannable-pr/SKILL.md)；這裡只決定「畫什麼、畫幾張」。

## Questions

### What problem(s) was I solving?

The gap as it existed *before* this PR — a failure mode the reviewer recognizes. Cause and intro PR if known. Stop before the fix.

### What user-facing changes did I ship?

What a user or caller can observe. Bold lead-in + one sentence. `No user-facing changes.` is a complete answer.

### How I implemented it

Internals for the person opening the diff. Group by component — 分組若用 `###`，那也是 heading，一樣是 English（`Test harness`, not `兩套 harness`）；不想翻就用粗體 lead-in，那是 prose，繁中。`file:line`. Shape and why that shape. Name the non-goal when the diff could be misread as including it.

這節最容易退化成一串粗體檔名 + 密集散文。開頭給檔案表 + 邊界圖，再逐檔講「為什麼是這個形狀」——[**Visual first**](#visual-first)。

### How to verify it

Commands you ran — checked if they passed, unchecked with why if not. Manual steps are a walkable path with expected before/after.

### Description for the changelog

One sentence, ship-note voice. Future readers / release notes.

## Risk / migration

Merge or deploy breaks without it → one `IMPORTANT` via scannable-pr. Compat notes live there or under implementation.
