---
name: describe-pr
description: >
  Describe a pull request for a reviewer. Use when writing or rewriting
  a PR body, running /describe-pr, or when another skill needs a
  reviewer-facing account of a change.
---

# Describe PR

Reviewer *digests* **problem → observable change → how → proof** without opening the diff.

The reader is a **cold reader**: a teammate who has never opened this corner of the repo and sees only this body. [**Cold reader**](#cold-reader) sets how every name gets introduced.

Repo has `.github/PULL_REQUEST_TEMPLATE.md`? Fill that, plus `Merge danger`. Else the six questions below, skeleton in [`reference/template.md`](reference/template.md). Section rules apply either way.

Presentation (fold, alerts, details, ship markdown): load the [`scannable-pr`](../scannable-pr/SKILL.md) skill **after the body exists**：start at **Pack bulk**. Keep these headings.

## Title & headings

Title: **繁體中文**. Every `##` / `###` heading and every `<summary>` line: **English**. Prose, tables, bullets, checklists, code comments: 繁體中文.

The split is about who reads what. A title answers *what changed* to a teammate scrolling `gh pr list`：their own language reads fastest. Headings are structure, not content: they become anchor links (`#how-i-implemented-it`), they are what a reviewer greps across PRs, and they stay stable while the prose under them is rewritten. Keeping them English makes the skeleton comparable across every PR the team opens; the sentences inside carry the meaning.

Title: 一句話講可觀察的變化, ≤72 chars：`修正公開 NDJSON 外洩 user_email`, not `修好了` and not `更新 export.py`. Match the repo's existing title convention (check `gh pr list`); adopt a `fix(scope):` prefix only if the repo already uses one：the prefix stays English, the sentence after it does not.

## Steps

1. **Read**：full diff, commits, files the diff references but does not show. Split every hunk: *user-facing* vs internal.

   **Done when:** every file in the diff is accounted for; the *problem* is one sentence the diff actually solves.

2. **Frame**：answer each kept question from the change, not from session memory. Drop a question with nothing to say. Structural content → [**Visual first**](#visual-first).

   **Done when:** a reader who stops after the first two sentences of *problem* + *user-facing* knows whether to care; implementation cites `file:line`; *verify* is commands you ran or marked manual; multi-file roles, boundaries and forked consequences are tables or diagrams：and a diff with no structure has no diagram; every repo-internal name is glossed at first mention ([**Cold reader**](#cold-reader)).

3. **Present**：load scannable-pr at Pack bulk. Ship `gh pr create --assignee @me` / `gh pr edit --body-file` markdown. Assignee 一律是自己：GitHub Project 的 auto-import workflow 靠 assignee 把 PR 拉進看板，漏了就不會出現（PreToolUse hook `pr-assignee-guard.sh` 會擋沒帶 assignee 的 `pr create`）。

   **Done when:** paste-ready body; title is 繁中, headings and `<summary>` lines are English; linked issues use `Fixes`/`Closes`/`Resolves` when merge should close them; `Merge danger` 有 Door 與 Blast radius 兩行；`pr create` 指令帶 `--assignee @me`。

Section's shape unclear：alternative table, boundary table, ship-fact, cost-of-choice, three-way deviation split? [`reference/examples.md`](reference/examples.md) quotes a real PR for each.

## Cold reader

第一次提到 repo 內的檔案、路徑、票號、ADR、內部術語時，用一句白話說它**是什麼**、**在這次改動裡扮演什麼角色**；名字相近的放在一起對照區分。之後再提就只用名字。

| | |
|---|---|
| Before | 這個 repo 從「每台 server 各自部署」收斂到共用 CI/CD（`deploy.yml` + 各台 `deploy.yaml`） |
| After | 以前每台 server 用自己的指令部署；現在統一由一支共用程式照每台的設定單部署：`.github/workflows/deploy.yml` 是全 repo 唯一一份部署 workflow，決定**何時**部署（merge 進 main → staging、發 Release → production）；`servers/<server>/deploy.yaml` 是每台自己的設定單，寫**部署到哪**（GCP project、Cloud Run 服務名） |

票號同理：`#206` → `#206（部署環境分離與 CI/CD 選型）`。

## Visual first

Structural content：多檔案各自的角色、邊界、分岔的後果、方案比較、前後數字：預設畫成表或圖，散文只留給「為什麼是這個形狀」。但**多數 PR 不需要任何圖**：小改動的正確形狀就是幾行散文加一張表。

挑**最便宜、還講得完**的那一階：行內一句 → 表 → `diff` 草圖 → mermaid。往上跳一階就多付 reviewer 一次視線跳躍。

| 內容形狀 | 用 |
|---|---|
| 前後數字、方案比較、不修的理由 | 表 |
| 多個檔案各自的角色 | 表：檔案 / 規模 / 角色 |
| 目錄或檔案佈局變了 | `diff` 檔案樹 |
| 呼叫鏈多了或少了一層 | `diff` call tree |
| 分支、狀態、快取條件換了 | `diff` pseudocode |
| 整塊都是新的，reviewer 需要可複製的目標形狀 | 整段 code |
| 同一個起點分岔成兩種後果（選 A 會怎樣、選 B 會怎樣） | `flowchart` |
| 多條路徑撞同一個失敗，或幾個元件互相守護 | `flowchart` |
| 誰在改動邊界內 / 外 | `flowchart` + `subgraph` |
| 呼叫往返、誰先誰後 | `sequenceDiagram` |

### 草圖：把改動疊在既有形狀上

既有形狀寫三到五行，只讓動到的那幾行帶 `+` / `-`。reviewer 一眼看到「原本長這樣、現在多這一層」，比 mermaid 便宜一個數量級，也比「新增了 `expandSkillMention`」這句散文精確：

```diff
 submitForm
   createSession
     persistPrompt
+    expandSkillMention
     launchAgent
```

改動落在哪一層就用哪一種：佈局用檔案樹、順序用 call tree、條件用 pseudocode。不是貼 patch：行號、完整路徑、沒動到的分支都不放，那些 reviewer 在 diff 裡看。

### 什麼時候不要畫

圖的成本是 reviewer 的一次視線跳躍，很多內容付不起：

- **線性鏈不畫。** `A → B → C` 沒有分岔也沒有匯流，一句話就講完了：真要保留節奏就寫成一行 `無上界 → 解析到 2.x → fastmcp 消失 → import 失敗`。幾乎每個 bugfix 都有一條因果鏈，那不是畫圖的理由。
- **只改一個常數、一個版本號、一個過濾條件 → 不會有圖。** 這種 PR 的正確形狀是三行散文加一張前後對照表。
- **不畫既有系統的運作流程。** 圖只呈現「這次改動造成的結構」。為了說明「單價 6.25 改成 7.1875」而畫一張成本閘門怎麼運作的圖，是把 reviewer 的注意力帶離 diff。
- **散文兩句話講得完 → 那兩句話就是答案。**

刪圖測試比「寫不寫得出結論」可靠：**把圖拿掉，這段還讀得懂嗎？** 讀得懂就刪掉。讀不懂，再問一次「換成 `diff` 草圖或一張表夠不夠？」：夠就降級，mermaid 留給真有分岔或邊界的那幾張。

### 畫 mermaid 的時候

- **一張圖只回答一個問題。** 邊的語意混了（驅動 / 守護 / 指向）就是兩張圖。
- **節點標籤是短句**；清單、數字、檔名全展開放圖後。
- **圖後 1–2 條洞察，不是圖說。** 圖給機制，洞察給結論。
- **先畫邊界。** 哪些檔案在新目錄外 = 回歸風險在哪，reviewer 第一個想知道的事。
- **只畫有來源證據的層。** 沒有 runtime 的 PR 不畫部署圖；層級不足就省略，不為了完整補節點。
- 圖 + 表仍塞不下 → `<details>`，實測數字放裡面，圖留在外面。

Mermaid 語法與 fold 機制歸 [`scannable-pr`](../scannable-pr/SKILL.md)；這裡只決定「畫什麼、畫幾張」。

## Questions

### What problem(s) was I solving?

The gap as it existed *before* this PR：a failure mode the reviewer recognizes. **Lead with the conclusion:** sentence one is the motive (what broke), sentence two its consequence (who pays, how). Background, examples and [cold-reader](#cold-reader) gloss tables follow to back them. Cause and intro PR if known. Stop before the fix.

| | 開頭兩句 |
|---|---|
| Before（#393） | 以前每台 server 各自用自己的指令部署；現在統一由一支共用部署程式…（接著對照表、環境三層、五個例子，最後才是動機） |
| After | code 換了形狀，文件沒跟上。新增或修改 server 時，人和 agent 都會被帶去錯的路徑。 |

### What user-facing changes did I ship?

What a user or caller can observe. Bold lead-in + one sentence. `No user-facing changes.` is a complete answer.

### How I implemented it

Internals for the person opening the diff. Group by component：分組若用 `###`，那也是 heading，一樣是 English（`Test harness`, not `兩套 harness`）；不想翻就用粗體 lead-in，那是 prose，繁中。`file:line`. Shape and why that shape. Name the non-goal when the diff could be misread as including it.

這節最容易退化成一串粗體檔名 + 密集散文。開頭給檔案表 + 邊界圖，再逐檔講「為什麼是這個形狀」：[**Visual first**](#visual-first)。

### How to verify it

Commands you ran：checked if they passed, unchecked with why if not. Manual steps are a walkable path with expected before/after.

### Description for the changelog

One sentence, ship-note voice. Future readers / release notes.

### Merge danger

**每個 PR 都寫，不可省略**；repo template 沒有這節就接在最後。兩行定調（`Door`、`Blast radius`），其餘選填；寫法見 [`reference/template.md`](reference/template.md) 的 `## Merge danger`。

**Door**：merge 之後走得回來嗎？

| | 判準 | 例 |
|---|---|---|
| two-way | `git revert` + 重新部署就完全回到原狀 | 重構、新增 flag 預設關、文件、純讀取的 query |
| one-way | revert code 也收不回已發生的事 | DB migration 刪欄位、刪資料／GCS 物件、對外 API 改契約、已寄出的通知、production 部署後客戶已看到、刪 secret／IAM |

一個 one-way 部分就整張是 one-way：寫出**哪一步**收不回，以及 merge 前怎麼降風險（先備份、expand–contract 分兩個 PR、feature flag）。

**Blast radius**：一個詞定級（`無`／`小`／`中`／`大`），一句話講**怎麼壞、壞到誰**，不是 caller 清單：

- 看 diff 以外：API response、DB column、wire format、跨 repo consumer、feature flag、排程、別的 service 讀同一份資料。
- 「影響不大」不是答案。查過無 → 寫查了什麼（`rg export_ndjson` 無其他 caller）。
- 碰到 shared contract 或 diff 小但不放心 → 先跑 [`blast-radius`](../blast-radius/SKILL.md) 的 Steps 2–5，把「它安全是因為 X」這一個事實的證明等級寫上，證不了就寫 unproven。

one-way，或 blast radius 是 `大` → 另用 scannable-pr 放一個 `IMPORTANT` 在 fold 之上（部署順序、migration 步驟、要誰先做什麼）。
