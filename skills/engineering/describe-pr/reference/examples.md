# Examples

Load when a section's shape is unclear. Quote here is the move, not the model to copy wholesale.

Four real PRs, anonymised. Quoted markdown is the *move*, not a template to copy.

| PR | Shows |
|---|---|
| **A** — cost-observability service | alternative table, baseline, payload-as-contract, tests named to AC |
| **B** — log sink into a partitioned table | ship-fact, decisions not file-tour, honest unverifiable |
| **C** — public export behind a PII boundary | boundary table, cost-of-choice, three-way deviations, curl-without-creds |
| **D** — new server skeleton wired to measurement tooling | visual-first implementation section: file map, boundary diagram, causal chains |

---

## What problems was I solving

### Alternative the change beats

PR A does not open with the new log line. It opens with why the incumbent cannot do the job. Each row is limitation → consequence → does this PR fix it.

```markdown
| # | `INFORMATION_SCHEMA.JOBS_BY_PROJECT` 的限制 | 後果 | 服務自報有沒有解 |
|---|---|---|---|
| 1 | 被成本閘門擋下的查詢**不產生 BigQuery job** | 「有人一直在撞上限」完全沒有紀錄 | ✅ `status="blocked"` |
| 7 | 180 天保留上限 | 做不了年度趨勢 | ⚠️ 部分 — 要靠 its parent issue |
| — | reservation 計價時 `total_bytes_billed` 換算是虛的 | 金額失真 | ❌ 兩邊誰也解不了 |
```

Then one sentence that states the leftover role of the incumbent (`INFORMATION_SCHEMA` remains the reconciliation source). The table is the argument; the prose only names what the table does not.

Use when the PR is a design choice against a known alternative. Skip when there is no incumbent.

### Boundary the change must hold

PR C is the public layer of a three-layer PII split. The problem is the constraint, shown as a table, not a paragraph of "we must not leak email":

```markdown
| 層 | 可含 |
|---|---|
| BQ 逐筆表（不公開） | `user_email` + Google `user_sub` + `job_id` |
| 聚合 view | — |
| **公開 NDJSON** | **只有 `user_hash` hash** |
```

Use when the PR exists to keep a boundary, not just to add a capability.

### Ship-fact

End on a checkable fact, not a hope.

- PR B: run a query → within minutes that row is in `run_googleapis_com_stderr`, including blocked queries (`blocked` is true).
- PR A: exactly one line per path; rates frozen on the line; `user_hash` joins back to job labels.
- PR C: `curl` with no credentials returns the file; no identity fields; `generated_at` distinguishes "nobody used it" from "the pipeline is dead".

### Baseline

PR A measures the gap on the live project before claiming it: HTTP logs vs `INFORMATION_SCHEMA` jobs, then a three-line conclusion (no real users those days; today's traffic is probes; the two sources only meet via labels). The blind spot is no longer a hypothesis.

Use when a reviewer could read the gap as speculative.

---

## What user-facing changes did I ship

PR A: no tool/return-shape change. The stderr JSON *is* the contract (downstream sink infers BQ schema from it), so the payload is shown once, in full. File links stay one line each.

PR B / PR C: file + one clause of what that file now owns, then an explicit non-goal (no new Cloud Run, Scheduler, image, or SA). PR C's observable artifact is the public URL, not the Terraform.

---

## How I implemented it

### Decisions, then shape

PR B draws the three Terraform resources as a tree, then isolates three decisions (`use_partitioned_tables` is not optional; no table expiration; filter pinned to `jsonPayload.event="bq_query"`). The rest of the file tour is omitted.

PR C is the same move across three layers (view / bucket / `EXPORT DATA`). Each layer gets the decision that is not obvious (Taipei calendar day; `uniform_bucket_level_access`; transfer config deliberately has no `service_account_name`). The PII test reads those two SQL strings in `main.tf` — it pins the boundary, not Terraform.

PR A is one emitter, four call sites: why it lives on `BigQueryService`, why the body is `try/except Exception: pass`, why amounts are `float`, why `error_type` reads `__cause__`. The control-flow rewrite is a short snippet, not a walk through every line.

### Visual first

PR D 是反例改寫過的樣本。原版是五段「粗體檔名 + 密集散文」，reviewer 要自己在腦中組出這幾個檔怎麼串。改寫後開頭兩張圖各回答一個問題：

```markdown
**先看邊界 —— 這個 PR 動到誰的地盤？**

flowchart LR
  subgraph NEW["servers/<new-server>/ — 全新目錄"]
    MK["Makefile"]
    CF["conftest.py"]
    ...
  end
  MK -->|"make crap"| SH["scripts/crap.py<br/>gsheet / bq 也在用"]

- 六個檔案裡只有 `scripts/crap.py` 在新目錄外 —— **回歸風險只有這一處**。
- 那一處的證據：改動前後整份輸出逐字相同（見 verify）。
```

第二張只畫「誰守誰」（`make` → `test_harness.py` → `conftest.py`），不把第一張的邊界關係重畫一次。三段散文式的「為什麼」各自變成一張分岔圖：斷回傳值 vs 斷送出 kwargs、回 `MagicMock` vs `raise`、`export` vs inline 的 venv 外洩鏈。實測數字（192 pkgs / 253 pkgs）留在 `<details>`，圖上只寫「五個 sibling server 混進來」。

刻意不畫的：C1 / C2 層。<new-server> 當時是空 package、無 Dockerfile、無部署 —— 畫 container 圖就是憑空造節點。

Use when the implementation touches more than two files, or when any "why" is a causal chain.

### Cost of the choice

PR C prices the rejected alternatives (materialized view, Cloud Run Job) in a table, then names the real growth risk (public-bucket egress, not the view scan). Use when the implementation is a cheaper path that looks like a missing one.

---

## Deviations from the plan

PR C's three-way split is the shape. PR A / PR B are earlier versions of the same move.

| Bucket | What goes here |
|---|---|
| Done per the issue | AC that shipped |
| Added, not in the issue | extras + why they exist (`test_cost_export_pii.py` turns a manual AC into a test because a leaked public file cannot be un-leaked) |
| In the issue, not done | left unchecked, pointed at verify |

Use when an issue or plan exists. Drop the heading when there is neither.

---

## How to verify it

Split what this branch can prove now from what needs apply/deploy.

- PR A: unit tests are the prove-now bar (`16 passed`); Cloud Run sightings stay unchecked manual.
- PR B: `terraform plan` (3 creates, nothing else) is prove-now; apply-after checks stay unchecked. An IMPORTANT states dataset/sink do not exist yet.
- PR C: `5 passed` + `terraform validate` are prove-now. A WARNING lists apply preconditions (globally unique bucket name, ADC BigQuery scope, sink table must already exist). The walkable path is `curl` with no credentials, then `jq` asserting identity fields are absent.
