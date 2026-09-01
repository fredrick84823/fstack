---
name: knowledge-map
description: 快速對焦學習標的、目前學習狀態與 visual-first 知識版面。
disable-model-invocation: true
---

# Knowledge Map

**Overview first.** 先用可修正的全景建立掛載點，再局部深入、回到全景整合。Knowledge Map 是持續演進的 **advance organizer**：同時提供 overview、navigation、integration。

## Domain model

| 詞彙 | 意義 |
|---|---|
| **Learning Target** | 本次要理解的具體對象 |
| **Learning State** | 學習者目前相對於標的的理解狀態，隨理解持續變化 |
| **Learning Move** | 下一步認知操作 |
| **Information Shape** | 知識本身的結構，如關係、流程、比較、時間 |
| **Visual Layout** | 主要由位置、容器、連線、方向、尺度或層級承載意義的抽象模板 |
| **Knowledge Map** | 主題的漸進式視覺總覽與導航入口 |

Visual Layout 可以包含文字。圖形與空間承載主要意義；文字只負責短標籤、一句定義、關係動詞、關鍵差異、例子與 caveat。

## 1. Route

先利用使用者已提供的內容推斷。需要區分會導向不同版面的路徑時，問一個辨別問題。

| 使用者目前的狀態 | Learning Move | Information Shape | Visual Layout |
|---|---|---|---|
| 主題邊界或核心問題仍模糊 | Orient | Questions / Boundary | Question Map |
| 新主題，或缺少可信的整體框架 | Map | Hierarchy + key relations | Knowledge Map v0 |
| 單一概念的意義或用途不清楚 | Define | Entity / attributes | Concept Card |
| 元件之間如何互動不清楚 | Relate | Network / dependency | Relationship Diagram |
| 運作順序、狀態變化或資料流不清楚 | Trace | Sequence / transformation | Flow Diagram |
| 需要選擇或理解差異與取捨 | Compare | Dimensions / alternatives | Comparison Matrix |
| 需要理解演進與時間因果 | Contextualize | Chronology | Timeline |
| 已理解但需要快速執行或查找 | Operationalize | Commands / rules | Cheat Sheet |
| 已理解但需要壓縮、回顧或解釋 | Compress | Hierarchy + synthesis | Summary Map |

新主題預設走 `Map → Knowledge Map v0`。若多種 shape 同時存在，先選最能解除目前理解瓶頸的一種，其餘成為後續 detail views。

**完成標準：**已選出一條主要路徑；任何足以改變版面的不確定性都已明示。

## 2. Align

立即提出一張對焦卡：

```markdown
| 對焦欄位 | 建議 |
|---|---|
| Topic | ... |
| Learning Target | ... |
| Current State | ... |
| Next Move | ... |
| Information Shape | ... |
| Visual Layout | ... |
| Map Role | Overview / Detail / Integration |
| Why | 一句話 |
```

接著顯示該版面的極簡骨架。路徑明確時只提一案；兩案都合理時列 A/B，並問一個區分問題。把內容教學留到使用者確認之後。

**完成標準：**使用者可以直接確認，或只需修正對焦卡中的特定欄位。

## 3. Build and loop

把使用者確認視為開始建立的訊號；route-only 目標則以已確認的對焦卡收尾。建立前讀 [`LAYOUTS.md`](LAYOUTS.md) 中所選版面的 required slots 與 skeleton。

1. 先顯示 visual skeleton，再用現有資訊填入。
2. 使用者指定媒介時沿用；未指定時，network／flow／timeline 優先 Mermaid，matrix／card 優先 Markdown，早期草圖可用 ASCII。
3. 用 `?` 標示 unknown，用 `assumption` 標示暫定結構。
4. Detail view 完成後，提出 Knowledge Map 更新：新增、改名、移動或連結哪些節點。

**完成標準：**所選 layout 的 required slots 全部已填入或標成 unknown；overview 與 detail 的掛載關係清楚；下一個理解瓶頸可從圖上看見。
