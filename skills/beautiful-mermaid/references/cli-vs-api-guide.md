# CLI vs API 使用指南

選擇正確的 beautiful-mermaid 使用方式：命令列工具 vs 程式化 API。

---

## 快速決策矩陣

| 情境 | 推薦方式 | 理由 |
|------|---------|------|
| **文檔維護** | CLI | 簡單直接，適合人工操作 |
| **批量渲染** | CLI（腳本） | 易於自動化，shell 腳本即可 |
| **Web 應用** | API | 動態渲染，程式化控制 |
| **CI/CD 流程** | CLI | 與 git hooks 整合容易 |
| **即時預覽** | API | 無需寫入檔案，記憶體操作 |
| **主題切換** | API | 無需重新執行命令 |
| **一次性任務** | CLI | 快速完成，無需編寫程式碼 |
| **複雜邏輯** | API | 完整的程式化控制 |

---

## CLI（Command Line Interface）

### 何時使用 CLI

✅ **適合的情境**：
- 手動創建/更新文檔圖表
- 批量渲染多個檔案（配合 shell 腳本）
- CI/CD 自動化流程
- 快速測試和驗證 Mermaid 語法
- 不需要程式化控制的簡單任務

❌ **不適合的情境**：
- 需要在 Web 應用中動態渲染
- 需要即時主題切換
- 需要複雜的條件邏輯
- 效能敏感的場景（避免多次啟動 Node 進程）

### CLI 命令參數詳解

#### 基本命令結構

```bash
node scripts/render_mermaid.js [options]
```

#### 必要參數

| 參數 | 簡寫 | 說明 | 範例 |
|------|------|------|------|
| `--input` | `-i` | 輸入的 .mmd 檔案路徑 | `-i diagram.mmd` |
| `--output` | `-o` | 輸出檔案路徑 | `-o output.svg` |

#### 可選參數

| 參數 | 簡寫 | 預設值 | 說明 | 範例 |
|------|------|--------|------|------|
| `--theme` | `-t` | `tokyo-night` | 主題名稱 | `-t github-light` |
| `--format` | `-f` | `svg` | 輸出格式（svg 或 html） | `-f html` |
| `--transparent` | 無 | `false` | 透明背景 | `--transparent` |
| `--help` | `-h` | - | 顯示幫助訊息 | `-h` |

### CLI 使用範例

#### 範例 1：基本 SVG 渲染

```bash
node scripts/render_mermaid.js \
  --input architecture.mmd \
  --output architecture.svg \
  --theme tokyo-night
```

#### 範例 2：渲染為 HTML

```bash
node scripts/render_mermaid.js \
  -i sequence.mmd \
  -o report.html \
  -f html \
  -t github-light
```

#### 範例 3：透明背景

```bash
node scripts/render_mermaid.js \
  -i logo.mmd \
  -o logo.svg \
  -t dracula \
  --transparent
```

#### 範例 4：批量渲染（Bash）

```bash
#!/bin/bash
# 渲染所有 .mmd 檔案

for file in diagrams/*.mmd; do
    filename=$(basename "$file" .mmd)
    node scripts/render_mermaid.js \
        -i "$file" \
        -o "rendered/${filename}.svg" \
        -t nord
    echo "✅ Rendered: $filename"
done
```

#### 範例 5：多主題渲染

```bash
#!/bin/bash
# 為同一個圖表渲染多個主題版本

INPUT="diagram.mmd"
THEMES=("tokyo-night" "github-light" "dracula" "nord")

for theme in "${THEMES[@]}"; do
    node scripts/render_mermaid.js \
        -i "$INPUT" \
        -o "output-${theme}.svg" \
        -t "$theme"
    echo "✅ Theme: $theme"
done
```

### CLI 在 CI/CD 中的應用

#### GitHub Actions 範例

