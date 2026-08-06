# Visual Layout Catalog

只讀已選中的 layout。每個 skeleton 表達資訊結構，可套用不同美術樣式。

## Question Map

**回答：**這個主題真正要問什麼？邊界在哪裡？

**Required slots：**中心主題、Why、What、How、Boundary、Unknowns。

```text
                 [Why?]
                   │
[Boundary] ── [Topic] ── [What?]
                   │
                 [How?]
                   │
              [? Unknowns]
```

## Knowledge Map v0

**回答：**整個領域由哪些主要區域組成？它們如何連接？

**Required slots：**Purpose、Boundary、top-level regions、key relationships、Unknowns。

```text
┌────────────────── Topic ──────────────────┐
│ Purpose                                   │
│                                           │
│ [Region A] ──關係──> [Region B]           │
│      │                     │              │
│      └────> [Region C] <───┘              │
│                                           │
│ Boundary: ...        Unknowns: ? ? ?      │
└───────────────────────────────────────────┘
```

每個 region 應可下鑽成一張 detail view。Knowledge Map 更新時保留版本或列出 structural patch。

## Concept Card

**回答：**這個概念是什麼、為何存在、如何辨認？

**Required slots：**Definition、Purpose、Mechanism、Example、Boundary / non-example、Related concepts。

```text
┌────────────── Concept ──────────────┐
│ 一句定義                            │
├───────────┬─────────────────────────┤
│ Purpose   │ Mechanism               │
├───────────┼─────────────────────────┤
│ Example   │ Boundary / non-example  │
└───────────┴─────────────────────────┘
          ↙ related       related ↘
```

## Relationship Diagram

**回答：**誰與誰有關？關係的方向與性質是什麼？

**Required slots：**entities、boundaries、directed edges、每條 edge 的關係動詞、feedback / dependency。

```text
[Entity A] ──觸發──> [Entity B]
     │                    │
   依賴                  產生
     ↓                    ↓
[Entity C] <──回饋── [Entity D]
```

## Flow Diagram

**回答：**事情如何依序發生？什麼條件造成分支或狀態改變？

**Required slots：**start、steps / states、inputs / outputs、decision points、end、feedback loops。

```text
(Start) → [Step A] → <Condition?> ─yes→ [Step B] → (End)
                         │
                         no
                         ↓
                     [Fallback]
```

跨角色流程用 lanes；資料轉換則在箭頭標示輸入與輸出。

## Comparison Matrix

**回答：**選項在哪些共同維度上不同？差異造成什麼取捨？

**Required slots：**alternatives、shared dimensions、evidence per cell、trade-off summary、decision context。

```text
                Option A   Option B   Option C
Dimension 1        ...        ...        ...
Dimension 2        ...        ...        ...
Dimension 3        ...        ...        ...
Trade-off          ...        ...        ...
```

維度必須對所有選項具有相同意義。

## Timeline

**回答：**什麼在何時改變？每次改變由什麼促成，又造成什麼結果？

**Required slots：**time axis、events / eras、trigger、change、consequence、continuities。

```text
Past ──[Trigger]──> [Change A] ──> [Change B] ──> Present
                         │                │
                    consequence      consequence
```

## Cheat Sheet

**回答：**執行工作時，需要最快取回哪些資訊？

**Required slots：**task groups、commands / rules、inputs、expected result、common failure recovery。

```text
┌──────── Task ────────┬──── Action ────┬── Result / Recovery ─┐
│ ...                  │ ...            │ ...                 │
└──────────────────────┴────────────────┴─────────────────────┘
```

依使用情境分群，讓一次掃視即可找到下一個 action。

## Summary Map

**回答：**如何用一張圖重建整體理解並向他人解釋？

**Required slots：**one-line thesis、core model、main mechanism、key distinctions、pitfalls、takeaway。

```text
                  [One-line thesis]
                          │
                    [Core model]
                   ↙      ↓      ↘
             [Part A] [Mechanism] [Part B]
                          │
             [Distinction / Pitfall]
                          │
                      [Takeaway]
```
