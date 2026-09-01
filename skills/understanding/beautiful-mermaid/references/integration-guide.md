# Beautiful Mermaid Integration Guide

`SKILL.md` covers rendering decisions. Load this guide when composing package-rendered SVG into
HTML or a framework.

## Standalone viewer

Use the CLI when the diagram is the whole page:

```bash
node scripts/render_mermaid.js -i diagram.mmd -o diagram.html -f html --offline
```

This full-window shell uses the same runtime as embedded viewers. `--static` is an explicit
opt-out for no-JS or print/PDF-only output, not the default for embedding.

## Embedded multi-instance viewer

`scripts/lib/html.js` is the single source of truth. Render SVG through `renderSVG()`, build each
fragment with `embeddedFigure()`, and include `embeddedViewerCSS()` and
`embeddedViewerScript()` once per document:

```js
const { renderSVG } = require('./scripts/lib/presets');
const {
  embeddedFigure,
  embeddedViewerCSS,
  embeddedViewerScript,
} = require('./scripts/lib/html');

const architecture = await renderSVG(architectureSource, { offline: true });
const lifecycle = await renderSVG(lifecycleSource, { offline: true });

const figures = [
  embeddedFigure(architecture.svg, {
    key: 'architecture',
    label: 'System architecture',
    caption: 'Requests move from edge to application services.',
  }),
  embeddedFigure(lifecycle.svg, {
    key: 'lifecycle',
    label: 'Resource lifecycle',
    caption: 'Terminal states cannot transition back to active.',
  }),
].join('\n');

const html = `<!doctype html>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>${embeddedViewerCSS()}</style>
<main>${figures}</main>
<script>${embeddedViewerScript()}</script>`;
```

For a ready-made self-contained page, use `embeddedDocument([{ svg, label, caption }, ...])`.
`assets/examples/embedded-viewer-showcase.html` is the generated integration fixture; regenerate
it with `node scripts/build_embedded_showcase.js`.

### Contract

- Figure chrome uses `.mermaid-viewer*` classes and `data-*`; SVG-local IDs are namespaced.
- Each instance owns `scale`, `baked`, `tx`, and `ty`; controls and focused keyboard input stay
  local to that instance.
- Load auto-fits. Desktop pointer drag pans. Ctrl/Cmd+wheel and two-finger pinch zoom. Plain
  wheel and one-finger touch remain available to the page.
- Toolbar controls are `−`, `+`, `Fit`, and `1:1`, with accessible labels and focus styles.
- The inline SVG is present before JS runs. Print CSS hides controls and restores static flow.
- `window.__mermaidViewers` is an array in document order. Entries expose `state()`, `fit()`,
  `reset()`, `zoomAt(scale, x, y)`, `zoomBy(factor, x?, y?)`, and `bake()`.

Do not extract, copy, or rewrite the runtime in a downstream HTML generator. Call these builders
so bug fixes remain one-place edits.

## Why bake + residual stays sharp

A permanent `transform: scale()` may enlarge an already rasterized compositing layer. The runtime
instead bakes settled zoom into `svg.style.width/height` and scaled padding, forcing vector
re-rasterization. During a gesture it applies only the residual `scale / baked` transform, then
bakes after 90 ms. `will-change` exists only while dragging, and the SVG has `max-width: none`
inside its clipped canvas.

## Framework integration

Render the SVG during build/server work, not in the browser. Insert the fragment as trusted output
from `beautiful-mermaid`, include the canonical assets once at the page shell, and call
`window.MermaidEmbeddedViewer.init(container)` only when a framework mounts fragments after the
initial script ran. Do not initialize the same fragment twice; the runtime marks ready instances.

## Completion checks

A multi-diagram integration is complete only when automated assertions verify:

1. All document IDs are unique and `window.__mermaidViewers.length` equals the figure count.
2. Zoom/pan/control/keyboard changes to A leave B's `state()` unchanged.
3. Plain wheel is not canceled; Ctrl/Cmd+wheel is canceled and changes scale.
4. Fit and reset work; drag changes translation; only a focused viewer handles shortcuts.
5. At 390px, `scrollWidth <= clientWidth`; one-finger touch is not canceled.
6. With JS disabled, every SVG/caption remains readable; print hides controls and shows SVG.
7. The page has no remote script, stylesheet, or font dependency, and the console is error-free.
