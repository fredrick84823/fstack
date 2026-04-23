# Beautiful Mermaid Integration Guide

完整指南：如何將 beautiful-mermaid 整合到各種工作流程和平台中。

---

## Markdown 嵌入完整語法

### 基本嵌入

在 Markdown 文檔中嵌入 SVG 圖表：

```markdown
# 系統架構文檔

## 概述

以下是我們的系統架構圖：

![系統架構](./diagrams/architecture.svg)

## 詳細說明

架構由三個主要部分組成...
```

### 相對路徑 vs 絕對路徑

```markdown
<!-- 相對路徑（推薦） -->
![圖表](./diagrams/flow.svg)
![圖表](../assets/sequence.svg)

<!-- 絕對路徑 -->
![圖表](/Users/username/project/diagrams/flow.svg)

<!-- GitHub 原始檔 URL -->
![圖表](https://raw.githubusercontent.com/user/repo/main/diagrams/flow.svg)
```

### 添加替代文字和標題

```markdown
![系統流程圖 - 描述處理流程的詳細步驟](./flow.svg "系統處理流程")
```

**最佳實踐**：
- ✅ 使用相對路徑以便於移植
- ✅ 提供有意義的替代文字（accessibility）
- ✅ 將圖表放在專門的 `diagrams/` 目錄中
- ✅ 同時保留 `.mmd` 原始檔和 `.svg` 輸出檔

---

## HTML 頁面組織模式

### 模式 1：單圖表頁面

適用於：專注於單一圖表的詳細說明

```html
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>系統架構圖</title>
    <style>
        body {
            font-family: 'Inter', -apple-system, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
            background: #1a1b26;
            color: #a9b1d6;
        }
        h1 { color: #7aa2f7; }
        .diagram-container {
            background: #24283b;
            padding: 30px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .diagram-container svg {
            max-width: 100%;
            height: auto;
        }
    </style>
</head>
<body>
    <h1>系統架構圖</h1>
    <p>以下圖表展示了我們系統的核心架構...</p>

    <div class="diagram-container">
        <!-- 嵌入 SVG -->
        <img src="architecture.svg" alt="系統架構圖">
    </div>

    <h2>說明</h2>
    <p>詳細的架構說明...</p>
</body>
</html>
```

### 模式 2：多圖表報告

適用於：技術報告、文檔頁面、演示

```html
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <title>技術報告</title>
    <style>
        body {
            font-family: 'Inter', sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 40px 20px;
            background: #f9fafb;
            color: #1f2937;
        }
        section {
            background: white;
            padding: 30px;
            margin: 30px 0;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        h1 { color: #1e40af; }
        h2 { color: #3b82f6; margin-top: 0; }
        .diagram { margin: 20px 0; }
        .diagram img { max-width: 100%; height: auto; }
    </style>
</head>
<body>
    <h1>系統技術報告</h1>

    <section>
        <h2>1. 系統架構</h2>
        <p>系統採用微服務架構...</p>
        <div class="diagram">
            <img src="diagrams/architecture.svg" alt="系統架構">
        </div>
    </section>

    <section>
        <h2>2. API 互動流程</h2>
        <p>前端與後端的通訊流程...</p>
        <div class="diagram">
            <img src="diagrams/api-sequence.svg" alt="API 流程">
        </div>
    </section>

    <section>
        <h2>3. 資料模型</h2>
        <p>資料庫實體關係...</p>
        <div class="diagram">
            <img src="diagrams/database-er.svg" alt="資料模型">
        </div>
    </section>
</body>
</html>
```

### 模式 3：互動式主題切換

適用於：演示、教學、展示 beautiful-mermaid 的主題功能

