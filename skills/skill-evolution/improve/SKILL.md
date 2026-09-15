---
name: improve
description: >
  Capture reusable skill gaps after user corrections or complaints by emitting a
  GAP marker for signal-queue.md. Use for skill improvement, self-improvement,
  rule updates, or `improve init`.
disable-model-invocation: true
---

# Improve — Skill 自我進化工具

讓 skill 生態系持續進化。Skill 在使用中學習，在學習中改善。

**最終目標**：建立不需要人工主動觸發的自我進化迴圈——每次 skill 執行都是一次學習機會，系統在使用過程中自動累積知識並改寫自身規則。

## 參數

| 參數 | 必填 | 說明 |
|------|------|------|
| `TARGET_SKILL` | 否 | 要改寫的 skill 名稱（省略時由 Step 2 歸因決定） |
| `SIGNAL` | 否 | 信號來源路徑（report 檔、git diff、錯誤訊息），省略時讀 signal-queue.md 或互動模式 |
| `SCOPE` | 否 | `user` / `project` / `repo`（省略時自動偵測） |

## Scope 解析

執行時以 Bash 邏輯（或 `~/.agents/skills/improve/scripts/resolve_scope.sh`）自動偵測 scope：

```
IF cwd 底下有 skills/{TARGET_SKILL}/SKILL.md        → scope=repo
ELIF cwd 底下有 .agents/skills/{TARGET_SKILL}/       → scope=project
ELIF ~/.agents/skills/{TARGET_SKILL}/ 存在           → scope=user
ELSE                                                 → 互動詢問
```

各 scope 的寫入路徑：

| scope | SKILL.md 路徑 | signal queue |
|-------|--------------|--------------|
| user | `~/.agents/skills/{target}/SKILL.md` | `~/.agents/skills/improve/signal-queue.md` |
| project | `.agents/skills/{target}/SKILL.md` | `.agents/skills/improve/signal-queue.md`（無則 fallback user） |
| repo | `skills/{target}/SKILL.md` | `skills/improve/signal-queue.md` |

## Skill Evolution Memory

`signal-queue.md` 是人工可讀的待辦佇列，也是 **current lifecycle status 的唯一 source of truth**。`memory/` 保存 raw evidence、decision events 與可重建索引；不得把 JSONL 或 graph 的 `pending` 與 queue pending 取 union。Stop hook 捕捉 `<<GAP>>` 時，必須透過 `scripts/signal_state.py capture` 寫入 shared `signal_id`：

```
skills/improve/memory/
  signals.jsonl                 # raw events: correction, failure, suspected gap
  transitions.jsonl             # append-only lifecycle decisions
  skill-graph.json              # compact lookup index
  claims/{skill}.md             # consolidated recurring gap claims
  eval-cases/{skill}.json       # generated / approved eval cases
  versions/{skill}.jsonl        # skill version and outcome trace
```

最小 schema：

```json
{
  "signal_id": "sig_20260518_001",
  "target_skill": "improve",
  "affected_rule": "Universal Signal Detection",
  "gap_type": "false_positive",
  "expected_behavior": "do not emit GAP for one-off requirement correction",
  "actual_behavior": "emits GAP because user said '不對'",
  "evidence_count": 1,
  "status": "pending",
  "links": {
    "duplicates": [],
    "tested_by": [],
    "caused_false_positive": []
  }
}
```

上例的 `status` 代表 capture 當下的狀態，等同 `status_semantics=captured_at_ingest`，不是 current lifecycle status。舊 records 保持 immutable，不為了 resolved/rejected/deferred 而改寫；current status 只讀 queue，decision history append 到 `transitions.jsonl`，graph status 則是可由 queue 重建的 projection。

查詢時使用 `scripts/memory.sh lookup --memory-dir <dir> --target-skill <skill> [--affected-rule <rule>] [--gap-type <type>]`，先依 `target_skill`、`affected_rule`、`gap_type` 找 prior signals / claims / eval cases；不要直接手寫解析 JSONL，也不要用 lookup 結果取代 queue 的 actionable selection。

### Lifecycle Safety Contract

