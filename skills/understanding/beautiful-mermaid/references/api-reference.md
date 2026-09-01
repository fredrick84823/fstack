# Beautiful Mermaid API Reference

Complete API documentation for the beautiful-mermaid package.

---

## Installation

```bash
npm install beautiful-mermaid
# or
pnpm add beautiful-mermaid
# or
bun add beautiful-mermaid
# or (global)
npm install -g beautiful-mermaid
```

---

## Core Functions

### `renderMermaidSVG(text, options?)` — primary API

Render a Mermaid diagram to SVG. **Synchronous** (ELK runs inline, no flash).

**Signature:**
```typescript
function renderMermaidSVG(
  text: string,
  options?: RenderOptions
): string
```

**Parameters:**

- `text` (string, required): Mermaid source code
- `options` (RenderOptions, optional): Rendering configuration

**Returns:** string - self-contained SVG

**Async variant:** `renderMermaidSVGAsync(text, options?): Promise<string>`.

**Deprecated aliases:** `renderMermaid` (async) and `renderMermaidAscii` still exist for
backwards compatibility; do not use them in new code.

**Example:**
```javascript
import { renderMermaidSVG } from 'beautiful-mermaid';

const svg = renderMermaidSVG(`
  graph TD
    A[Start] --> B{Decision}
    B -->|Yes| C[Action]
    B -->|No| D[End]
`);
```

---

### `renderMermaidASCII(text, options?)`

Render a Mermaid diagram to ASCII/Unicode text. **Synchronous.**

**Signature:**
```typescript
function renderMermaidASCII(
  text: string,
  options?: AsciiRenderOptions
): string
```

**Parameters:**

- `text` (string, required): Mermaid source code
- `options` (AsciiRenderOptions, optional): ASCII rendering options

**Returns:** string - ASCII/Unicode diagram

**Example:**
```javascript
import { renderMermaidASCII } from 'beautiful-mermaid';

// Unicode output (prettier)
const unicode = renderMermaidASCII(`graph LR; A --> B`);

// ASCII output (maximum compatibility)
const ascii = renderMermaidASCII(`graph LR; A --> B`, { 
  useAscii: true 
});
```

---

### `fromShikiTheme(theme)`

Extract diagram colors from a Shiki theme object.

**Signature:**
```typescript
function fromShikiTheme(theme: ShikiTheme): DiagramColors
```

**Parameters:**

- `theme` (ShikiTheme, required): Shiki theme object

**Returns:** DiagramColors - Color configuration for beautiful-mermaid

**Example:**
```javascript
import { getSingletonHighlighter } from 'shiki';
import { renderMermaidSVG, fromShikiTheme } from 'beautiful-mermaid';

const highlighter = await getSingletonHighlighter({
  themes: ['vitesse-dark', 'rose-pine']
});

const colors = fromShikiTheme(highlighter.getTheme('vitesse-dark'));
const svg = renderMermaidSVG(diagram, colors);
```

**Theme color mapping:**
- `editor.background` → `bg`
- `editor.foreground` → `fg`
- `editorLineNumber.foreground` → `line`
- `focusBorder` → `accent`
- `editorLineNumber.foreground` (muted) → `muted`
- `editor.selectionBackground` → `surface`
- `editorWidget.border` → `border`

---

## Type Definitions

### RenderOptions

Configuration for SVG rendering.

```typescript
interface RenderOptions {
  // Required colors (Mono Mode)
  bg?: string;          // Background color (default: '#FFFFFF')
  fg?: string;          // Foreground color (default: '#27272A')
  
  // Optional enrichment colors
  line?: string;        // Edge/connector color
  accent?: string;      // Arrow heads, highlights
  muted?: string;       // Secondary text, labels
  surface?: string;     // Node fill color
  border?: string;      // Node stroke color
  
  // Typography
  font?: string;        // Font family (default: 'Inter')

  // Layout spacing
  padding?: number;           // Canvas padding (default: 40)
  nodeSpacing?: number;       // Sibling spacing (default: 24)
  layerSpacing?: number;      // Layer spacing (default: 40)
  componentSpacing?: number;  // Disconnected components (default: nodeSpacing)

  // Output
  transparent?: boolean;// No background on the SVG root (default: false)
  interactive?: boolean;// Hover tooltips, xychart only (default: false)
}
```

There is **no** `theme`, `fontFamily`, `scale`, `width` or `height` option.
Select a theme by spreading `THEMES[name]` into the options object.

**Defaults:**
```javascript
{
  bg: '#FFFFFF',
  fg: '#27272A',
  font: 'Inter',
  padding: 40,
  nodeSpacing: 24,
  layerSpacing: 40,
  transparent: false
}
```

