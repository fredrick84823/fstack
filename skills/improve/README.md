# improve — Skill 自我進化工具

讓 skill 生態系在使用中自動學習、持續改善。

## Signal Flow

```
  ┌─────────────────────────────────────────────────────────────┐
  │  🔍 Signal Detection — 任何對話中（無需 opt-in）              │
  │                                                             │
  │  使用者說「不對」「少了 X」「漏掉了」→ Claude 偵測缺口        │
  │  在 response 末尾輸出：                                      │
  │  <<IMPROVE_SIGNAL skill="x" type="S2" gap="...">>           │
  └───────────────────────┬─────────────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          │                               │
          ▼                               ▼
  ┌───────────────────┐         ┌───────────────────────┐
  │  🖥️  Claude Code  │         │  ☁️  Cowork / Subagent │
  │                   │         │                       │
  │  Stop hook 自動   │         │  無 Stop hook         │
  │  觸發             │         │  Agent 直接用 Bash     │
  │  capture-         │         │  工具寫入              │
  │  signal.sh        │         │                       │
  └────────┬──────────┘         └──────────┬────────────┘
           │                               │
           └───────────────┬───────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   📄 signal-queue.md   │
              │                        │
              │  ## [timestamp] skill  │
              │  - type: S1/S2/S3      │
              │  - gap: 一句話描述     │
              │  - status: pending     │
              └────────────┬───────────┘
                           │
          ┌────────────────┴────────────────┐
          │                                 │
          ▼                                 ▼
  ┌──────────────────────┐       ┌────────────────────────┐
  │  🖥️  Claude Code      │       │  ☁️  Cowork             │
  │                      │       │                        │
  │  SessionStart hook   │       │  無 SessionStart hook  │
  │  check-signal-       │       │  Coordinator 手動觀察  │
  │  queue.sh            │       │  或人工輸入 /improve   │
  │  ↓                   │       │                        │
  │  ⚠️ 有 N 個 pending   │       │                        │
  │  signal，建議執行     │       │                        │
  │  /improve            │       │                        │
  └──────────┬───────────┘       └──────────┬─────────────┘
             │                              │
             └──────────────┬───────────────┘
                            │  使用者觸發 /improve
                            ▼
  ┌─────────────────────────────────────────────────┐
  │  🔄  /improve 7-Step Workflow                    │
  │                                                 │
  │  Step 0  Scope 偵測（user / project / repo）    │
  │  Step 1  讀取 signal-queue，取出 pending 項目   │
  │  Step 2  歸因分析，定位 SKILL.md 缺口段落       │
  │  Step 3  IF/THEN 規則萃取                       │
  │  Step 4  建立候選版本（working memory only）    │
  │  Step 5  skill-creator eval（無 evals 則跳過）  │
  │  Step 6  ⚠️ Human Gate                         │
  │          [A] Approve → Step 7                   │
  │          [R] Reject  → 結束                     │
  │          [M] Modify  → 回 Step 3                │
  │  Step 7  寫入 SKILL.md + 更新 queue + changelog │
  └─────────────────────────────────────────────────┘

  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
  🚀  /improve init — 一次性批量初始化（獨立流程）

  使用者輸入 /improve init
       │
       ▼
  列出 ~/.claude/skills/ 所有 skill
       │
       ▼
  詢問：要為哪些 skill 加入 Signal Collection 區塊？
       │
       ▼  （對每個選定 skill）
  Spawn subagent 分析 SKILL.md
  → 提案 2-4 個 IF-condition + S1/S2/S3 類型
       │
       ▼
  ⚠️ Human Gate [A] Approve / [S] Skip / [M] Modify
       │
       ▼  （Approve 時）
  Append Signal Collection 區塊到 SKILL.md
  （此區塊同時作為 skill-creator eval 驗證指標）
  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
```

## Signal 類型

| 類型 | 觸發情境 |
|------|---------|
| **S1** | 下游 skill 發現上游 skill 的產出格式不符 |
| **S2** | 使用者修正、抱怨、說「少了什麼」 |
| **S3** | Agent 執行 skill 時傳錯參數或遺漏步驟 |

## 使用方式

### 自動捕捉（無需操作）

當使用者在任何對話中表達不滿或指出缺口，Claude 自動在 response 末尾輸出標記：

```
<<IMPROVE_SIGNAL skill="skill-name" type="S2" gap="gap description">>
```

Stop hook (`capture-signal.sh`) 捕捉後寫入 `signal-queue.md`，下次 session 啟動時
`check-signal-queue.sh` 自動提示。

### 手動觸發

```
/improve                        # 讀取 signal-queue 或互動模式
/improve TARGET_SKILL=gsheet-progress-sync   # 指定目標 skill
/improve SCOPE=repo             # 指定 scope（user / project / repo）
```

### 批量初始化 Signal Collection

```
/improve init
```

互動流程：選擇 skill → subagent 分析 → 展示 proposal → 人工確認 → 寫入 SKILL.md。

## Signal Collection 區塊（可選強化）

若 skill 的 SKILL.md 末尾有 Signal Collection 區塊，偵測條件更精確，並同時作為
`skill-creator eval` 的驗證指標。無此區塊時，Universal Signal Detection 仍正常運作。

範本見 `references/signal-collection-protocol.md`。

## Cowork 環境

Cowork 中沒有 Stop hook，偵測到 gap 時直接用 Bash 工具寫入：

```bash
ts=$(date -Iseconds)
queue="$HOME/.claude/skills/improve/signal-queue.md"
printf '\n## [%s] %s\n\n- **type**: %s\n- **source**: cowork auto-detected\n- **gap**: %s\n- **status**: pending\n' \
  "$ts" "skill-name" "S2" "gap description" >> "$queue"
```

## Hooks 安裝

安裝 `tagtoo-skills` 時選擇 `improve`，安裝腳本會詢問是否啟用三個 hooks：

| Hook | 腳本 | 作用 |
|------|------|------|
| Stop | `capture-signal.sh` | 從 response 捕捉 `<<IMPROVE_SIGNAL>>` → signal-queue |
| Stop | `capture-skill-candidate.sh` | 從 response 捕捉 `<<SKILL_CANDIDATE>>` → candidate-queue |
| SessionStart | `check-signal-queue.sh` | session 啟動時若有 pending signal 即提示 |

## 檔案結構

```
improve/
├── SKILL.md                          # 主 skill 指令
├── signal-queue.md                   # 待處理 signal 佇列
├── candidate-queue.md                # 待審 skill 候選佇列
├── changelog.md                      # 改寫歷史（只 append）
├── scripts/
│   ├── capture-signal.sh             # Stop hook: signal 捕捉
│   ├── capture-skill-candidate.sh    # Stop hook: candidate 捕捉
│   ├── check-signal-queue.sh         # SessionStart hook: 提示
│   ├── resolve_scope.sh              # Scope 自動偵測
│   ├── list_candidate_downstream.sh  # 動態推斷下游 skill
│   └── propose.sh                    # 手動提交 candidate（Codex CLI 用）
└── references/
    ├── signal-collection-protocol.md # Signal Collection 區塊範本
    ├── scope-resolution.md           # Scope 解析說明
    └── skill-candidate-protocol.md   # Skill candidate 協議說明
```
