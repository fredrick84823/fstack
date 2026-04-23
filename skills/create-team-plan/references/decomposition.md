# Task Decomposition Guide

Lead 在 Decompose 階段讀這份文件，決定如何將 plan 拆成可平行的 task。

## 1. 拆解維度優先順序

拿到一份 plan 後，**依序嘗試以下維度**，用第一個能產出 ≥2 個互斥 task 的維度：

| 優先序 | 維度 | 適用情境 | 範例 |
|---|---|---|---|
| 1 | **Phase（plan 原有分段）** | plan 已按邏輯分好 phase，各 phase 碰不同檔案 | Phase 1 改 parser（含 test）、Phase 2 改 UI（含 test）、Phase 3 e2e 驗證 |
| 2 | **Layer / 系統層** | 同一 feature 但跨 frontend / backend / infra | 前端改 React component、後端改 API route、infra 改 Terraform |
| 3 | **功能模組** | 同一 phase 裡包含多個獨立子模組 | auth module + notification module + logging module |
| 4 | **工作類型** | implementation vs. research vs. verification 可拆開 | 一人實作、一人同步跑 regression test suite |

**若以上都切不出互斥 task** → 不拆，整份留給 lead 用 `/implement-plan` 序列執行。

## 2. 從 plan 萃取 write_scope

plan 通常不會直接列檔案路徑。用以下步驟推導：

1. **讀 plan 的 Changes / Phase 段落**，找出所有提到的：
   - 明確檔案路徑（`src/auth/handler.py`）
   - 模組名（「改 auth module」→ grep codebase 找對應目錄）
   - 動作描述（「新增 migration」→ 對應 `migrations/` 目錄）

2. **用 Glob/Grep 展開模糊描述**：
   ```
   plan 說「改 parser 相關」→ grep -r "parser" --files-with-matches → 得出具體路徑清單
   ```

3. **列出每個候選 task 的 write_scope 清單**，格式：
   ```
   Task A: [src/auth/, tests/unit/auth/, tests/integration/auth/]
   Task B: [src/api/, tests/unit/api/, tests/integration/api/]
   Task C: [src/shared/types.ts]  ← 跨切面，見 §4
   ```

4. **比對重疊**：任兩個 task 的 write_scope 有交集 → 進入 §3 判斷。

## 3. 部分重疊的處理

兩個 task 都碰同一個檔案，不代表一定不能平行。判斷流程：

```
同檔案？
├─ 不同函式 / 不同 section（可明確用行號劃界）
│   └─ ✅ 可平行，但 write_scope 寫到函式級別
│      e.g. write_scope: ["src/utils.py:parse_date()", "src/utils.py:format_output()"]
│      escalation_rule 加「若需改檔案頂層 import 或 class 定義，先通知 lead」
│
├─ 同函式但只是「讀」vs「改」
│   └─ ✅ 讀的那方不列入 write_scope，標為 read-only dependency
│
├─ 真的要改同一段邏輯
│   └─ ❌ 合併成同一個 task，或排成序列（先 A 完成，B 再開始）
│      用 TaskUpdate addBlockedBy 建立依賴
│
└─ 不確定
    └─ ❌ 預設合併。寧可少一個 teammate、不要冒 overwrite 風險。
```

## 4. 跨切面工作的歸屬

### 核心原則：每個 implementer 交出完整垂直切片

每個 implementer teammate 負責其功能的 **implementation + unit test + integration test**。
這是為了長時間運行的 harness 設計：teammate 自主完成、自主驗證，
lead 不在中間逐模組跑測試當 bottleneck。

只有 **e2e test（跨模組整合驗證）** 才集中處理 — 由專門的 `e2e-tester` teammate
在所有 implementer 完成後接棒。

### 測試金字塔的歸屬

| 測試層 | 歸屬 | 理由 |
|---|---|---|
| **Unit test** | 該模組的 implementer | 寫完 code 馬上寫 test，context 最熱、最高效 |
| **Integration test**（模組內） | 該模組的 implementer | 測自己模組對外部依賴的整合（mock 外部、real 本模組） |
| **e2e test**（跨模組） | `e2e-tester` teammate | 需要所有模組都到位才能跑，自然是最後一棒 |

### 其他跨切面類型

| 跨切面類型 | 歸屬策略 |
|---|---|
| **共用 types / interfaces** | 拆成獨立前置 task（`T-types`），其他 task 用 `addBlockedBy` 等它完成。若變動極小（加 1-2 個 field），併入最先需要它的 task。 |
| **Docs / README** | 歸 lead 在 Integrate 步驟統一更新。Teammate 的 task-completion 裡記「需更新文件」即可。 |
| **Config / Migration** | 歸擁有該 config 語意的 task。若多人都要改同一個 config（e.g. `pyproject.toml` 加 dependency），由 lead 收集需求後統一改。 |
| **Shared utilities** | 若只加新函式（不改既有）→ 可平行，各自加各自的。若改既有函式簽名 → 拆成前置 task。 |

**原則**：跨切面的東西寧可歸 lead 或前置 task，也不要讓兩個 teammate 搶。

## 5. 粒度拿捏

### 一個 task 太大的信號
- write_scope 超過 5 個檔案
- 預估會碰超過 3 個不相關的子系統
- objective 需要用「和」連接兩個動詞（「改 parser **和** 重構 validator」）

→ 拆成兩個 task。

### 一個 task 太小的信號
- 只改一個檔案的一行
- 拆開後 task brief 比實際工作還長

→ 合併回相鄰的 task 或留給 lead 順手做。

### 理想粒度
- 1 個 task = 1 個 teammate 能在 **1 個 context window 內完成** 的工作量
- 產出可獨立驗證（跑一個指令就能確認對不對）
- objective 用一句話說得清楚

## 6. Decompose 輸出格式

Step 3 完成後，產出以下結構寫入 team-plan 的 Tasks 區塊：

```
Decomposition Summary:
- 拆解維度：[phase / layer / module / work-type]
- 拆解理由：[一句話]

Tasks:
  T-types: 更新共用 types（若需要）
    owner_role: types-implementer（或併入最先需要的 implementer）
    write_scope: [src/shared/types.ts]
    depends_on: []
    model: sonnet

  T-auth: auth 模組 implementation + unit test + integration test
    owner_role: auth-implementer
    write_scope: [src/auth/, tests/unit/auth/, tests/integration/auth/]
    depends_on: [T-types]
    model: sonnet

  T-parser: parser 模組 implementation + unit test + integration test
    owner_role: parser-implementer
    write_scope: [src/parser/, tests/unit/parser/, tests/integration/parser/]
    depends_on: [T-types]
    model: sonnet

  T-e2e: 跨模組 e2e 驗證
    owner_role: e2e-tester
    write_scope: [tests/e2e/]
    depends_on: [T-auth, T-parser]
    model: sonnet

Lead 保留：
  - 整合、文件更新、使用者溝通、最終 accept/reject

不拆的理由（若有 phase 被合併回 lead）：
  - Phase X：write_scope 與 T-auth 重疊於 src/shared/utils.py
```

### 關鍵：每個 implementer 的 write_scope 含測試目錄

Implementer 交出的是**完整垂直切片**（code + unit + integration test 全綠）。
T-e2e 是最後一棒，只在所有 implementer 都 done 後才 unblock，
驗證「切片之間的黏合處」，不重複跑各模組已驗證的 unit/integration。
