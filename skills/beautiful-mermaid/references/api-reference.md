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

### `renderMermaid(text, options?)`

Render a Mermaid diagram to SVG.

**Signature:**
```typescript
async function renderMermaid(
  text: string,
  options?: RenderOptions
): Promise<string>
```

**Parameters:**

- `text` (string, required): Mermaid source code
- `options` (RenderOptions, optional): Rendering configuration

**Returns:** Promise<string> - SVG string

**Example:**
```javascript
import { renderMermaid } from 'beautiful-mermaid';

const svg = await renderMermaid(`
  graph TD
    A[Start] --> B{Decision}
    B -->|Yes| C[Action]
    B -->|No| D[End]
`);
```

---

### `renderMermaidAscii(text, options?)`

Render a Mermaid diagram to ASCII/Unicode text. **Synchronous.**

**Signature:**
```typescript
function renderMermaidAscii(
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
import { renderMermaidAscii } from 'beautiful-mermaid';

// Unicode output (prettier)
const unicode = renderMermaidAscii(`graph LR; A --> B`);

// ASCII output (maximum compatibility)
const ascii = renderMermaidAscii(`graph LR; A --> B`, { 
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
import { renderMermaid, fromShikiTheme } from 'beautiful-mermaid';

const highlighter = await getSingletonHighlighter({
  themes: ['vitesse-dark', 'rose-pine']
});

const colors = fromShikiTheme(highlighter.getTheme('vitesse-dark'));
const svg = await renderMermaid(diagram, colors);
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
  
  // Other options
  font?: string;        // Font family (default: 'Inter')
  transparent?: boolean;// Transparent background (default: false)
}
```

**Defaults:**
```javascript
{
  bg: '#FFFFFF',
  fg: '#27272A',
  font: 'Inter',
  transparent: false
}
```

**Mono Mode Example:**
```javascript
await renderMermaid(diagram, {
  bg: '#1a1b26',
  fg: '#a9b1d6'
});
// All other colors auto-derived via color-mix()
```

**Enriched Mode Example:**
```javascript
await renderMermaid(diagram, {
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
import { renderMermaid, THEMES } from 'beautiful-mermaid';

const svg = await renderMermaid(diagram, THEMES['tokyo-night']);
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
import { renderMermaid, DEFAULTS } from 'beautiful-mermaid';

const svg = await renderMermaid(diagram, DEFAULTS);
```

---

## Browser Usage

### Via CDN (unpkg)

```html
<script src="https://unpkg.com/beautiful-mermaid/dist/beautiful-mermaid.browser.global.js"></script>
<script>
  const { renderMermaid, THEMES } = beautifulMermaid;
  
  renderMermaid('graph TD; A-->B', THEMES['tokyo-night'])
    .then(svg => {
      document.getElementById('diagram').innerHTML = svg;
    });
</script>
```

### Via CDN (jsDelivr)

```html
<script src="https://cdn.jsdelivr.net/npm/beautiful-mermaid/dist/beautiful-mermaid.browser.global.js"></script>
```

### Available exports

The global `beautifulMermaid` object includes:
- `renderMermaid`
- `renderMermaidAscii`
- `THEMES`
- `DEFAULTS`
- `fromShikiTheme`

---

## Advanced Usage

### Custom Theme with Transparency

```javascript
const customTheme = {
  bg: '#1a1b26',
  fg: '#a9b1d6',
  transparent: true  // Makes background transparent
};

const svg = await renderMermaid(diagram, customTheme);
```

### Dynamic Theme Switching

Beautiful-mermaid uses CSS custom properties, allowing live theme changes without re-rendering:

```javascript
// Initial render
const svg = await renderMermaid(diagram, THEMES['tokyo-night']);
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
import { renderMermaid, fromShikiTheme } from 'beautiful-mermaid';

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
const svg1 = await renderMermaid(diagram, vitesseColors);
const svg2 = await renderMermaid(diagram, rosePineColors);
```

### Font Customization

```javascript
const svg = await renderMermaid(diagram, {
  ...THEMES['tokyo-night'],
  font: 'JetBrains Mono, monospace'
});
```

---

## Error Handling

```javascript
try {
  const svg = await renderMermaid(mermaidCode, options);
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
  diagrams.map(d => renderMermaid(d, theme))
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
      chunk.map(d => renderMermaid(d, theme))
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
  renderMermaid, 
  renderMermaidAscii,
  RenderOptions,
  DiagramColors,
  THEMES
} from 'beautiful-mermaid';

const options: RenderOptions = {
  bg: '#1a1b26',
  fg: '#a9b1d6',
  transparent: false
};

const svg: string = await renderMermaid('graph TD; A-->B', options);
```
