---
name: grill-me
description: |
  把模糊的功能想法逼成具體的 PRD。一次問完所有關鍵問題，存成 md 檔讓使用者
  填答，迭代到對齊後產出 PRD draft，再交給 create-plan 寫詳細計畫。當使用者
  說「grill me」、「拷問」、「釐清需求」、「想做 X 但很模糊」、「幫我把想法
  變具體」、「pre-PRD」時觸發。**只做需求對齊，不寫程式、不寫 plan**。
allowed-tools: Read, Write, Edit, Bash
---

# Grill Me

把模糊的功能想法逼成具體的 PRD。批次提問、md 迭代，直到對齊後交給 `/create-plan`。

## Initial Response

收到 seed 後：
- 若 seed 超過 3 句話，先說「請把想法濃縮成 1–2 句，避免我順著你的方向走而失去拷問價值」
- 若 seed 提到具體檔案或 code，先讀取它以了解背景
- 決定 slug 與路徑後，立即寫入 Round 1 md，再提示使用者填答

## Process

### Step 1: Receive Seed

接受 1–2 句的模糊想法作為 seed。

若使用者一開始給長篇規格（>3 句），要求濃縮：

> 「這個描述很詳細，但 grill 的價值在於從零逼出破綻——請把想法縮成一句話，
> 讓我從最基本的角度開始問。」

### Step 2: Decide Slug & Path

從 seed 語意生成 slug（英文小寫、hyphen 分隔、≤4 個字）。

路徑判斷：
- 若 `thoughts/` 目錄存在：寫到 `thoughts/shared/grill/YYYY-MM-DD-<slug>.md`
- 否則：寫到 `grill/YYYY-MM-DD-<slug>.md`（在當前工作目錄下建立）

用 `date +%Y-%m-%d` 取得今天日期。

### Step 3: Write Round 1

套用 **md Template**，填入：
- seed 原文
- 5 核心問題（每次都問）
- 動態加題（依 seed 內容判斷是否加入）

寫入後在 chat 告知路徑：
> 「已建立 `<path>`，請在每題 `A:` 下方填入答案，填完後回到 chat 說「答完了」。」

### Step 4: Wait for Answers

等待使用者填答。不要在這個階段追問。

使用者填完後會說「答完了」或執行 `/grill-me review <md path>`。

### Step 5: Review & Decide

讀取 md 檔，逐題評估答案的「具體程度」：

**具體的判斷標準**：
- 有明確邊界（誰、哪些場景、哪些不在 scope）
- 有可量測的描述（數字、狀態、行為）
- 沒有「視情況」「看看再說」「之後再決定」這類模糊詞

**若 ≥1 題答案仍模糊**：
- 在 md 的 `## Round N Questions` 下追加新一輪問題（只問模糊的那幾題的 follow-up）
- 更新 frontmatter：`status: awaiting-answers`，`rounds: N`
- 在 chat 說「我在 md 追加了 Round N 問題，請繼續填答。」

**若全部答案夠具體**：
- 填寫 `## PRD Draft` 區塊（套用 PRD Draft Template）
- 更新 frontmatter：`status: ready-for-plan`
- 移至 Step 6

### Step 6: Handoff

PRD Draft 填好後，在 chat 說：

> 「PRD 已寫入 `<path>`，狀態為 `ready-for-plan`。
> 下一步：`/create-plan <path>`」

---

## 5 核心問題（每次都問）

以下 5 題每次 Round 1 都問，不可省略：

1. **誰會用 / 誰刻意不服務？** —— 使用者邊界
2. **失敗或降級時怎麼辦？** —— 錯誤處理與 fallback
3. **怎麼知道成功？怎麼知道失敗？** —— 量測指標（含領先 / 落後指標）
4. **為什麼不用現成方案？為什麼不直接不做？** —— 替代方案與機會成本
5. **明確 out of scope 是什麼？** —— v1 / v2 切點

---

## 動態加題判準

依 seed 內容決定是否追加以下問題（每條最多加 1 題）：

| seed 出現關鍵詞 | 追加問題 |
|---|---|
| 資料、DB、ETL、bigquery、表、欄位 | 資料來源、量級、是否需要回溯歷史？ |
| UI、頁面、介面、按鈕、表單 | edge case：空狀態、權限視圖、異常輸入分別怎麼處理？ |
| API、Cloud Run、外部服務、webhook | rate limit、認證方式、配額上限、retry 策略？ |
| 部署、上線、release、rollout | rollout 策略、回滾觸發條件、是否需要 feature flag？ |

若上述都不符合：不加題（最多 7 題總量：5 核心 + 2 動態）。

---

## md Template

每次建立新 grill md 時使用此格式：

```markdown
---
seed: "<原始 seed 文字>"
created: <YYYY-MM-DD>
status: awaiting-answers   # awaiting-answers | reviewing | ready-for-plan
rounds: 1
---

# Grill: <slug>

## Seed
<原始 seed，1–2 句>

## Round 1 Questions

### Q1: 誰會用 / 誰刻意不服務？
// FEEDBACK: 

### Q2: 失敗或降級時怎麼辦？
// FEEDBACK: 

### Q3: 怎麼知道成功？怎麼知道失敗？
// FEEDBACK: 

### Q4: 為什麼不用現成方案？為什麼不直接不做？
// FEEDBACK: 

### Q5: 明確 out of scope 是什麼？
// FEEDBACK: 

<!-- 動態加題（若有）放在這裡 -->

## PRD Draft
<!-- status = ready-for-plan 時填 -->

## Notes
<!-- 自由區，使用者可寫雜記 -->
```

---

## PRD Draft Template

當所有問題對齊後，填入 `## PRD Draft` 區塊（≤30 行）：

```markdown
## PRD Draft

### Problem
<2–3 句>

### Users
- In: <誰用>
- Out: <誰不服務>

### Success Metrics
- <指標 1>
- <指標 2>

### In Scope (v1)
- <項目 1>
- <項目 2>

### Out of Scope
- <項目>

### Open Risks
- <風險>

### Design Concept
<一段話描述這東西是什麼，作為 create-plan 的入口>
```

---

## 不要做的事

- **不寫程式碼** —— grill-me 只做需求對齊
- **不寫 implementation plan** —— 那是 `/create-plan` 的工作
- **不要一題一題問** —— 永遠 batch 問完再等使用者填答
- **不要把明確答案打回去重問** —— 答案夠具體就接受，不要為了「問得更精確」而反覆追問
- **不要 proactive trigger** —— 只在使用者主動呼叫時啟動
- **不要自動接 `/create-plan`** —— 讓使用者手動執行，不自動串接
- **不要整合 plan-ceo-review** —— 兩者完全獨立，不做任何形式的整合
