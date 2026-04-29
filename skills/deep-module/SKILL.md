---
name: deep-module
description: Applies the Deep Module principle (John Ousterhout / Matt Pocock) at any stage of development. Use this skill during planning (create-plan) to shape module boundaries before writing specs, during implementation (implement-plan) to enforce interface-first design before writing code, or during code review to identify shallow abstractions. Trigger when the user mentions "deep module", "shallow module", "interface design", "encapsulation", asks to review module structure, or when any new module/class/function is about to be designed or implemented.
allowed-tools: Read, Write, Edit, Bash
---

# Deep Module

> 人類設計介面輪廓，AI 填實作細節。
> — Matt Pocock，AI-assisted Software Engineering

深模組（Deep Module）的核心：對外暴露極簡介面，對內封裝複雜邏輯。
淺模組（Shallow Module）的問題：只是轉發呼叫，把本應隱藏的複雜性洩漏給呼叫方。

根據目前所在的階段，選擇對應模式：

---

## Mode 1：Plan（規劃階段）

在 `create-plan` 或定義架構時使用。目標是在撰寫任何程式碼前，先確認各模組的邊界與職責。

**做法：**

對計畫中每個預計新增的 module/class/service，輸出一份 Module Boundary Sketch：

```
## Module Boundary Sketch: {名稱}

**Purpose**: {一句話，說明這個模組對外解決什麼問題}
**Consumers**: {誰會呼叫它？他們需要知道什麼？}
**Hidden complexity**: {它應該封裝哪些呼叫方不需要知道的複雜度？}
**Interface shape**: {預計對外暴露的 function/method 數量與粗略簽名}

**Depth check**: 介面是否比它封裝的複雜度更簡單？
→ {是 ✅ 繼續 / 否 ⚠️ 重新考慮邊界}
```

輸出完後問使用者：「這些模組邊界是否合理？有需要調整的嗎？」

---

## Mode 2：Implement（實作前）

在 `implement-plan` 執行、即將動手寫新 module/class/function 時使用。目標是先鎖定介面，再填實作。

**做法：**

1. 輸出 Interface Sketch：

   ```
   ## Interface Sketch: {名稱}

   **Purpose**: {一句話職責}
   **Input**: {參數名稱、型別}
   **Output**: {回傳值型別與意義}
   **Errors**: {可能的例外情況}

   **Hidden inside**:
   - {呼叫方不需要知道的內部邏輯 1}
   - {呼叫方不需要知道的內部邏輯 2}

   **Depth check**: 介面是否比它封裝的複雜度更簡單？
   → {是 ✅ / 否 ⚠️}
   ```

2. **停下來等確認**：輸出後問「介面設計是否符合預期？」收到確認才實作內部邏輯。

---

## Mode 3：Review（審查既有程式碼）

在 code review 或 implement-plan phase 驗證時使用。目標是找出淺模組並建議重構方向。

**淺模組判斷標準（符合任一即可判定）：**
- 函式體幾乎只是呼叫另一個函式，無額外邏輯
- 呼叫方必須了解被呼叫方的內部細節才能正確使用
- 介面的複雜度（參數數量、型別限制、呼叫順序）≥ 它封裝的複雜度

**做法：**

掃描指定範圍的程式碼，輸出審查報告：

```
## Deep Module Review

### ✅ Deep modules
- {名稱}：介面簡潔（{N} 個參數），隱藏了 {描述內部複雜度}

### ⚠️ Shallow modules（建議重構）
- {名稱}：{問題描述}
  建議：{合併到呼叫端 / 在此加入實際邏輯後暴露更簡潔介面 / 重新劃分邊界}

### 整體評估
{良好 / 需改善} — {一句話說明}
```

---

## 範例對比

**淺模組（問題）：**
```python
def get_user_name(user_id):
    return user_repository.find_by_id(user_id).name
# 呼叫方需要知道 repository 的存在；介面複雜度 ≈ 內部複雜度
```

**深模組（好）：**
```python
def get_user_profile(user_id: str) -> UserProfile:
    # 封裝：快取、錯誤處理、資料轉換、權限驗證
    # 呼叫方只需 user_id，取回 UserProfile
```

---

## 核心原則

來自 John Ousterhout《A Philosophy of Software Design》，由 Matt Pocock 應用於 AI 輔助開發：

> "The best modules are those that provide powerful functionality yet have simple interfaces."

人類掌握系統的「形狀」（介面輪廓），AI 負責填入「內容」（實作細節）。
