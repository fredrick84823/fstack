# Beautiful Mermaid Themes Reference

Complete reference for all 15 built-in themes in beautiful-mermaid.

## 快速主題選擇流程

### 根據用途選擇

**文檔與報告**
- 企業正式 → `zinc-light`（最專業）
- GitHub 相關 → `github-light` / `github-dark`
- 溫暖邀請 → `catppuccin-latte` / `catppuccin-mocha`
- 護眼長文 → `solarized-light` / `solarized-dark`

**技術文檔與開發**
- 標準開發者 → `tokyo-night`（預設，最推薦）
- VS Code 用戶 → `one-dark`
- 涼爽專業 → `nord` / `nord-light`

**演示與培訓**
- 高能見度 → `dracula`
- 北極靈感 → `nord`（深）/ `nord-light`（淺）
- 暖色親近感 → `catppuccin-mocha`

### 決策矩陣

| 情境 | 推薦主題（淺色） | 推薦主題（深色） |
|------|----------------|----------------|
| **首次使用** | `github-light` | `tokyo-night` ⭐ |
| **企業報告** | `zinc-light` | `zinc-dark` |
| **開源專案** | `github-light` | `github-dark` |
| **技術演示** | `catppuccin-latte` | `catppuccin-mocha` |
| **長時間閱讀** | `solarized-light` | `nord` |
| **程式碼相關** | `tokyo-night-light` | `one-dark` |

---

## Theme Color Structure

Each theme consists of:
- **bg** (background): Base background color
- **fg** (foreground): Primary text and line color
- **line** (optional): Edge/connector color
- **accent** (optional): Arrow heads, highlights
- **muted** (optional): Secondary text, labels
- **surface** (optional): Node fill color
- **border** (optional): Node stroke color

If optional colors aren't provided, they are derived from `bg` and `fg` using `color-mix()`.

---

## Light Themes

### zinc-light
**Best for:** Professional documents, reports, clean presentations

```javascript
{
  bg: '#FFFFFF',
  fg: '#27272A',
  line: '#52525B',
  accent: '#3F3F46',
  muted: '#71717A',
  surface: '#FAFAFA',
  border: '#E4E4E7'
}
```

**Characteristics:** Neutral, high contrast, professional

---

### tokyo-night-light
**Best for:** Modern interfaces, technical documentation

```javascript
{
  bg: '#d5d6db',
  fg: '#34548a',
  line: '#565a6e',
  accent: '#8c4351',
  muted: '#9699a3',
  surface: '#cbccd1',
  border: '#a8aecb'
}
```

**Characteristics:** Soft colors, good readability, technical feel

---

### catppuccin-latte
**Best for:** Warm, inviting presentations

```javascript
{
  bg: '#eff1f5',
  fg: '#8839ef',
  line: '#dc8a78',
  accent: '#d20f39',
  muted: '#9ca0b0',
  surface: '#e6e9ef',
  border: '#acb0be'
}
```

**Characteristics:** Warm palette, unique accent colors

---

### nord-light
**Best for:** Cool, professional diagrams

```javascript
{
  bg: '#eceff4',
  fg: '#5e81ac',
  line: '#81a1c1',
  accent: '#88c0d0',
  muted: '#d8dee9',
  surface: '#e5e9f0',
  border: '#d8dee9'
}
```

**Characteristics:** Cool blues, Arctic-inspired

---

### github-light
**Best for:** GitHub-style documentation, READMEs

```javascript
{
  bg: '#ffffff',
  fg: '#0969da',
  line: '#6e7781',
  accent: '#1f883d',
  muted: '#656d76',
  surface: '#f6f8fa',
  border: '#d0d7de'
}
```

**Characteristics:** Familiar GitHub aesthetic

---

### solarized-light
**Best for:** Low eye strain, long reading sessions

```javascript
{
  bg: '#fdf6e3',
  fg: '#268bd2',
  line: '#2aa198',
  accent: '#859900',
  muted: '#93a1a1',
  surface: '#eee8d5',
  border: '#93a1a1'
}
```

**Characteristics:** Scientifically designed color palette

---

## Dark Themes

### zinc-dark
**Best for:** Dark mode applications, modern UIs

```javascript
{
  bg: '#18181B',
  fg: '#FAFAFA',
  line: '#A1A1AA',
  accent: '#D4D4D8',
  muted: '#71717A',
  surface: '#27272A',
  border: '#3F3F46'
}
```

**Characteristics:** Clean dark mode, high contrast

---

### tokyo-night (DEFAULT)
**Best for:** Developer tools, terminals, code-heavy diagrams

