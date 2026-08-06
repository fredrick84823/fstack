# Skill Inventory Review

Created: 2026-07-08

Purpose: 盤點目前 `/Users/fredrick/.agents/skills` 中的本機 skills，作為後續保留、停用或刪除討論用。

保留欄位建議填法：

- `keep`: 保留
- `maybe`: 先觀察或移到 quarantine
- `remove`: 可停用或刪除

## Summary

- Total local skills: 64
- From `fstack`: 24
- Local-only: 40

## Inventory

| Category | Skill | Source | 功能簡述 | 初步建議 | 保留? | 備註 |
|---|---|---|---|---|---|---|
| Browser / Automation | `agent-browser` | local | 自動操作網站、填表、點擊、截圖、抓頁面資料、測試 web app。 | maybe |  | 若主要用內建 browser/computer-use，可考慮停用。 |
| Code workflow | `ask-codebase-questions` | fstack | 在研究、設計、計畫前先產出 Questions artifact，整理 code-answerable 與 human questions。 | keep |  | fstack 新核心流程。 |
| Diagram | `beautiful-mermaid` | fstack | 用 beautiful-mermaid 套件渲染高品質 Mermaid 圖。 | keep |  | 常用於架構/流程圖輸出。 |
| Work / BigQuery | `bigquery-cost-control` | local | BigQuery 查詢前 dry run，估算成本並依 Data Team 政策警告或阻擋。 | keep |  | 工作安全 guardrail。 |
| Work / BigQuery | `bigquery-labeled-query` | local | BigQuery/ETL 查詢套用標準安全、label 與查詢規範。 | keep |  | 工作安全 guardrail。 |
| Thinking | `brainstorming` | fstack | 個人腦力激盪教練，用問題引導你產生自己的想法。 | keep |  | 明確 brainstorm 時使用。 |
| Work / GCP | `cf-verify` | local | Cloud Function unit/integration/e2e/deploy/logs 全流程驗證。 | keep |  | 工作驗證用。 |
| Git workflow | `clean-worktree` | local | 清理已合併 worktree，同步 output、移除暫存 raw files、刪 branch/worktree。 | keep |  | 若常用 worktree 建議保留。 |
| Thinking | `codex-brainstorm` | fstack | Claude 與 Codex 獨立研究後辯論，用於可行性、方案探索、完整枚舉。 | keep |  | 高成本但有用。 |
| Code review | `codex-cli-review` | fstack | 呼叫 Codex CLI 對未提交變更做獨立 code review。 | keep |  | 可作第二意見。 |
| Handoff | `create-handoff` | fstack | 建立 session handoff 文件，交接未完成工作與上下文。 | keep |  | 核心續工流程。 |
| Planning | `create-plan` | fstack | 透過研究與互動建立詳細 implementation plan，寫入合適 plans 位置。 | keep |  | 核心規劃流程。 |
| Planning | `create-team-plan` | fstack | 將標準 plan 拆成 team-plan、任務 brief、依賴圖與模型分工。 | keep |  | 只有複雜任務會用。 |
| Runtime sync | `cross-machine-runtime-sync` | local | 同步與驗證 work/home machine 的 runtime、skills、hooks、Personal Wiki。 | keep |  | 這次任務使用。 |
| Research | `deep-inquiry` | local | 多來源深度研究、來源交叉驗證、假設檢查與綜合。 | keep |  | 穩定版研究流程。 |
| Research | `deep-inquiry-v2` | local | 實驗版 local-first 深度研究，含 evidence matrix 與 durable artifacts。 | maybe |  | 若未常用可 quarantine。 |
| Design / Architecture | `deep-module` | fstack | 用 Deep Module 原則檢查介面、封裝與模組邊界。 | keep |  | 設計/實作/review 都有用。 |
| Code workflow | `design-concept` | fstack | 將 questions 與 research 轉成簡短設計概念，供人類對齊。 | keep |  | fstack 新核心流程。 |
| Personal reflection | `digest-agent` | local | 整理 Heptabase journal 成主題、決策、問題與 next actions。 | maybe |  | 若近期少做反思 digest 可停用。 |
| Diagram | `excalidraw-diagram` | local | 產生 Excalidraw JSON，用圖解工作流、架構或概念。 | maybe |  | 若 beautiful-mermaid 已足夠可停用。 |
| Skill evolution | `extract-skill` | fstack | 從 candidate queue 去重、合併、review，經批准後建立新 skill。 | keep |  | skill 自我演化流程。 |
| Skill discovery | `find-skills` | local | 幫忙尋找或安裝可用 skill。 | maybe |  | 若已很少安裝新 skill 可停用。 |
| Work / GCP | `gcp-debug` | local | 系統性調查 Cloud Function/Cloud Run 問題，查 logs、git/GitHub 線索。 | keep |  | 工作 debugging 用。 |
| Meeting | `generate-meeting-notes` | local | 從錄音、逐字稿或文字紀錄產生會議記錄，支援 Drive/Slack 輸出。 | keep |  | 若會議整理需求存在則保留。 |
| Work report | `generate-pm-weekly-doc` | local | 聚合一週 commits/handoffs，產生 PM 週會報告。 | keep |  | 週三 PM 流程用。 |
| Knowledge graph | `graphify` | local | 將輸入轉成 knowledge graph、社群分群、HTML/JSON/audit report。 | maybe |  | 情境型，若少用可停用。 |
| PRD | `grill-me` | fstack | 用一次性問題把模糊想法逼成 PRD draft，不寫程式不寫 plan。 | keep |  | 前置需求釐清。 |
| Work report | `gsheet-progress-sync` | local | 將工作進度、handoff 或 git work 同步到 Tagtoo Data Team 進度表。 | keep |  | 工作流程核心。 |
| Reasoning | `heavyskill` | local | 對高正確性需求問題做多軌推理與 sequential deliberation。 | maybe |  | 若很少做數學/競賽/嚴格推理可停用。 |
| Heptabase | `heptabase-task-card` | fstack | 在 Heptabase 建立符合 Sprint whiteboard 格式的任務卡與依賴。 | keep |  | start-day 相關。 |
| Implementation | `implement-plan` | fstack | 執行已批准 plan，依 phase 更新 checkbox，階段間停下驗證。 | keep |  | 核心實作流程。 |
| Implementation | `implement-team-plan` | fstack | 執行 team-plan，使用 agent teams 分派任務並產出 walkthrough。 | keep |  | 複雜任務用。 |
| Skill evolution | `improve` | fstack | 捕捉 skill gap signal、維護 signal queue、提出 skill 規則改進。 | keep |  | 核心自我演化。 |
| Career | `job-application-optimizer` | local | 依職缺客製履歷、cover letter、面試問題。 | maybe |  | 求職期保留，否則可停用。 |
| Personal wiki | `personal-llm-wiki` | local | Personal LLM Wiki router，依需求轉到 query/inject/lint 等子 skill。 | keep |  | 個人知識系統入口。 |
| Personal wiki | `personal-wiki-inject` | local | 將已審核 synthesis/source 注入 Personal LLM Wiki。 | keep |  | wiki 寫入流程。 |
| Personal wiki | `personal-wiki-lint` | local | 檢查 Personal LLM Wiki 結構、引用、隱私、source queue 與 discoverability。 | keep |  | wiki 健康檢查。 |
| Personal wiki | `personal-wiki-mine` | fstack | 從 bounded thoughts/ 與 Heptabase sources 挖 mechanism-first candidate claims。 | keep |  | 知識萃取流程。 |
| Personal wiki | `personal-wiki-query` | local | 唯讀查詢 Personal LLM Wiki，回答 compiled knowledge 與 project routing 問題。 | keep |  | wiki 查詢入口。 |
| Plugin | `plugin-creator` | local | 建立 Claude Code plugin 結構、manifest 與 marketplace integration。 | maybe |  | 若 fstack/plugin 工作不常做可停用。 |
| Product | `product-lens` | local | 用 PM/product lens 做開發前產品判斷 gate。 | maybe |  | 只有明確 invoke 才用。 |
| Career wiki | `repos-wiki-ingest` | local | 從本機 repo 更新 career repos-wiki project page。 | keep |  | 履歷素材庫用。 |
| Career wiki | `repos-wiki-lint` | local | 檢查 career repos-wiki schema、連結、量化與 index 健康。 | keep |  | 履歷素材庫用。 |
| Career wiki | `repos-wiki-query` | local | 依職缺從 career repos-wiki 選 project evidence。 | keep |  | 求職期尤其重要。 |
| Planning | `research-and-plan` | fstack | 小型任務直接 codebase research + concise plan，一步產出可實作計畫。 | keep |  | 輕量替代完整流程。 |
| Writing | `research-article` | local | 研究 5-10 位專家觀點後，以你的第一人稱寫繁中觀點文章並存 Heptabase。 | maybe |  | 若近期少寫文章可停用。 |
| Research | `research-codebase` | fstack | 透過 subagents 盤點 codebase 現況、架構與既有決策。 | keep |  | 核心研究流程。 |
| Handoff | `resume-handoff` | fstack | 從 handoff 文件恢復工作，先驗證當前 repo 狀態再續工。 | keep |  | 核心續工流程。 |
| Research digest | `rss-research-digest` | local | 匯入 RSS/YouTube RSS，產生來源標註 digest 與 email/local archives。 | maybe |  | 若沒有固定 digest 流程可停用。 |
| Personal reflection | `self-observer` | local | 從 Heptabase/journal/memory 做長期模式與風險觀察。 | maybe |  | 偏個人反思，視使用頻率。 |
| Skill evolution | `skill-memory-reflect` | fstack | 整理 improve memory，生成 claims、eval cases、worklists。 | keep |  | skill 自我演化流程。 |
| Slack | `slack-canvas` | local | 建立或更新 Slack Canvas，用於報告、會議記錄、技術說明。 | keep |  | 工作溝通用。 |
| Slack | `slack-message` | local | 草擬或發送 Slack 訊息，確保格式正確渲染。 | keep |  | 工作溝通用。 |
| Daily workflow | `start-day` | fstack | 整合 GSheet/GitHub/Heptabase 任務狀態，建立每日任務看板。 | keep |  | 日常啟動流程。 |
| Daily workflow | `start-standup` | local | 互動式 daily stand-up，整理近期專案狀態、阻塞與今日 focus。 | keep |  | 與 start-day 可互補。 |
| Git workflow | `start-worktree` | local | 建立新的 git worktree 以隔離任務開發。 | keep |  | 若常用 worktree 建議保留。 |
| Startup | `startup-ideation` | local | 產生與評估 startup idea、市場機會與可行性。 | maybe |  | 情境型，若少用可停用。 |
| Code workflow | `structure-outline` | fstack | 在詳細 planning/implementation 前產出 interface-first structure outline。 | keep |  | fstack 新核心流程。 |
| Work / Tagtoo | `tagtoo-create-flow` | local | 依 data_team_repos 原始碼與知識產出標準 flow 文件。 | keep |  | Tagtoo knowledge pool 用。 |
| Work / Tagtoo | `tagtoo-cross-repo` | local | 查詢跨 repo/service/table 資料流與整合點。 | keep |  | Tagtoo 跨服務理解用。 |
| UI / Design | `ui-ux-pro-max` | local | UI/UX 設計 intelligence，涵蓋風格、palette、font、framework 與 review。 | maybe |  | 若現有 frontend 指令已夠用可停用。 |
| Deployment | `vercel-deployment` | local | Next.js/Vercel 部署專家知識。 | maybe |  | 若近期少用 Vercel 可停用。 |
| Work / BigQuery | `verify-audience-write` | local | 驗證 EC 受眾是否正確寫入 BigQuery LTA 表。 | keep |  | Tagtoo 特定流程。 |
| Wrap up | `work-wrap-up` | fstack | 功能完成後執行 commit/PR、GSheet 進度同步、可選 Slack 通知。 | keep |  | 收尾流程核心。 |

## Review Notes

第一輪建議不要直接刪除。比較安全的做法是建立：

```bash
mkdir -p /Users/fredrick/.agents/skills.disabled
```

然後將 `保留? = remove` 的 skill 先移到 `skills.disabled/`，觀察一段時間沒有缺口再刪除。