```yaml
name: Render Diagrams

on:
  push:
    paths:
      - 'diagrams/**/*.mmd'

jobs:
  render:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '18'

      - name: Install beautiful-mermaid
        run: npm install -g beautiful-mermaid

      - name: Render all diagrams
        run: |
          mkdir -p rendered
          for file in diagrams/*.mmd; do
            filename=$(basename "$file" .mmd)
            node scripts/render_mermaid.js \
              -i "$file" \
              -o "rendered/${filename}.svg" \
              -t github-light
          done

      - name: Commit changes
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          git add rendered/
          git commit -m "chore: update diagrams" || exit 0
          git push
```

---

## API（Application Programming Interface）

### 何時使用 API

✅ **適合的情境**：
- Web 應用中動態渲染圖表
- 需要即時主題切換
- 使用者生成內容（UGC）的圖表
- 複雜的條件邏輯和資料處理
- 效能敏感的場景（避免檔案 I/O）
- 需要快取和優化的場景

❌ **不適合的情境**：
- 簡單的一次性渲染任務
- 不需要程式化控制的場景
- 純命令列環境

### API 函數簽名

#### 主要渲染函數

```typescript
function renderMermaid(
  code: string,
  options?: RenderOptions
): Promise<string>
```

**參數**：
- `code` (string) - Mermaid 圖表程式碼
- `options` (RenderOptions, 可選) - 渲染選項

**RenderOptions 介面**：

```typescript
interface RenderOptions {
  theme?: string;              // 主題名稱，預設 'tokyo-night'
  fontFamily?: string;         // 字體，預設 'Inter'
  monoFontFamily?: string;     // 等寬字體，預設 'JetBrains Mono'
  transparent?: boolean;       // 透明背景，預設 false
  scale?: number;              // 縮放比例，預設 1
  width?: number;              // 寬度（像素）
  height?: number;             // 高度（像素）
}
```

**返回值**：
- Promise<string> - 渲染後的 SVG 字串

#### ASCII 渲染函數

```typescript
function renderMermaidAscii(
  code: string
): Promise<string>
```

**參數**：
- `code` (string) - Mermaid 圖表程式碼

**返回值**：
- Promise<string> - ASCII/Unicode 藝術字串

### API 使用範例

#### 範例 1：基本 Node.js 使用

```javascript
import { renderMermaid } from 'beautiful-mermaid';

const code = `
graph TD
    A[Start] --> B{Decision}
    B -->|Yes| C[Process]
    B -->|No| D[End]
`;

const svg = await renderMermaid(code, {
  theme: 'tokyo-night',
  fontFamily: 'Inter',
});

console.log(svg); // SVG 字串
```

#### 範例 2：自定義選項

```javascript
const svg = await renderMermaid(code, {
  theme: 'github-light',
  fontFamily: 'Arial',
  monoFontFamily: 'Courier New',
  transparent: true,
  scale: 1.5,
});
```

#### 範例 3：錯誤處理

```javascript
try {
  const svg = await renderMermaid(code, { theme: 'tokyo-night' });
  console.log('✅ Rendered successfully');
} catch (error) {
  console.error('❌ Rendering failed:', error.message);
  // 處理錯誤：顯示錯誤訊息給使用者
}
```

#### 範例 4：React Hook

```typescript
import { useEffect, useState } from 'react';
import { renderMermaid } from 'beautiful-mermaid';

function useMermaid(code: string, theme: string = 'tokyo-night') {
  const [svg, setSvg] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const render = async () => {
      setLoading(true);
      setError(null);

      try {
        const result = await renderMermaid(code, { theme });
        if (!cancelled) {
          setSvg(result);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Unknown error');
          setLoading(false);
        }
      }
    };

    render();

    return () => {
      cancelled = true;
    };
  }, [code, theme]);

  return { svg, loading, error };
}

// 使用 Hook
function DiagramComponent({ code }: { code: string }) {
  const { svg, loading, error } = useMermaid(code, 'github-light');

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;

  return <div dangerouslySetInnerHTML={{ __html: svg }} />;
}
```

#### 範例 5：Vue 3 Composable

