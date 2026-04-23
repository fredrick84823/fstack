---
description: 根據 Heptabase 命名系統 v1.0 生成文件標題
---

請根據以下 Heptabase 命名系統規則，為文件生成符合規範的標題。

# 核心原則

1. **全小寫標籤**：所有標籤都使用小寫（如 [concept], [snippet]）
2. **英文術語優先**：使用英文術語以提升搜尋精準度與技術社群接軌
3. **搜尋導向**：標題要包含未來可能搜尋的關鍵字

# 分類標籤系統

## 📚 知識與學習 (Engineering & Learning)

存放可被反覆引用的原子知識。

- **[concept]**：核心概念、原理、演算法、專有名詞
  - 範例：[concept] Association Rule Mining、[concept] CAP Theorem

- **[snippet]**：代碼片段、Regex、Config 設定
  - 範例：[snippet] Pandas Date Conversion、[snippet] Nginx Config Template

- **[cheatsheet]**：速查表、快捷鍵清單、指令集
  - 範例：[cheatsheet] Frequently Used Websites、[cheatsheet] Vim Shortcuts

- **[howto]**：Step-by-step 操作步驟、安裝指南
  - 範例：[howto] Install Claude Plugin、[howto] Setup BigQuery Partition

- **[framework]**：思維模型、商業分析架構
  - 範例：[framework] North Star Metric、[framework] AARRR Funnel

- **[til]**：今日所學 (Today I Learned)，零散、尚未成體系的知識點
  - 範例：[til] Python dataclass frozen

## 🛠 專案與工作 (Projects & Execution)

具有時效性與特定目的，專案結束後可封存。

- **[project]**：專案主頁，彙整所有相關卡片連結
  - 範例：[project] 2025 Data Platform、[project] Membership System

- **[doc]**：正式文件、規格書、SOP、已定案規範
  - 範例：[doc] Plugin Publishing Flow、[doc] API Spec v1.0

- **[plan]**：計畫、時程表、Roadmap、Todo List
  - 範例：[plan] Q1 Roadmap、[plan] Weekly Sprint 12

- **[brainstorm]**：會議記錄、未定案想法、靈感發想
  - 範例：[brainstorm] Shopping Basket Naming

- **[postmortem]**：事後檢討、專案復盤、踩坑記錄
  - 範例：[postmortem] BigQuery Slot Limit Incident

## 📖 內省與輸入 (Input & Reflection)

心靈沈澱，與「你」有關的內容。

- **[journal]**：日記、生活流水帳、心情紀錄
  - 範例：[journal] 2025-12-01

- **[book]**：書籍筆記、讀書摘要
  - 範例：[book] 生命系列：中道

- **[reflection]**：反思洞見、消化後的個人觀點
  - 範例：[reflection] 真實與臣服的思考

# 你的任務

根據使用者提供的文件內容脈絡，生成適當的標題：

1. 從上述分類中選擇最合適的標籤
2. 使用清晰、可搜尋的英文短語（除非是日記使用日期，或書籍/反思類別可使用中文）
3. 標籤使用小寫格式

如需更多脈絡資訊，請向使用者詢問，然後提供 2-3 個標題建議，並簡要說明選擇該標籤的理由。