```javascript
{
  bg: '#1a1b26',
  fg: '#a9b1d6',
  line: '#3d59a1',
  accent: '#7aa2f7',
  muted: '#565f89',
  surface: '#292e42',
  border: '#3d59a1'
}
```

**Characteristics:** Popular developer theme, excellent contrast

---

### tokyo-night-storm
**Best for:** Alternative to tokyo-night with lighter background

```javascript
{
  bg: '#24283b',
  fg: '#a9b1d6',
  line: '#3d59a1',
  accent: '#7aa2f7',
  muted: '#565f89',
  surface: '#292e42',
  border: '#3d59a1'
}
```

**Characteristics:** Slightly lighter than tokyo-night

---

### catppuccin-mocha
**Best for:** Cozy, warm dark mode

```javascript
{
  bg: '#1e1e2e',
  fg: '#cba6f7',
  line: '#f38ba8',
  accent: '#fab387',
  muted: '#6c7086',
  surface: '#313244',
  border: '#585b70'
}
```

**Characteristics:** Warm dark palette, pastel accents

---

### nord
**Best for:** Arctic-inspired dark mode

```javascript
{
  bg: '#2e3440',
  fg: '#88c0d0',
  line: '#81a1c1',
  accent: '#5e81ac',
  muted: '#616e88',
  surface: '#3b4252',
  border: '#4c566a'
}
```

**Characteristics:** Cool blues and grays

---

### dracula
**Best for:** High contrast, vibrant colors

```javascript
{
  bg: '#282a36',
  fg: '#bd93f9',
  line: '#ff79c6',
  accent: '#50fa7b',
  muted: '#6272a4',
  surface: '#44475a',
  border: '#6272a4'
}
```

**Characteristics:** Vibrant purples and pinks

---

### github-dark
**Best for:** GitHub dark mode, developer documentation

```javascript
{
  bg: '#0d1117',
  fg: '#4493f8',
  line: '#7d8590',
  accent: '#3fb950',
  muted: '#8b949e',
  surface: '#161b22',
  border: '#30363d'
}
```

**Characteristics:** GitHub's official dark palette

---

### solarized-dark
**Best for:** Low eye strain in dark environments

```javascript
{
  bg: '#002b36',
  fg: '#268bd2',
  line: '#2aa198',
  accent: '#859900',
  muted: '#586e75',
  surface: '#073642',
  border: '#586e75'
}
```

**Characteristics:** Scientifically designed for comfort

---

### one-dark
**Best for:** Atom/VS Code users, familiar workflow

```javascript
{
  bg: '#282c34',
  fg: '#c678dd',
  line: '#61afef',
  accent: '#98c379',
  muted: '#5c6370',
  surface: '#2c323c',
  border: '#3e4451'
}
```

**Characteristics:** Popular editor theme, balanced colors

---

## Theme Selection Guide

### By Use Case

**Documentation & Reports:**
- Light: `zinc-light`, `github-light`
- Dark: `zinc-dark`, `github-dark`

**Technical/Developer Content:**
- Light: `tokyo-night-light`, `nord-light`
- Dark: `tokyo-night`, `one-dark`

**Presentations:**
- Light: `catppuccin-latte`, `solarized-light`
- Dark: `catppuccin-mocha`, `dracula`

**Extended Reading:**
- Light: `solarized-light`
- Dark: `solarized-dark`, `nord`

### By Aesthetic

**Minimal/Professional:** zinc-light, zinc-dark
**Warm/Cozy:** catppuccin-latte, catppuccin-mocha
**Cool/Arctic:** nord-light, nord
**Vibrant:** dracula, one-dark
**Familiar:** github-light, github-dark, tokyo-night

---

## Creating Custom Themes

Minimum required (Mono Mode):
```javascript
{
  bg: '#0f0f0f',
  fg: '#e0e0e0'
}
```

Enriched mode (optional enhancements):
```javascript
{
  bg: '#0f0f0f',
  fg: '#e0e0e0',
  accent: '#ff6b6b',    // Arrows, highlights
  line: '#666666',      // Connectors
  muted: '#888888',     // Labels
  surface: '#1a1a1a',   // Node backgrounds
  border: '#333333'     // Node borders
}
```

## Using Shiki Themes

Extract colors from any VS Code theme:

```javascript
import { getSingletonHighlighter } from 'shiki';
import { fromShikiTheme } from 'beautiful-mermaid';

const highlighter = await getSingletonHighlighter({
  themes: ['vitesse-dark']
});

const colors = fromShikiTheme(highlighter.getTheme('vitesse-dark'));
```

This gives access to hundreds of community themes from the Shiki ecosystem.
