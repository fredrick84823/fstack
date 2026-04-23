# Markdown 整合範例

這個文檔展示如何在 Markdown 中嵌入 Beautiful Mermaid 渲染的圖表。

---

## 目錄

1. [系統架構](#系統架構)
2. [資料處理流程](#資料處理流程)
3. [API 互動序列](#api-互動序列)
4. [資料庫模型](#資料庫模型)
5. [最佳實踐](#最佳實踐)

---

## 系統架構

我們的系統採用三層架構設計，包含前端、後端和資料層。

![系統架構圖](./flowchart.svg)

### 架構說明

- **前端層**：使用 React 建構的單頁應用
- **後端層**：Node.js + Express REST API
- **資料層**：PostgreSQL 資料庫

---

## 資料處理流程

資料處理流程展示了從資料輸入到最終輸出的完整過程。

![資料處理流程圖](./advanced-flowchart-subgraph.svg)

### 流程步驟

1. **資料準備階段**
   - 讀取 project.yaml 配置檔案
   - 驗證配置的有效性
   - 解析參數並準備執行環境

2. **SQL 生成階段**
   - 載入對應的 SQL 模板
   - 將參數替換到模板中
   - 優化查詢以提升效能

3. **執行階段**
   - 檢查快取是否存在
   - 若無快取則執行 BigQuery 查詢
   - 將結果儲存到快取

4. **輸出階段**
   - 格式化查詢結果
   - 儲存為 JSON 格式
   - 轉換為 CSV 供後續使用
   - 生成分析報告

---

## API 互動序列

API 互動圖展示了客戶端與伺服器之間的通訊流程。

![API 互動序列圖](./sequence.svg)

### 互動流程

```
Client → Server: 發送 API 請求
Server → Cache: 檢查快取
Cache → Server: 返回快取狀態
Server → Database: 查詢資料（若無快取）
Database → Server: 返回查詢結果
Server → Client: 返回 API 響應
```

---

## 資料庫模型

資料庫 ER 圖展示了各個實體之間的關係。

![資料庫 ER 圖](./er.svg)

### 實體說明

- **USER**：使用者資料表，儲存使用者基本資訊
- **POST**：文章資料表，記錄所有發布的文章
- **COMMENT**：評論資料表，儲存使用者的評論
- **TAG**：標籤資料表，用於分類和搜尋

### 關係說明

- 一個使用者可以發布多篇文章（1:N）
- 一個使用者可以撰寫多則評論（1:N）
- 一篇文章可以有多則評論（1:N）
- 文章與標籤是多對多關係（M:N）

---

## 最佳實踐

### 1. 圖表命名規範

建議使用清晰且描述性的檔名：

```
✅ 好的命名：
- architecture-overview.svg
- user-authentication-flow.svg
- database-schema-v2.svg

❌ 不好的命名：
- diagram1.svg
- untitled.svg
- temp.svg
```

### 2. 目錄結構

建議的專案結構：

```
project/
├── README.md              # 主要文檔
├── docs/                  # 詳細文檔
│   ├── architecture.md
│   ├── api.md
│   └── database.md
├── diagrams/              # Mermaid 原始檔
│   ├── architecture.mmd
│   ├── sequence.mmd
│   └── er.mmd
└── rendered/              # 渲染後的 SVG
    ├── architecture.svg
    ├── sequence.svg
    └── er.svg
```

### 3. 嵌入圖表的語法

#### 相對路徑（推薦）

```markdown
![圖表說明](./diagrams/architecture.svg)
![圖表說明](../rendered/sequence.svg)
```

#### 絕對路徑

```markdown
![圖表說明](/path/to/diagram.svg)
```

#### 添加替代文字和標題

```markdown
![系統架構圖 - 展示三層架構設計](./architecture.svg "系統架構")
```

### 4. 渲染工作流程

#### 方式 A：手動渲染

```bash
# 渲染單一檔案
node scripts/render_mermaid.js -i diagram.mmd -o diagram.svg -t github-light

# 批量渲染
./assets/examples/batch-render.sh diagrams rendered github-light
```

#### 方式 B：Git Hook 自動渲染

在 `.git/hooks/pre-commit` 中：

```bash
#!/bin/bash
# 自動渲染修改過的 .mmd 檔案

changed_files=$(git diff --cached --name-only --diff-filter=ACM | grep '\.mmd$')

if [ -n "$changed_files" ]; then
    echo "Rendering Mermaid diagrams..."
    for file in $changed_files; do
        filename=$(basename "$file" .mmd)
        node scripts/render_mermaid.js \
            -i "$file" \
            -o "rendered/${filename}.svg" \
            -t github-light
        git add "rendered/${filename}.svg"
    done
fi
```

### 5. 主題選擇建議

根據文檔類型選擇合適的主題：

| 文檔類型 | 推薦主題（淺色） | 推薦主題（深色） |
|---------|----------------|----------------|
| GitHub README | `github-light` | `github-dark` |
| 企業文檔 | `zinc-light` | `zinc-dark` |
| 技術部落格 | `tokyo-night-light` | `tokyo-night` |
| 演示簡報 | `catppuccin-latte` | `catppuccin-mocha` |

### 6. 圖表大小控制

#### HTML 中控制大小

```html
<img src="diagram.svg" alt="圖表" width="600">
<img src="diagram.svg" alt="圖表" style="max-width: 100%;">
```

#### Markdown 中（某些渲染器支援）

```markdown
![圖表](./diagram.svg){width=600px}
<img src="./diagram.svg" alt="圖表" width="600">
```

---

## 進階技巧

### 多主題支援

為同一個圖表生成多個主題版本：

```bash
#!/bin/bash
themes=("github-light" "github-dark" "tokyo-night")
for theme in "${themes[@]}"; do
    node scripts/render_mermaid.js \
        -i architecture.mmd \
        -o "architecture-${theme}.svg" \
        -t "$theme"
done
```

然後在 Markdown 中根據上下文切換：

```markdown
<!-- Light mode -->
![架構圖](./architecture-github-light.svg#gh-light-mode-only)

<!-- Dark mode -->
![架構圖](./architecture-github-dark.svg#gh-dark-mode-only)
```

### 圖表版本控制

在檔名中包含版本號：

```
architecture-v1.svg
architecture-v2.svg
architecture-latest.svg  # 連結到最新版本
```

### 快取策略

使用 Git LFS 管理大型 SVG 檔案：

```bash
git lfs track "*.svg"
git add .gitattributes
```

---

## 疑難排解

### 圖表無法顯示

**問題**：Markdown 文檔中的圖表無法顯示

**解決方案**：
1. 檢查檔案路徑是否正確
2. 確認 SVG 檔案已經渲染並存在
3. 使用相對路徑而非絕對路徑
4. 確認檔案已提交到 Git（如果是遠端檢視）

### 圖表更新不同步

**問題**：修改 .mmd 檔案後，SVG 圖表沒有更新

**解決方案**：
1. 手動重新渲染：`node scripts/render_mermaid.js -i file.mmd -o file.svg`
2. 設定 Git hook 自動渲染
3. 使用批量渲染腳本：`./batch-render.sh`

---

## 相關資源

- [Beautiful Mermaid 官方文檔](https://github.com/seanchas116/beautiful-mermaid)
- [Mermaid 語法參考](https://mermaid.js.org/)
- [Markdown 語法指南](https://www.markdownguide.org/)

---

**最後更新**：2026-02-10

**維護者**：Claude Code

---

## 總結

透過 Beautiful Mermaid，你可以：

✅ 在 Markdown 中嵌入美觀的圖表
✅ 選擇 15 種精心設計的主題
✅ 使用批量渲染腳本提高效率
✅ 整合進 Git 工作流程自動化
✅ 保持文檔與圖表的一致性

開始使用 Beautiful Mermaid，讓你的技術文檔更專業、更美觀！