- 新 signal 一律用 `scripts/signal_state.py capture`：同一個 top-level process 持有 scope-local lock，先 atomic commit queue，再寫 raw memory 與 graph；memory 失敗時 queue 保留 `memory_sync=failed` 供 recovery。
- Approve 前以 `signal_state.py prepare --candidate-id <hash>` 記錄 deterministic apply intent。重試時若同一 intent 的 post-state 已存在，跳過重複 patch / test append / changelog append，再完成 transition。
- Approve、Reject、Deferred 都用 `signal_state.py transition`；禁止直接用文字編輯只改 queue status。
- `signal_state.py reconcile` 預設 dry-run，只處理指定 `signal_id`。Legacy entry 只能用 `(timestamp, target_skill, normalized gap)` 唯一精確匹配後 `adopt-legacy`；ambiguous/unmatched 時禁止猜測。
- `signal_state.py` 是唯一 lock owner；其 internal primitives 不重新取得 lock，避免 nested-lock deadlock。Queue rewrites、raw append、transition append、graph projection 都用 same-directory temp file + atomic rename。

反思整理時要讀 `memory/signals.jsonl`、推論舊 records 的缺失欄位、產生 `claims/{skill}.md`、`eval-cases/{skill}.json`，並輸出 prioritized `/improve` worklist，而不是把 raw hook capture 當成最終狀態。`scripts/consolidate-memory.sh` 只作為機械備援，不是語意去重與 eval 產生的主要流程。

## Signal 類型

| 類型 | 觸發情境 | 範例 |
|------|---------|------|
| **S1: 下游漏接** | Skill A 的產出讓 Skill B 發現缺口 | Skill B 執行後發現 Skill A 遺漏某分類 |
| **S2: 人工修正** | 使用者手動修正 skill 的產出或行為 | 使用者推翻了 skill 的判斷結果 |
| **S3: 執行偏差** | Agent 使用 skill 時傳錯參數、遺漏步驟、誤判分支 | agent 呼叫腳本時格式不符規格 |

## Signal Detection — 判準只有一份

**判準不在這裡。** accept / abstain 的完整規則住在
[`references/validate-gap-prompt.md`](references/validate-gap-prompt.md)，由 Layer 2
validator（`scripts/validate-gap.sh`）執行。這一節只說明 signal 怎麼進來，不複述規則。

規則曾經同時寫在這一節與 validator prompt 兩處，而分類真正發生時只有 prompt 那份在
context 裡 —— 這一節的 abstain 條件從來沒有被套用過。兩份就是遲早會分岔的兩份；
改判準請改 prompt，不要在這裡加回一份摘要。

判準的形狀（細節去讀 prompt）：

- **precision-first**：不確定一律 reject。accept 等於宣稱你指得出證明它的那句使用者原話。
- accept 必須同時有正確歸因、可重複的規則缺口、逐字的 `evidence_quote`、以及
  expected vs actual。
- 歸因是第一道閘門：缺口是真的但掛錯 skill，仍然是 reject（`misroute`）。
- 自動化流程（digest cron、排程、`claude -p` 子 agent）不得對 `improve` /
  `skill-memory-reflect` 自己提 signal。
- `===KNOWN_SIGNALS===` 裡已有的缺口，換句話說仍是 `duplicate`，以 `duplicate_of` 指回原 id。

