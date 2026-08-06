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

# interactive HTML viewer (pan/zoom, offline)
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

## HTML output

`-f html` produces an **interactive viewer** by default. Zero dependencies, works from
`file://`, no CDN, no remote fonts when combined with `--offline`.

| Interaction | Behavior |
|---|---|
| wheel / trackpad pinch | zoom anchored at the cursor, 0.1x–8x |
| left-drag | pan (pointer events + `setPointerCapture`) |
| double-click | reset to 1:1 |
| `f` | fit to window |
| `0` | reset to 1:1 |
| `+` / `-` | zoom about the viewport center |
| HUD (top-right) | `−` / percentage / `+` / `Fit` / `1:1` |

The diagram is auto-fitted on load; the hint strip sits bottom-left.

**Sharpness:** zoom is *baked* into the SVG's real layout size (`svg.style.width/height`,
padding scaled to match), not only applied as a CSS `transform: scale()`. During a gesture a
residual `scale(scale / baked)` transform gives instant feedback, then a ~90 ms debounce
re-bakes so the browser re-rasterizes vectors at the new size. `will-change: transform` is
applied only while dragging. See
[integration-guide.md](references/integration-guide.md#為何-css-transform-縮放會模糊) for the rationale.

Use `--static` when the HTML is a build input rather than something a human pans around:
embedding into another page, further post-processing, PDF/print pipelines, or diffing HTML text.

Automation hook: the viewer exposes `window.__mermaidViewer`
(`state()`, `fit()`, `reset()`, `zoomAt()`, `bake()`).

## Scripts

| Script | Purpose |
|---|---|
| `scripts/setup_check.js [--install]` | verify package + API + presets; `--install` runs `npm ci` |
| `scripts/render_mermaid.js` | CLI renderer (svg / html / ascii) |
| `scripts/build_showcase.js` | regenerate `assets/examples/all-diagrams-showcase.html` |
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
- `markdown-integration-example.md` — embedding patterns

## Tests

```bash
npm test                       # semantic SVG assertions + screenshot regression
npm run test:update-baselines  # accept intended visual changes
```

Covered: preset defaults, theme override precedence, hero structural parity, transparency,
offline output, all six families, fixture hygiene (no emoji/inline colors), showcase
self-containment, showcase freshness, CLI behavior, Chromium screenshot baselines
(`tests/baselines/`, auto-skipped when no Chromium is present).

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