**Skill default (`craft` preset):**
```javascript
{ ...THEMES['zinc-light'], transparent: true, font: 'Inter',
  padding: 40, nodeSpacing: 28, layerSpacing: 48 }
```

**Mono Mode Example:**
```javascript
renderMermaidSVG(diagram, {
  bg: '#1a1b26',
  fg: '#a9b1d6'
});
// All other colors auto-derived via color-mix()
```

**Enriched Mode Example:**
```javascript
renderMermaidSVG(diagram, {
  bg: '#1a1b26',
  fg: '#a9b1d6',
  line: '#3d59a1',
  accent: '#7aa2f7',
  muted: '#565f89',
  surface: '#292e42',
  border: '#3d59a1'
});
```

---

### AsciiRenderOptions

Configuration for ASCII/Unicode rendering.

```typescript
interface AsciiRenderOptions {
  useAscii?: boolean;       // Use pure ASCII (default: false, uses Unicode)
  paddingX?: number;        // Horizontal padding (default: 5)
  paddingY?: number;        // Vertical padding (default: 5)
  boxBorderPadding?: number;// Padding inside boxes (default: 1)
  colorMode?: 'none' | 'auto' | 'ansi16' | 'ansi256' | 'truecolor' | 'html'; // default 'auto'
  theme?: Partial<AsciiTheme>; // ASCII color theme
}
```

**Defaults:**
```javascript
{
  useAscii: false,
  paddingX: 5,
  paddingY: 5,
  boxBorderPadding: 1
}
```

**Unicode vs ASCII:**

Unicode (default):
```
┌───┐     ┌───┐
│ A │────►│ B │
└───┘     └───┘
```

ASCII (useAscii: true):
```
+---+     +---+
| A |---->| B |
+---+     +---+
```

---

### DiagramColors

Color configuration object.

```typescript
interface DiagramColors {
  bg: string;      // Required: Background
  fg: string;      // Required: Foreground
  line?: string;   // Optional: Edges
  accent?: string; // Optional: Accents
  muted?: string;  // Optional: Muted text
  surface?: string;// Optional: Surfaces
  border?: string; // Optional: Borders
}
```

---

## Constants

### `THEMES`

Object containing all 15 built-in themes.

**Signature:**
```typescript
const THEMES: Record<string, DiagramColors>
```

**Available themes:**
- `zinc-light`
- `zinc-dark`
- `tokyo-night`
- `tokyo-night-storm`
- `tokyo-night-light`
- `catppuccin-mocha`
- `catppuccin-latte`
- `nord`
- `nord-light`
- `dracula`
- `github-light`
- `github-dark`
- `solarized-light`
- `solarized-dark`
- `one-dark`

**Example:**
```javascript
import { renderMermaidSVG, THEMES } from 'beautiful-mermaid';

const svg = renderMermaidSVG(diagram, THEMES['tokyo-night']);
```

---

### `DEFAULTS`

Default color configuration.

**Signature:**
```typescript
const DEFAULTS: { 
  bg: string;  // '#FFFFFF'
  fg: string;  // '#27272A'
}
```

**Example:**
```javascript
import { renderMermaidSVG, DEFAULTS } from 'beautiful-mermaid';

const svg = renderMermaidSVG(diagram, DEFAULTS);
```

---

## Browser Usage

### Via CDN (unpkg)

```html
<script src="https://unpkg.com/beautiful-mermaid/dist/beautiful-mermaid.browser.global.js"></script>
<script>
  const { renderMermaidSVG, THEMES } = beautifulMermaid;
  
  renderMermaidSVG('graph TD; A-->B', THEMES['tokyo-night'])
    .then(svg => {
      document.getElementById('diagram').innerHTML = svg;
    });
</script>
```

### Via CDN (ESM only)

The package ships ESM (`dist/index.js`); there is no browser global bundle.

```html
<script type="module">
  import { renderMermaidSVG, THEMES } from 'https://cdn.jsdelivr.net/npm/beautiful-mermaid@1.1.3/+esm';
  document.getElementById('d').innerHTML =
    renderMermaidSVG('graph TD; A-->B', { ...THEMES['zinc-light'], transparent: true });
</script>
```

### Available exports

- `renderMermaidSVG`, `renderMermaidSVGAsync`, `renderMermaidASCII`
- `parseMermaid`
- `THEMES`, `DEFAULTS`, `fromShikiTheme`
- deprecated: `renderMermaid`, `renderMermaidAscii`, `renderMermaidSync`

