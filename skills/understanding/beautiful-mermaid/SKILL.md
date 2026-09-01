---
name: beautiful-mermaid
description: Render restrained, Craft-style Mermaid diagrams with the beautiful-mermaid npm package. Use when the user asks to "create a diagram", "render a Mermaid diagram", "make a beautiful/styled diagram", or wants SVG/ASCII diagram output. Supports flowchart, state, sequence, class, ER and XY chart diagrams; default output is monochrome, transparent, Inter.
disable-model-invocation: true
---

# Beautiful Mermaid

Render Mermaid diagrams through `beautiful-mermaid` 1.1.3. Default output matches the
package's own Craft showcase (<https://agents.craft.do/mermaid>): monochrome zinc,
transparent background, Inter, ELK orthogonal routing.

## Core model

```text
.mmd source (semantics only)
        │
        ▼
preset (presentation: colors, spacing, font, transparency)
        │
        ▼
renderMermaidSVG()  /  renderMermaidASCII()      ← single render path
        │
        ├─ .svg   embed anywhere; container owns the background
        ├─ .html  interactive pan/zoom viewer (default) or --static
        └─ ascii  terminal preview
```

Rule: diagram sources never carry colors. Presentation belongs to the preset.

## Quick start

```bash
# 1. verify / install (deterministic: npm ci when a lockfile exists)
node scripts/setup_check.js            # verify
node scripts/setup_check.js --install  # install then verify

# 2. render (default preset: craft)
node scripts/render_mermaid.js -i diagram.mmd -o diagram.svg

# dark container
node scripts/render_mermaid.js -i diagram.mmd -o diagram.svg -p craft-dark

# fully offline SVG (system fonts, no @import)
node scripts/render_mermaid.js -i diagram.mmd -o diagram.svg --offline

# standalone interactive HTML viewer (pan/zoom, offline)
node scripts/render_mermaid.js -i diagram.mmd -o diagram.html -f html

# static HTML (no script)
node scripts/render_mermaid.js -i diagram.mmd -o diagram.html -f html --static

# terminal preview
node scripts/render_mermaid.js -i diagram.mmd -f ascii

# stdin → stdout
cat diagram.mmd | node scripts/render_mermaid.js -i - > diagram.svg
```

## Presets

| Preset | Colors | Background | Spacing | Use |
|---|---|---|---|---|
| `craft` (default) | `zinc-light` `#FFFFFF/#27272A` | transparent | 40 / 28 / 48 | docs, light pages, embedding |
| `craft-dark` | `zinc-dark` | transparent | 40 / 28 / 48 | dark pages, dark slides |
| `legacy` | `tokyo-night` | opaque | 40 | reproducing pre-refresh output |

Spacing = `padding / nodeSpacing / layerSpacing`.

`--theme <name>` is an explicit override kept for backwards compatibility; it swaps colors
but keeps preset spacing. Prefer presets. Themes: see [themes.md](references/themes.md).

## Authoring rules

1. Pick one reading direction: `LR` for pipelines/flows, `TD` for decisions/state.
2. Short noun/verb labels. Protocols, events, formats, conditions go on **edge labels**.
3. At most 2–3 shapes per diagram; shape carries meaning, not decoration.
4. Monochrome by default. Add an accent only for failure, risk, or one highlighted path.
5. No emoji, no inline `style`/`fill:` in `.mmd` files (tests enforce this).
6. 6–10 nodes, one concept per diagram. If too wide, split — do not shrink type.
7. Review at final render width before shipping.

Reference fixture: `assets/examples/hero.mmd` reproduces the Craft hero exactly
(viewBox `0 0 1181.938 182.5`, 9 nodes, 9 edges, 4 edge labels).

```text
stateDiagram-v2
  direction LR
  [*] --> Input
  Input --> Parse: DSL
  Parse --> Layout: AST
  Layout --> SVG: Vector
  Layout --> ASCII: Text
  SVG --> Theme
  ASCII --> Theme
  Theme --> Output
  Output --> [*]
```

## Diagram families (6, per package 1.1.3)

| Family | Header | Use |
|---|---|---|
| Flowchart | `graph TD` / `flowchart LR` | process, decisions |
| State | `stateDiagram-v2` | lifecycle, state machines |
| Sequence | `sequenceDiagram` | request/response over time |
| Class | `classDiagram` | type structure |
| ER | `erDiagram` | data model |
| XY chart | `xychart-beta` | line/bar series |

Node shapes (14): `rectangle`, `rounded`, `diamond`, `stadium`, `circle`, `subroutine`,
`doublecircle`, `hexagon`, `cylinder`, `asymmetric`, `trapezoid`, `trapezoid-alt`,
`state-start`, `state-end`. Details: [diagram-types.md](references/diagram-types.md).

Note: keep the diagram header on the first line — `%%` comments before it break detection.

## API (programmatic)

```js
import { renderMermaidSVG, renderMermaidASCII, THEMES } from 'beautiful-mermaid';

const CRAFT_PRESET = {
  ...THEMES['zinc-light'],   // bg #FFFFFF, fg #27272A
  transparent: true,
  font: 'Inter',
  padding: 40,
  nodeSpacing: 28,
  layerSpacing: 48,
};

const svg = renderMermaidSVG(source, CRAFT_PRESET);       // synchronous, no flash
const art = renderMermaidASCII(source, { colorMode: 'none' });
```

