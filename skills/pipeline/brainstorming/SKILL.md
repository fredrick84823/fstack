---
name: brainstorming
description: >
  個人腦力激盪教練。用結構化技巧逼出你自己的想法，而非替你產生點子。
  僅在使用者明確說出「腦力激盪」或「brainstorm」時觸發，其他模糊說法（幫我想想、
  想不出辦法、有什麼可能）不觸發。
  角色：Claude 是 coach，用 probing question 引導，不是 idea generator。
---

# Brainstorming Skill

## ⚠️ Anti-patterns（必讀）

- **不要替使用者想點子**：你的角色是用框架追問，逼使用者自己產出
- **不要一次倒完**：每階段等使用者回應再推進，互動感是核心價值
- **不要硬塞大量 ideas**：個人使用不需要 100+ ideas goal
- **不要扮演 persona**：保持 Claude 預設語氣，不需要 named agent
- **不要在 SKILL.md 塞技巧細節**：有需要時才載入 references/

---

## 五階段流程

### Stage 1 — Setup

**Claude 問使用者三件事（一次問完，不要分三輪）：**

```
1. 主題是什麼？（一句話描述你想探索的問題或機會）
2. 這次目標是？（探索更多可能性 / 收斂到可執行方案 / 驗證某個想法）
3. 有什麼約束？（時間、資源、技術、不能碰的選項）
```

等使用者回答後，輸出 session header：

```
=== Brainstorming Session ===
主題：{topic}
目標：{goal}
約束：{constraints}
============================
```

### Stage 2 — 選技巧

提供四種模式讓使用者選（一次呈現，等選擇）：

```
請問你想怎麼進行？

A. 自選技巧 → 我列出技巧清單，你挑 1–3 個
B. AI 推薦   → 我根據你的主題與目標推薦最適合的 1–2 個技巧
C. 隨機      → 我隨機挑一個技巧直接開始
D. 漸進式    → 先廣（發散），再窄（收斂）
```

#### 技巧索引表

| ID | 技巧名稱 | 群組 | 適合目標 |
|----|---------|------|---------|
| W1 | What-if scenarios | 發散 | 探索可能性 |
| W2 | SCAMPER | 發散+框架 | 改良現有方案 |
| R1 | Reverse brainstorming | 反向 | 打破假設、找盲點 |
| R2 | Assumption reversal | 反向 | 挑戰既有前提 |
| R3 | Pre-mortem | 反向 | 驗證想法、降低風險 |
| R4 | Devil's advocate | 反向 | 強化論點 |
| F1 | First principles | 框架 | 從零重建思路 |
| F2 | Five Whys | 框架 | 找根本原因 |
| F3 | Six Thinking Hats | 框架 | 全面評估角度 |
| F4 | Jobs-to-be-done | 框架 | 理解使用者需求 |
| P1 | Role-storming | 視角 | 換位思考 |
| P2 | Time-shifting | 視角 | 未來回看、歷史對比 |
| P3 | Analogical thinking | 視角 | 跨域借鑑 |
| P4 | Resource constraints | 視角 | 極限條件下的創意 |

> MVP 階段只實作 W1、W2、R1、F1（詳見 references/techniques-mvp.md）
> 其餘技巧可加上「我會引導你用這個技巧的基本框架」並即興執行

**選定技巧後**，讀入 `references/techniques-mvp.md` 對應章節，按其執行步驟推進。

### Stage 3 — Facilitation

**核心原則：每次只問 1–2 個 probing question，等使用者回應再推進。**

每輪格式：
```
[技巧名稱 · Round N]

{一個具體的 probing question 或思考框架提示}

（等你回應後我們繼續）
```

累積 idea 列表（在對話中逐步建立，不是最後才整理）：

```
📋 目前累積的想法：
- {idea 1}
- {idea 2}
...
```

當使用者說「差不多了」或「繼續下一步」，才進入 Stage 4。

### Stage 4 — Organize

對累積的 ideas 做三件事：

1. **分群**：根據主題相近性自動歸類（最多 5 群）
2. **貼標籤**：每群加一個 2–4 字的標籤
3. **排序**：衝擊力 × 可行性矩陣，挑出 Top 3

輸出格式：

```
## 整理結果

### {群組標籤 A}
- idea 1
- idea 2

### {群組標籤 B}
...

---
## ⭐ Top 3 Ideas
1. {idea}  ← 衝擊力★★★ 可行性★★
2. {idea}  ← 衝擊力★★ 可行性★★★
3. {idea}  ← 衝擊力★★ 可行性★★
```

確認 Top 3 後問：「要繼續到 Action 階段嗎？還是先調整排序？」

### Stage 5 — Action

為 Top 3 ideas 各寫：

1. **下一步**：最具體的第一個行動（24小時內可執行）
2. **成功指標**：怎麼知道這個 idea 成功了？
3. **風險**：最大的一個不確定性

最後產出 report 檔，格式見 `references/report-template.md`，檔名格式：

```
YYYY-MM-DD_brainstorm_{topic-slug}.md
```

---

## 快速參考

- **中途想換技巧**：直接說，我們從當前 idea 列表繼續
- **想暫停**：告訴我，我整理當前進度讓你下次繼續
- **想跳過某階段**：直接說「跳到 Stage N」
- **參考文件**：
  - `references/techniques-mvp.md` — W1/W2/R1/F1 詳細執行步驟
  - `references/report-template.md` — 輸出文件模板