---

## Advanced Usage

### Custom Theme with Transparency

```javascript
const customTheme = {
  bg: '#1a1b26',
  fg: '#a9b1d6',
  transparent: true  // Makes background transparent
};

const svg = renderMermaidSVG(diagram, customTheme);
```

### Dynamic Theme Switching

Beautiful-mermaid uses CSS custom properties, allowing live theme changes without re-rendering:

```javascript
// Initial render
const svg = renderMermaidSVG(diagram, THEMES['tokyo-night']);
document.getElementById('diagram').innerHTML = svg;

// Later, switch theme dynamically
const svgElement = document.querySelector('#diagram svg');
svgElement.style.setProperty('--bg', '#282a36');
svgElement.style.setProperty('--fg', '#f8f8f2');
svgElement.style.setProperty('--accent', '#bd93f9');
// Diagram updates immediately!
```

### Using with Shiki Themes

```javascript
import { getSingletonHighlighter } from 'shiki';
import { renderMermaidSVG, fromShikiTheme } from 'beautiful-mermaid';

// Load highlighter with desired themes
const highlighter = await getSingletonHighlighter({
  themes: ['vitesse-dark', 'rose-pine', 'material-theme-darker']
});

// Extract colors from any loaded theme
const vitesseColors = fromShikiTheme(
  highlighter.getTheme('vitesse-dark')
);

const rosePineColors = fromShikiTheme(
  highlighter.getTheme('rose-pine')
);

// Use extracted colors
const svg1 = renderMermaidSVG(diagram, vitesseColors);
const svg2 = renderMermaidSVG(diagram, rosePineColors);
```

### Font Customization

```javascript
const svg = renderMermaidSVG(diagram, {
  ...THEMES['tokyo-night'],
  font: 'JetBrains Mono, monospace'
});
```

---

## Error Handling

```javascript
try {
  const svg = renderMermaidSVG(mermaidCode, options);
  console.log('Success:', svg);
} catch (error) {
  if (error.message.includes('Parse error')) {
    console.error('Invalid Mermaid syntax:', error.message);
  } else {
    console.error('Rendering failed:', error);
  }
}
```

Common errors:
- **Parse error**: Invalid Mermaid syntax
- **Unsupported diagram type**: Diagram type not supported by beautiful-mermaid
- **Invalid color**: Color value not in valid format

---

## Performance Considerations

### Rendering Speed

Beautiful-mermaid is optimized for speed:
- **100+ diagrams in under 500ms** (typical workload)
- Pure TypeScript, no DOM dependencies
- Minimal bundle size

### Batch Rendering

```javascript
const diagrams = [diagram1, diagram2, diagram3];
const theme = THEMES['tokyo-night'];

const svgs = await Promise.all(
  diagrams.map(d => renderMermaidSVG(d, theme))
);
```

### Memory Efficiency

For large-scale rendering, process in chunks:

```javascript
async function renderInChunks(diagrams, theme, chunkSize = 10) {
  const results = [];
  for (let i = 0; i < diagrams.length; i += chunkSize) {
    const chunk = diagrams.slice(i, i + chunkSize);
    const svgs = await Promise.all(
      chunk.map(d => renderMermaidSVG(d, theme))
    );
    results.push(...svgs);
  }
  return results;
}
```

---

## Compatibility

### Supported Diagram Types

- ✅ Flowcharts (`graph`, `flowchart`)
- ✅ State Diagrams (`stateDiagram-v2`)
- ✅ Sequence Diagrams (`sequenceDiagram`)
- ✅ Class Diagrams (`classDiagram`)
- ✅ ER Diagrams (`erDiagram`)

### Not Supported

- ❌ Gantt charts
- ❌ Pie charts
- ❌ Git graphs
- ❌ User journey diagrams
- ❌ Timeline diagrams

Use the official Mermaid library for unsupported diagram types.

### Node.js

- Minimum: Node.js 16+
- Recommended: Node.js 18+

### Browsers

- Modern browsers with ES modules support
- No IE11 support (uses modern JavaScript)

---

## TypeScript Support

Beautiful-mermaid is written in TypeScript and includes type definitions.

```typescript
import {
  renderMermaidSVG,
  renderMermaidASCII,
  type RenderOptions,
  type DiagramColors,
  THEMES
} from 'beautiful-mermaid';

const options: RenderOptions = {
  ...THEMES['zinc-light'],
  transparent: true,
  nodeSpacing: 28,
  layerSpacing: 48
};

const svg: string = renderMermaidSVG('graph TD; A-->B', options);
```