Real `RenderOptions`: `bg`, `fg`, `line`, `accent`, `muted`, `surface`, `border`, `font`,
`padding`, `nodeSpacing`, `layerSpacing`, `componentSpacing`, `transparent`,
`interactive` (xychart only). There is no `theme`, `fontFamily`, `scale`, `width` or
`height` option. `renderMermaid` / `renderMermaidAscii` are deprecated aliases;
`renderMermaidSVGAsync` exists for async contexts.

Skill-side helpers live in `scripts/lib/presets.js` (`renderSVG`, `renderASCII`,
`resolveRenderOptions`, `stripRemoteFontImports`).

Full reference: [api-reference.md](references/api-reference.md).

## HTML viewers

Two shells share one canonical implementation in `scripts/lib/html.js`:

- **Standalone**: `-f html` creates a full-window single-diagram viewer. `--static` is only
  for an explicit static/no-JS/print-only request.
- **Embedded multi-instance**: doc pages compose `embeddedFigure()` fragments, include
  `embeddedViewerCSS()` and `embeddedViewerScript()` exactly once, or call
  `embeddedDocument()` for a complete self-contained page. Never copy the runtime into a
  downstream skill.

Every embedded figure uses classes/data attributes, namespaces SVG-local IDs, auto-fits, and
owns independent `scale` / `baked` / `tx` / `ty` state. Controls are `−`, `+`, `Fit`, `1:1`.
Desktop drag pans; Ctrl/Cmd+wheel and two-finger pinch zoom. Plain wheel and one-finger mobile
gestures remain page scrolling. Keyboard shortcuts (`f`, `0`, `+`, `−`) affect only the
focused viewer. Static SVG remains readable with JavaScript disabled and is used for print.

The automation contract is `window.__mermaidViewers`, an array in document order. Each entry
provides `state()`, `fit()`, `reset()`, `zoomAt()`, `zoomBy()`, and `bake()`. Standalone output
also aliases the first entry as `window.__mermaidViewer` for compatibility.

The sharp bake + residual strategy, canonical markup/API example, and integration checks are
disclosed in [integration-guide.md](references/integration-guide.md#embedded-multi-instance-viewer).

## Scripts

| Script | Purpose |
|---|---|
| `scripts/setup_check.js [--install]` | verify package + API + presets; `--install` runs `npm ci` |
| `scripts/render_mermaid.js` | CLI renderer (svg / html / ascii) |
| `scripts/build_showcase.js` | regenerate the preset gallery |
| `scripts/build_embedded_showcase.js` | regenerate the canonical two-viewer integration fixture |
| `assets/examples/batch-render.sh` | batch render a directory (`<in> <out> <preset> <format>`) |

CLI options: `-i/--input` (`-` = stdin), `-o/--output` (omit → stdout), `-p/--preset`,
`-t/--theme`, `-f/--format svg|html|ascii`, `--interactive`, `--static`,
`--transparent`, `--opaque`, `--offline`,
`--font`, `--padding`, `--node-spacing`, `--layer-spacing`, `--ascii-chars`,
`--list-presets`, `--list-themes`, `-h`.

## Examples

- `assets/examples/hero.mmd` — Craft reference fixture
- `flowchart.mmd`, `state.mmd`, `sequence.mmd`, `class.mmd`, `er.mmd`, `xychart.mmd` — one per family
- `advanced-flowchart-subgraph.mmd` — subgraph staging, no color coding
- `all-diagrams-showcase.html` — generated, offline, package-rendered, preset switcher
- `embedded-viewer-showcase.html` — self-contained, two independent embedded viewers
- `markdown-integration-example.md` — embedding patterns

## Tests

```bash
npm test                       # semantic SVG assertions + screenshot regression
npm run test:update-baselines  # accept intended visual changes
```

Covered: rendering and CLI contracts plus embedded ID namespacing, independent state and
controls, modifier/plain wheel policy, drag, fit/reset, focused keyboard, mobile touch policy,
print/no-JS fallback, 390px overflow, automation API, and Chromium screenshots.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `beautiful-mermaid is not installed` | `node scripts/setup_check.js --install` |
| `Invalid mermaid header` | header must be the first line; no leading `%%` comments |
| `Unknown preset` / `Unknown theme` | `--list-presets` / `--list-themes` |
| Diagram too wide | split it; do not reduce font size |
| Fonts missing offline | render with `--offline` |
| Screenshot test fails | inspect `tests/baselines/*.actual.png`, then update baselines if intended |

## Reference docs

- [themes.md](references/themes.md) — 15 themes, color specs, custom themes
- [diagram-types.md](references/diagram-types.md) — syntax for all 6 families
- [api-reference.md](references/api-reference.md) — API and types
- [integration-guide.md](references/integration-guide.md) — React/Vue/CI usage
- [cli-vs-api-guide.md](references/cli-vs-api-guide.md) — when to use which