```typescript
import { ref, watch } from 'vue';
import { renderMermaid } from 'beautiful-mermaid';

export function useMermaid(code: string, theme: string = 'tokyo-night') {
  const svg = ref('');
  const loading = ref(true);
  const error = ref<string | null>(null);

  const render = async () => {
    loading.value = true;
    error.value = null;

    try {
      svg.value = await renderMermaid(code, { theme });
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error';
    } finally {
      loading.value = false;
    }
  };

  watch([() => code, () => theme], render, { immediate: true });

  return { svg, loading, error };
}
```

#### 範例 6：Express.js API 端點

```javascript
import express from 'express';
import { renderMermaid } from 'beautiful-mermaid';

const app = express();
app.use(express.json());

app.post('/api/render', async (req, res) => {
  const { code, theme = 'tokyo-night' } = req.body;

  if (!code) {
    return res.status(400).json({ error: 'Missing code' });
  }

  try {
    const svg = await renderMermaid(code, { theme });
    res.setHeader('Content-Type', 'image/svg+xml');
    res.send(svg);
  } catch (error) {
    res.status(500).json({
      error: 'Rendering failed',
      message: error.message,
    });
  }
});

app.listen(3000, () => {
  console.log('Server running on http://localhost:3000');
});
```

#### 範例 7：快取優化

```javascript
import { renderMermaid } from 'beautiful-mermaid';

const cache = new Map();

async function renderWithCache(code, theme = 'tokyo-night') {
  const key = `${code}:${theme}`;

  if (cache.has(key)) {
    console.log('✅ Cache hit');
    return cache.get(key);
  }

  console.log('🔄 Rendering...');
  const svg = await renderMermaid(code, { theme });
  cache.set(key, svg);

  // 限制快取大小
  if (cache.size > 100) {
    const firstKey = cache.keys().next().value;
    cache.delete(firstKey);
  }

  return svg;
}
```

#### 範例 8：ASCII 渲染（終端預覽）

```javascript
import { renderMermaidAscii } from 'beautiful-mermaid';

const code = `
graph TD
    A --> B
    B --> C
`;

const ascii = await renderMermaidAscii(code);
console.log(ascii);

// 輸出範例：
//     A
//     |
//     v
//     B
//     |
//     v
//     C
```

---

## 效能比較

| 指標 | CLI | API |
|------|-----|-----|
| **啟動時間** | ~100-200ms（Node 進程啟動） | ~0ms（已載入） |
| **記憶體使用** | 每次執行獨立 | 共享記憶體 |
| **適合批量** | ✅ 透過腳本 | ✅ 程式化迴圈 |
| **快取** | ❌ 需要自己實作檔案快取 | ✅ 易於實作記憶體快取 |
| **除錯** | 簡單（命令列輸出） | 較複雜（需要日誌系統） |

---

## 選擇建議

### 選擇 CLI 如果：
1. 你只需要渲染幾個靜態圖表
2. 你在使用 CI/CD 流程
3. 你偏好命令列工作流程
4. 你不需要即時渲染或主題切換

### 選擇 API 如果：
1. 你在建構 Web 應用或 API
2. 你需要動態渲染使用者內容
3. 你需要即時主題切換
4. 你需要效能優化和快取
5. 你需要複雜的條件邏輯

### 混合使用：
- **開發階段**：使用 CLI 快速測試和驗證
- **生產環境**：使用 API 提供動態渲染
- **CI/CD**：使用 CLI 自動渲染靜態資產
- **文檔**：使用 CLI 預先渲染，嵌入 Markdown

---

## 常見問題

**Q: 可以在瀏覽器中使用 API 嗎？**
A: 可以，beautiful-mermaid 支援瀏覽器環境。透過 CDN 或 bundler 載入即可。

**Q: CLI 和 API 渲染結果一樣嗎？**
A: 是的，使用相同參數會產生相同的 SVG 輸出。

**Q: 哪個更快？**
A: 單次渲染 API 更快（無需啟動進程）。批量任務則差異不大。

**Q: 可以混合使用嗎？**
A: 可以，CLI 用於靜態渲染，API 用於動態需求是常見做法。

**Q: CLI 支援管道（pipe）嗎？**
A: 目前不支援，需要使用檔案輸入輸出。如需管道支援，使用 API。