**偵測發生在哪裡**：session 結束後、out-of-band、讀 transcript，不是每輪回應自報。
agent 的主 context 裡沒有任何 GAP 指令 —— 那正是 2026-07 讓訊號量失控的設計
（見 [#40](https://github.com/fredrick84823/fstack/issues/40)）。接線由 #44 負責；
在那之前，`<<GAP>>` 標記只由「收工」時的 `session-ender` 這條顯式路徑產生。

**標記格式（單行，放 response 末尾，不要放在 code block 內）：**

```
<<GAP skill-name: 一句話描述缺口>>
```

**若 skill 有 Signal Collection 區塊**：以該區塊的條件為準（比通用偵測更精確），Signal Collection 區塊同時作為 skill-creator eval 的驗證指標，不需 opt-in 才能接收 signal。

**⚠️ Cowork / Subagent 環境（無 Stop hook）**：標記無法被 hook 自動捕捉。偵測到 gap 時，直接用 Bash 工具寫入：

```bash
ts=$(date -Iseconds)
queue="$HOME/.agents/skills/improve/signal-queue.md"
~/.agents/skills/improve/scripts/signal_state.py capture \
  --queue "$queue" \
  --memory-dir "$(dirname "$queue")/memory" \
  --timestamp "$ts" \
  --target-skill "skill-name" \
  --type S2 \
  --source "cowork auto-detected" \
  --gap "gap description"
```

## improve init — 批量初始化 Signal Collection

使用者輸入 `/improve init` 或 `improve init` 時，執行以下流程：

1. 列出 user scope 下所有 skill（`~/.agents/skills/`）
2. 詢問使用者：「要為哪些 skill 加入 Signal Collection 區塊？」（可複選，或輸入 `all`）
3. 對每個選定的 skill，**spawn 獨立 subagent**：
   - 讀取該 skill 的完整 SKILL.md
   - 理解 skill 的目的、步驟、以及可能的失敗模式
   - 提出 2-4 個具體的 Signal Collection 條件（IF situation → THEN emit S1/S2/S3 signal）
   - 產出完整的 Signal Collection markdown 區塊，包含要 append 到 signal-queue.md 的格式範例
4. 逐一展示每個 skill 的 proposal（**不自動寫入**）：

```
## Signal Collection Proposal: {skill-name}

### 建議新增條件：
- IF {具體情境} → S2: {gap 描述}
- IF {具體情境} → S3: {gap 描述}

### 建議 Signal Collection 區塊：
[完整 markdown 內容]

[A] Approve 寫入  [R] Skip  [M] Modify
```

5. 收集所有確認的 skill，批量 append Signal Collection 區塊到各自的 SKILL.md

## Workflow

### Step 0: Scope 偵測

1. 若使用者提供了 `SCOPE=user/project/repo`，直接使用
2. 否則執行 `~/.agents/skills/improve/scripts/resolve_scope.sh` 自動推斷
3. 顯示偵測結果：`scope={value}, skill_path={path}, queue_path={path}`

### Step 0.5: Skill Evolution Memory Lookup

在正式進入 Step 2 歸因前：

1. 從 queue 選定 signal；若沒有 `signal_id`，先用 `signal_state.py adopt-legacy` 做唯一精確連結
2. 對該 `signal_id` 執行 `signal_state.py reconcile` dry-run，將 drift 納入 evidence，但不自動改狀態
3. 再查 `memory/skill-graph.json` 與 `memory/signals.jsonl`：

   - 是否已有相似 signal（`duplicates`）
   - 是否已有 rejected false positive（避免重複誤判）
   - 是否已有同一 `affected_rule` 的 prior candidate / version
   - 是否已有可重用的 A/B/C/D eval case
   - 是否有 downstream skill 被過去改寫影響

若查到相似歷史，Step 6 review 包必須展示：

```
related_signals: <signal ids>
prior_decisions: approved / rejected / superseded
reused_eval_cases: <eval case ids>
risk: regression / contradiction / false_positive
```

### Step 1: 收集信號 (Collect Signal)

依以下優先順序確定信號來源：

1. **指定 SIGNAL 路徑**：直接讀取指定檔案（report、diff、log）
2. **讀取 signal queue**：讀取 scope 對應的 `signal-queue.md`，取出所有 `status: pending` 項目；這是唯一 actionable set
3. **互動模式**：若無任何輸入，詢問使用者描述遇到的缺口

將每個缺口結構化為：
```
gap = {
  現象: <觀察到什麼>,
  預期行為: <skill 應該做什麼>,
  實際行為: <skill 實際做了什麼>,
  signal_type: <S1 / S2 / S3>,
  source_skill: <哪個 skill 觸發這個 gap>
}
```

同時讀取 Skill Evolution Memory lookup 結果，附加：

```
memory_evidence = {
  related_signals: <相似 signal id 列表>,
  prior_claims: <claims/{skill}.md 中相關 claim>,
  reusable_eval_cases: <eval-cases/{skill}.json 中可重用 cases>,
  risk: <regression / contradiction / false_positive / none>
}
```

若 queue 為空且無輸入，輸出「目前無待處理的缺口信號」並結束。

若有多個 pending 信號，優先處理 **S1 > S2 > S3**，每次只處理一個 skill 的改寫。

### Step 2: 歸因分析 (Root Cause Attribution)

對每個 gap：

1. 若已指定 `TARGET_SKILL` → 直接讀取目標 skill 的 SKILL.md
2. 否則 → 執行 `~/.agents/skills/improve/scripts/list_candidate_downstream.sh` 動態推斷候選，逐一讀取 SKILL.md
3. 定位缺口對應的具體段落（Step N、判斷規則、對照表的某行）

**動態下游推斷**（取代手動維護的 dependency map）：
- 在當前 scope 下 glob 所有 SKILL.md
- grep 它們的 body 是否提及 `{TARGET_SKILL}`（提及 = 潛在下游）
- 將命中列表納入 `downstream_impact` 欄位

**歸因輸出格式**：
```
target_skill: <skill 名稱>
section: <Step N / 表格名 / 判斷規則名>
root_cause: <為什麼這段規則會產生這個缺口>
downstream_impact: <動態推斷出的下游 skill，若無則填「無」>
```

⚠️ **Scope Guard（嚴格執行）**：
- `scope=user`：只能改 `~/.agents/skills/` 下的檔案
- `scope=project`：只能改 `.agents/skills/` 下的檔案
- `scope=repo`：只能改 `skills/` 下的檔案
- 禁止修改 CLAUDE.md、settings.json、或任何非 skill 檔案

### Step 3: 模式萃取 (Pattern Extraction)

將 gap 歸納為可操作規則，格式固定：

```
IF <condition> THEN <action>
```

例：
- `IF skill 預期回傳結構化資料但回傳自然語言 → THEN 加入輸出格式範本`
- `IF agent 呼叫腳本時 label 包含空格 → THEN 提醒 label 需用底線`
- `IF 參數含路徑且路徑有空格 → THEN 自動加引號`

每條規則同時識別：
- 需要改寫的 SKILL.md 段落（哪一個 Step、哪一個判斷分支）
- 需要同步新增或修改的測試案例（若該 skill 有 tests/）

### Step 4: 建立候選版本 (Build Candidate)

**Role**：Skill Generator session = 主 Claude session 本身（執行 `/improve` 的這個 session）。不要為 generator 另 spawn subagent；主 session 已累積 Step 1-3 的 signal、memory evidence、歸因與 IF/THEN context。

在 working memory 中（**不寫入正式檔案**）產出：
- 改寫後的完整段落內容
- 測試更新內容（若有）

清楚標記：
- 哪些是新增的規則（`[NEW]`），哪些是修改（`[MODIFIED]`）
- 若這是第 N 輪改寫（N > 1），標註上一輪 v_{N-1} 的 verifier diagnostic 與本輪 v_N 的修正點

禁止在此 session 內做 self-review；驗證交給 Step 4.5 的獨立 verifier。

### Step 4.5: Surrogate Verifier（協同演化驗證）⚡

**目的**：在 human gate 前，用獨立 verifier 自動合成測試、做 mental simulation，攔截可預期的失敗。

**Agent 拓撲**：
- Generator = 主 Claude session（你自己，承載 Step 4 改寫）
- Verifier = fresh subagent；優先使用 `skill-verifier`，若不存在則用 `general-purpose`

**資訊隔離規則**：Verifier 只能看到下列資料，不看 generator 的推理過程與完整對話：
- signal-queue.md 中的 gap 描述
- Skill Evolution Memory 中與該 skill/rule 相關的 distilled evidence
- target SKILL.md 改寫後完整段落（v_N）
- 該 skill 的 Signal Collection 區塊（若有）
- `references/eval-test-cases-design.md` 的 A/B/C/D 原型摘要

**Verifier 流程**：

1. 判定 eval 原型：
   - A Golden Reference：有客觀答案可比對
   - B Rubric + Scenario：產出主觀品質文件 / 報告 / scaffold
   - C State Transition：會改變外部狀態 / 送訊息 / 部署 / 寫入系統
   - D Adversarial / Counter-Example：任務是在找問題 / 診斷 / review / 判斷是否該標 GAP
2. 依原型合成 3-5 個測試案例：
   - A：golden answer + tolerance + wrong-but-plausible trap
   - B：Yes/No rubric + typical / boundary / error scenarios
   - C：pre-state / action / post-state + non-mutation assertion
   - D：recall case + clean precision case + false-positive trap case
3. 對候選 v_N 做 mental simulation：若測試案例觸發，新規則會怎麼處理？
4. 若失敗，產 structured diagnostic 並回 Step 4 產生下一版
5. 若通過，標記 `surrogate_pass` 並進 Step 5

**特別規則**：若 target 是 `/improve` 的 Universal Signal Detection，必須至少生成 1 個「不應標 GAP」的 precision clean case 和 1 個 false-positive trap case；只測 recall 不算通過。

**Diagnostic schema（必須回傳 YAML）**：

```yaml
verdict: fail | pass
eval_prototype:
  primary: A | B | C | D
  secondary: []
synthesized_cases:
  - id: D-precision-clean
    input: <具體情境>
    expected: <應該發生什麼，例如 no_gap>
    observed: <v_N 會怎麼處理>
    source_evidence: <memory signal id / claim id / synthetic>
root_cause: <為什麼 v_N 仍會觸發原 gap，pass 時填 none>
missed_cases:
  - case: <具體情境>
    why_fails: <一句話原因>
    failure_type: false_negative | false_positive | weak_rubric | state_leak | wrong_method
actionable_fix:
  - <Generator 下一輪該補什麼規則>
memory_updates:
  - <應新增 / supersede / link 的 signal、claim、eval case>
```

**Loop control**：
- 內部預算 M=5：verifier subagent 內部最多 refine 自己 5 次
- 外部預算 K=3：Step 4 ↔ Step 4.5 來回最多 3 次
- 達上限仍 fail：不 rollback，帶最後 v_N 進 Step 6；review 包標記 `verifier_status: budget_exhausted`

### Step 5: skill-creator Eval（Eval on Candidate）⚡

**目的**：在人工審核前先驗證改寫品質，讓 human review 拿到的是「改寫 + 驗證結果」的完整包。

**若 target skill 有 eval set**（目標 skill 目錄下有 `evals/evals.json`）：
1. 觸發 `/skill-creator` 對候選版本跑 eval
2. 收集：
   - Trigger precision score（描述改寫後的觸發精度）
   - Output quality pass_rate + delta（改寫前後對比）
3. 判定：
   - `trigger_score >= 0.8` AND `pass_rate delta >= 0` → ✅ 品質通過
   - `trigger_score < 0.8` → ⛔ 觸發精度退化，回 Step 3 調整 description
   - `pass_rate delta < 0` → ⛔ 產出品質退化，回 Step 3 調整規則

**若 target 是 GAP 偵測 / Universal Signal Detection**：
- 必跑 D 型 precision guard：recall=1、precision clean=1、false-positive trap=1
- precision clean 或 trap 任一失敗時，不得升級到 user-level `CLAUDE.md` 或 hook-level 強指示
- 若現有 eval set 缺 D 型 cases，使用 Step 4.5 合成 cases 補進 Step 6 review 包，標記 `recommended_eval_cases`

**若無 eval set**：
- 標記 `eval_status: skipped（無 eval set）`
- 不能只標 skipped；必須把 Step 4.5 合成的 A/B/C/D cases 放進 Step 6 review 包，作為「建議新增 eval set」給 human gate 審核

### Step 6: Human Review Gate ⚠️ STOP — 等待人工審核

一次展示完整包（diff + eval 結果同時呈現）：

```
## Skill Improvement Proposal

**Target**: {target_skill} — {section}
**Signal**: {S1/S2/S3} — {來源}
**Scope**: {scope} → {skill_path}

### 改寫規則
IF {condition}
THEN {action}

### Diff Preview

**改寫前：**
{原始段落完整引用}

**改寫後：**
{新段落（含新規則，[NEW]/[MODIFIED] 標記）}

### Eval 結果
| 維度 | 結果 |
|------|------|
| Eval prototype | {A/B/C/D primary}（secondary: {optional}） |
| Surrogate verifier rounds | {N} / 3（攔截 {x} 個問題） |
| Synthesized eval cases | {case_count}（包含 {precision_count} 個 precision/trap cases） |
| Trigger precision | {score} {✅/⛔/⏭️} |
| Output quality | {pass_rate} (delta: {+/-}) {✅/⛔/⏭️} |
| 演化軌跡 | v1 → v2 → ... → v_N |
| 狀態 | ✅ 通過 / ⛔ 退化 / ⚠️ budget exhausted / ⏭️ 跳過（無 eval set） |

### Verifier 攔截報告（節選）
- v1 問題：{verifier diagnostic 1}
- v2 修正：{generator response}

### False Positive Guard（若 target 是 GAP 偵測）
- clean case: {no_gap case} → {pass/fail}
- trap case: {looks_like_gap_but_not_skill_issue} → {pass/fail}

### Memory Evidence
- related_signals: {ids}
- prior_decisions: approved / rejected / superseded
- reused_eval_cases: {ids}
- risk: regression / contradiction / false_positive / none

### 影響範圍
- 直接改寫：{target_skill}/{section}
- 下游可能受影響：{動態推斷的下游 skill，若無則填「無」}

---
**請選擇**：[A] Approve  [R] Reject  [M] Modify（提供修改意見後回 Step 3）
```

處理結果：
- `A (Approve)` → 進入 Step 7
- `R (Reject)` → 呼叫 `signal_state.py transition --to rejected`，同步 queue authority、transition log 與 graph projection後結束
- `D (Defer)` → 呼叫 `signal_state.py transition --to deferred`，不得直接手改 queue
- `M (Modify)` → 使用者提供修改意見，回 Step 3 重新萃取規則

### Step 7: 寫入 + Changelog (Apply & Log)

1. **建立 apply intent**：以 `signal_id + normalized candidate diff` 計算 deterministic `candidate_id`，呼叫 `signal_state.py prepare`。若 retry 發現相同 intent，先驗證 post-state，已存在的 skill/test/changelog 變更不得重複 append
2. **寫入正式 SKILL.md**：用 Edit 工具 idempotently 修改對應段落（路徑由 Step 0 的 scope 決定）
3. **更新並執行測試**（若有變動）；失敗時 queue 保持 pending + prepared，不得 transition resolved
4. **Append changelog.md once**：以 `signal_id + candidate_id` 作唯一鍵，已存在則跳過
5. **Transition + verify**：呼叫 `signal_state.py transition --to resolved --candidate-id <id>`，再執行同 signal 的 reconcile dry-run；只有 queue、raw evidence presence、transition event、graph projection 與 `memory_sync=synced` 全部收斂才宣告完成
6. **Append changelog.md 內容**：

```markdown
## {YYYY-MM-DD} — {target_skill} / {section}

- **Signal**: {S1/S2/S3} — {來源描述}
- **Gap**: {現象一句話描述}
- **Rule**: `IF {condition} THEN {action}`
- **Evolution**:
  - surrogate_rounds: {N}
  - oracle_rounds: {K}
  - final_version: v{N}
  - verifier_caught: {問題類型列表}
- **Eval cases**:
  - prototype: {A/B/C/D}
  - added_cases: recall={N}, precision={N}, trap={N}
- **Memory links**:
  - related_signals: {ids}
  - tested_by: {eval case ids}
- **Eval**: trigger={score}, quality={pass_rate} (delta: {delta})
- **Decision**: approved by human
```

5. **提示使用者考慮 commit**：
   ```
   建議 commit message：[skill] improve {target_skill}：{改寫規則一句話摘要}
   ```

6. **若 scope=repo**（在 skills 源碼 repo 內），額外輸出 PR 提示：
   ```
   📦 Repo 模式：建議 PR 流程
     git checkout -b skill/improve-{target}-{yyyymmdd}
     git add skills/{target}/
     git commit -m "skill({target}): {rule 一句話}"
     gh pr create --title "improve({target}): ..." --body "改寫理由 + eval 結果"
   ```

## Signal Collection Protocol

Auto-trigger 機制：signal 產生時，skill **在當下輸出提示**，不依賴 Stop hook。

其他 skill 若要 opt-in，參考 `~/.agents/skills/improve/references/signal-collection-protocol.md` 在 SKILL.md 末尾加入 Signal Collection 區塊。

## Notes

- 每次只處理一個 skill 的改寫，避免批量改寫產生難以追蹤的影響
- Scope guard 嚴格：只改對應 scope 下的 skill 檔案，不例外
- changelog.md 只 append，永不修改歷史記錄
- Eval 失敗（⛔）時不進入 Step 6，直接回 Step 3；三次仍失敗則報告 blocker 並請人工介入
- 若 skill-creator plugin 未安裝，eval 步驟自動跳過並標記 skipped
- Skill Evolution Memory 只追蹤 skill/rule/signal/eval/version/outcome，不建立完整個人知識庫
- 定期整理 memory 時，使用 `scripts/consolidate-memory.sh --memory-dir <dir>` 合併 duplicates、標記 superseded claims、產出 high-priority candidate claims
- `signals.jsonl` 是 immutable capture evidence；任何 current pending 統計只能來自 `signal-queue.md`
