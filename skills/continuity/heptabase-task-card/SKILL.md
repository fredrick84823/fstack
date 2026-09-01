---
name: heptabase-task-card
description: |
  在 Heptabase 建立符合 Sprint whiteboard 標準格式的任務卡片。
  當使用者說「建立任務卡片」「新增 sprint card」「create task card」「加一張卡到 sprint」，
  或要把計畫拆解成子任務時立即觸發。
  支援批次建立多張卡片，並在每張卡片的 `## Depends on` section 標記依賴關係，
  讓 /start-day skill 可正確解析。
---

## 任務卡片格式

```markdown
# [type] 任務標題

---

## Task Context

- Goal: {一句話說明目標}
- Description:
  - What: {要做什麼，核心工作範圍}
  - Expected: {完成後的預期狀態或可驗證結果}

---

## Related Source

- {描述}: `{.md 文件路徑}`

---

## Note

- {補充說明，無則留空}

---

## Depends on

- {依賴的任務卡片完整標題}
- 或 nothing（此任務無前置依賴）
```

`type` 可選值：`feature` / `fix` / `debug` / `refactor` / `report` / `doc` / `test` / `archi` / `harness` / `research` / `auto`

---

## 各 section 填寫原則

**Goal**：一句話，說明「做完這個任務，達成什麼結果」。

**Description**：用結構化 bullet list 呈現，每個 label 一行：
- `What:` 要做什麼，核心工作範圍（一句話）
- `Expected:` 完成後的預期狀態或可驗證結果
- 其他 label 視需要加，例如 `Scope:` / `Constraint:` / `Output:`
不要列步驟清單或程式碼，細節留在計畫文件（.md）中。

**Related Source**：只放 `.md` 格式的文件。格式為 `{描述}: \`{路徑}\``，描述說明這份文件的用途，讓人一眼知道要去哪裡查什麼。不放程式碼檔案、JSON、YAML 等。

範例：
```markdown
## Related Source

- wave 1.5 儲存層外部化主計畫: `thoughts/shared/plans/2026-04-28-wave-1-5-storage-mvp.md`
- 22 個 client 遷移詳細邏輯: `thoughts/shared/plans/2026-04-28-clients-output-unification-migration.md`
```

**Note**：任何影響判斷但不屬於 Description 的補充，例如特殊邊界 case、已知限制、待確認事項。

**程式符號格式規則**：卡片任何欄位中，凡是含有技術符號的詞彙一律用 inline code（backtick）包住，包括但不限於：
- CLI flags / options：`--apply`、`--dry-run`
- 路徑分隔符相關：`output/`、`clients/{c}/{pid}/`、`_archive/`
- 特殊字元組合：`project.yaml`、`run_manifest.json`、`final_status`

**Depends on**：卡片完整標題（與依賴卡片的 H1 一致），解析時做 normalize（小寫 + 空白壓縮）後比對。

---

## `## Depends on` 格式規範

此 section 由 `/start-day` skill 的 `fetch_heptabase.py` 自動解析。每行一個依賴，內容為依賴卡片的完整標題。

**正確格式：**
```markdown
## Depends on

- [wave-1.5/P0] GCS 前置設定
- [wave-1.5/G2] path_utils 重寫 + orchestrator 路徑切換
```

**無依賴時：**
```markdown
## Depends on

- nothing
```

只列**直接**前置依賴，不列間接依賴（避免依賴鏈冗餘）。

---

## 識別符命名慣例

批次建立時在標題加識別符，讓依賴關係清晰可讀：

| 格式 | 範例標題 |
|------|----------|
| `[project/PhaseStep]` | `[wave-1.5/G1] clients+output 目錄遷移` |
| `[project/TaskCode]` | `[wave-1.5/I0+I1] validator 根因分析與修正` |

---

## 建立後的提醒

每次建立完畢，告知使用者：

> ✅ 已建立 N 張卡片：
> - [card 1 title]
> - ...
>
> ⚠️ 卡片已建立在 main space，請在 Sprint whiteboard 將它們拖入 `{週號}` section。
> 可用 Heptabase Search 搜尋卡片標題快速定位。