```html
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <title>互動式圖表展示</title>
    <style>
        body {
            font-family: 'Inter', sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
            background: #0f0f0f;
            color: #e0e0e0;
        }
        .controls {
            background: #1a1a1a;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
        }
        .theme-buttons {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        .theme-btn {
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
        }
        .theme-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }
        .diagram-container {
            background: #1a1a1a;
            padding: 30px;
            border-radius: 8px;
        }
    </style>
</head>
<body>
    <h1>Beautiful Mermaid 主題展示</h1>

    <div class="controls">
        <h3>選擇主題：</h3>
        <div class="theme-buttons">
            <button class="theme-btn" onclick="switchTheme('tokyo-night')" style="background: #7aa2f7; color: #1a1b26;">Tokyo Night</button>
            <button class="theme-btn" onclick="switchTheme('github-light')" style="background: #0969da; color: white;">GitHub Light</button>
            <button class="theme-btn" onclick="switchTheme('dracula')" style="background: #bd93f9; color: #282a36;">Dracula</button>
            <button class="theme-btn" onclick="switchTheme('nord')" style="background: #88c0d0; color: #2e3440;">Nord</button>
            <button class="theme-btn" onclick="switchTheme('catppuccin-mocha')" style="background: #cba6f7; color: #1e1e2e;">Catppuccin</button>
        </div>
    </div>

    <div class="diagram-container" id="diagram-container">
        <img id="diagram-img" src="diagrams/demo-tokyo-night.svg" alt="示範圖表">
    </div>

    <script>
        function switchTheme(theme) {
            const img = document.getElementById('diagram-img');
            img.src = `diagrams/demo-${theme}.svg`;
        }
    </script>
</body>
</html>
```

---

## 批量渲染腳本範例

### Bash 腳本（macOS/Linux）

```bash
#!/bin/bash
# batch-render.sh - 批量渲染所有 .mmd 檔案

THEME="tokyo-night"
INPUT_DIR="./diagrams"
OUTPUT_DIR="./rendered"

# 創建輸出目錄
mkdir -p "$OUTPUT_DIR"

# 渲染所有 .mmd 檔案
for mmd_file in "$INPUT_DIR"/*.mmd; do
    # 取得檔案名稱（不含路徑和副檔名）
    filename=$(basename "$mmd_file" .mmd)

    echo "Rendering: $filename..."

    # 渲染為 SVG
    node scripts/render_mermaid.js \
        -i "$mmd_file" \
        -o "$OUTPUT_DIR/${filename}.svg" \
        -t "$THEME"

    if [ $? -eq 0 ]; then
        echo "✅ $filename.svg"
    else
        echo "❌ Failed: $filename"
    fi
done

echo "✨ 完成！共渲染 $(ls "$OUTPUT_DIR"/*.svg 2>/dev/null | wc -l) 個檔案"
```

### PowerShell 腳本（Windows）

```powershell
# batch-render.ps1 - 批量渲染所有 .mmd 檔案

$Theme = "tokyo-night"
$InputDir = "./diagrams"
$OutputDir = "./rendered"

# 創建輸出目錄
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

# 渲染所有 .mmd 檔案
Get-ChildItem -Path $InputDir -Filter *.mmd | ForEach-Object {
    $filename = $_.BaseName
    Write-Host "Rendering: $filename..." -ForegroundColor Yellow

    node scripts/render_mermaid.js `
        -i $_.FullName `
        -o "$OutputDir/$filename.svg" `
        -t $Theme

    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ $filename.svg" -ForegroundColor Green
    } else {
        Write-Host "❌ Failed: $filename" -ForegroundColor Red
    }
}

$count = (Get-ChildItem -Path $OutputDir -Filter *.svg).Count
Write-Host "✨ 完成！共渲染 $count 個檔案" -ForegroundColor Cyan
```

---

## CI/CD 整合範例

### GitHub Actions

在 `.github/workflows/render-diagrams.yml`：

```yaml
name: Render Mermaid Diagrams

on:
  push:
    paths:
      - 'diagrams/**/*.mmd'
  pull_request:
    paths:
      - 'diagrams/**/*.mmd'

jobs:
  render:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '18'

      - name: Install beautiful-mermaid
        run: npm install -g beautiful-mermaid

      - name: Render diagrams
        run: |
          mkdir -p rendered
          for file in diagrams/*.mmd; do
            filename=$(basename "$file" .mmd)
            npx beautiful-mermaid render \
              -i "$file" \
              -o "rendered/${filename}.svg" \
              -t github-light
          done

      - name: Commit rendered diagrams
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          git add rendered/
          git diff --quiet && git diff --staged --quiet || \
            git commit -m "chore: update rendered diagrams"
          git push
```

---

## Web 框架整合

### React 範例

```tsx
import { useEffect, useState } from 'react';
import { renderMermaid } from 'beautiful-mermaid';

interface DiagramProps {
  code: string;
  theme?: string;
}

export function MermaidDiagram({ code, theme = 'tokyo-night' }: DiagramProps) {
  const [svg, setSvg] = useState<string>('');
  const [error, setError] = useState<string>('');

  useEffect(() => {
    const render = async () => {
      try {
        const result = await renderMermaid(code, {
          theme,
          fontFamily: 'Inter',
        });
        setSvg(result);
        setError('');
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Rendering failed');
      }
    };

    render();
  }, [code, theme]);

  if (error) {
    return <div className="error">Failed to render diagram: {error}</div>;
  }

  return (
    <div
      className="mermaid-diagram"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}

// 使用範例
function App() {
  const diagramCode = `
    graph TD
      A[Start] --> B{Decision}
      B -->|Yes| C[Process]
      B -->|No| D[End]
  `;

  return (
    <div>
      <h1>System Flow</h1>
      <MermaidDiagram code={diagramCode} theme="github-light" />
    </div>
  );
}
```

### Vue 3 範例

```vue
<template>
  <div class="mermaid-diagram">
    <div v-if="error" class="error">{{ error }}</div>
    <div v-else v-html="svg"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import { renderMermaid } from 'beautiful-mermaid';

const props = defineProps<{
  code: string;
  theme?: string;
}>();

const svg = ref('');
const error = ref('');

const render = async () => {
  try {
    svg.value = await renderMermaid(props.code, {
      theme: props.theme || 'tokyo-night',
      fontFamily: 'Inter',
    });
    error.value = '';
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Rendering failed';
  }
};

watch(() => [props.code, props.theme], render, { immediate: true });
</script>

<style scoped>
.mermaid-diagram {
  margin: 20px 0;
}
.error {
  color: #ef4444;
  padding: 10px;
  background: #fee;
  border-radius: 4px;
}
</style>
```

---

## 最佳實踐總結

### 專案組織

```
project/
├── diagrams/           # Mermaid 原始檔 (.mmd)
│   ├── architecture.mmd
│   ├── sequence.mmd
│   └── database.mmd
├── rendered/           # 渲染後的 SVG
│   ├── architecture.svg
│   ├── sequence.svg
│   └── database.svg
├── docs/              # 文檔（嵌入 SVG）
│   └── README.md
└── scripts/
    └── batch-render.sh
```

### 版本控制策略

**選項 A：只提交原始檔**
- ✅ 倉庫更乾淨
- ✅ 避免合併衝突
- ❌ 需要渲染才能查看

```gitignore
rendered/
*.svg
```

**選項 B：同時提交原始檔和輸出檔**（推薦）
- ✅ 可直接在 GitHub 上查看
- ✅ 適合文檔專案
- ⚠️ 需要保持同步

```gitignore
# 只忽略臨時檔案
.mermaid-cache/
```

### 效能優化

1. **快取渲染結果** - 避免重複渲染相同內容
2. **預渲染靜態圖表** - 在建置階段渲染，而非執行時
3. **使用 CDN** - 對於公開圖表，使用 CDN 加速
4. **延遲載入** - 只渲染可見的圖表

---

## 疑難排解

### 常見問題

**Q: SVG 在 GitHub 上顯示不正確**
A: 確保使用相對路徑，並且 SVG 檔案已提交到倉庫

**Q: 批量渲染腳本權限錯誤**
A: 執行 `chmod +x batch-render.sh` 賦予執行權限

**Q: CI/CD 渲染失敗**
A: 確認 Node.js 版本 >= 16，並檢查 npm 安裝日誌

**Q: React/Vue 中渲染緩慢**
A: 使用 `useMemo` 或 `computed` 快取結果，避免重複渲染
