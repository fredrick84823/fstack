'use strict';

/** Canonical HTML wrappers and embedded multi-instance viewer runtime. */

const crypto = require('node:crypto');

const SYSTEM_STACK = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
let fragmentSerial = 0;

function fontStack(offline) {
  return offline ? SYSTEM_STACK : `Inter, ${SYSTEM_STACK}`;
}

function isDark(presetName = '', themeName = '') {
  return presetName.includes('dark') || /dark|night|mocha|dracula/.test(themeName);
}

function palette(dark) {
  return dark
    ? { page: '#09090b', surface: '#18181b', ink: '#e4e4e7', muted: '#a1a1aa', rule: '#3f3f46', hover: '#27272a' }
    : { page: '#f4f4f5', surface: '#ffffff', ink: '#27272a', muted: '#71717a', rule: '#e4e4e7', hover: '#f4f4f5' };
}

function escapeHTML(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);
}

/** Prefix SVG-local IDs so multiple beautiful-mermaid SVGs can share one document. */
function namespaceSVG(svg, prefix) {
  const ids = [...svg.matchAll(/\sid="([^"]+)"/g)].map((match) => match[1]);
  let output = svg;
  for (const id of ids) {
    const safe = id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const next = `${prefix}-${id}`;
    output = output
      .replace(new RegExp(`id="${safe}"`, 'g'), `id="${next}"`)
      .replace(new RegExp(`url\\(#${safe}\\)`, 'g'), `url(#${next})`)
      .replace(new RegExp(`(["'])#${safe}(["'])`, 'g'), `$1#${next}$2`);
  }
  return output;
}

function embeddedViewerCSS() {
  return `
.mermaid-viewer {
  --mv-surface: #fff; --mv-ink: #27272a; --mv-muted: #71717a; --mv-rule: #e4e4e7;
  position: relative; margin: 1.5rem 0; min-width: 0; color: var(--mv-ink);
  outline: none;
}
.mermaid-viewer:focus-visible { outline: 2px solid #2563eb; outline-offset: 3px; }
.mermaid-viewer__canvas {
  position: relative; width: 100%; min-height: 0; overflow: auto; cursor: default;
  touch-action: auto; background: var(--mv-surface);
  border: 1px solid var(--mv-rule); border-radius: 10px;
}
.mermaid-viewer[data-viewer-ready="true"] .mermaid-viewer__canvas {
  height: min(520px, 70vh); min-height: 280px; overflow: hidden; cursor: grab; touch-action: pan-y;
}
.mermaid-viewer[data-viewer-ready="true"] .mermaid-viewer__canvas.dragging { cursor: grabbing; }
.mermaid-viewer__stage {
  position: relative; transform-origin: 0 0; padding: 24px;
  background: var(--mv-surface); border-radius: 8px;
}
.mermaid-viewer[data-viewer-ready="true"] .mermaid-viewer__stage { position: absolute; left: 0; top: 0; }
.mermaid-viewer[data-viewer-ready="true"] .mermaid-viewer__canvas.dragging .mermaid-viewer__stage { will-change: transform; }
.mermaid-viewer__stage > svg { display: block; max-width: 100%; height: auto; }
.mermaid-viewer[data-viewer-ready="true"] .mermaid-viewer__stage > svg { max-width: none; }
.mermaid-viewer__toolbar {
  display: none; align-items: center; justify-content: flex-end; gap: 6px;
  margin-bottom: 8px; flex-wrap: wrap; user-select: none;
}
.mermaid-viewer[data-viewer-ready="true"] .mermaid-viewer__toolbar { display: flex; }
.mermaid-viewer__toolbar button {
  font: inherit; font-size: 12px; line-height: 1; min-width: 30px; min-height: 30px;
  padding: 6px 8px; border: 1px solid var(--mv-rule); border-radius: 6px;
  background: var(--mv-surface); color: var(--mv-ink); cursor: pointer;
}
.mermaid-viewer__toolbar button:hover { background: color-mix(in srgb, var(--mv-ink) 5%, var(--mv-surface)); }
.mermaid-viewer__toolbar button:focus-visible { outline: 2px solid #2563eb; outline-offset: 2px; }
.mermaid-viewer__level { min-width: 48px; text-align: center; font-size: 12px; font-variant-numeric: tabular-nums; }
.mermaid-viewer__hint, .mermaid-viewer figcaption { color: var(--mv-muted); font-size: 12px; }
.mermaid-viewer__hint { display: none; margin: 7px 0 0; }
.mermaid-viewer[data-viewer-ready="true"] .mermaid-viewer__hint { display: block; }
.mermaid-viewer figcaption { margin-top: 8px; }
.mermaid-viewer--standalone { margin: 0; height: 100vh; }
.mermaid-viewer--standalone .mermaid-viewer__toolbar { position: absolute; z-index: 2; top: 12px; right: 12px; }
.mermaid-viewer--standalone .mermaid-viewer__canvas { height: 100vh; border: 0; border-radius: 0; }
.mermaid-viewer--standalone .mermaid-viewer__hint { position: absolute; z-index: 2; left: 12px; bottom: 12px; margin: 0; }
@media (max-width: 480px) {
  .mermaid-viewer[data-viewer-ready="true"] .mermaid-viewer__canvas { height: 360px; min-height: 240px; }
  .mermaid-viewer__hint { font-size: 11px; }
}
@media (prefers-reduced-motion: reduce) { .mermaid-viewer * { scroll-behavior: auto !important; } }
@media print {
  .mermaid-viewer { break-inside: avoid; }
  .mermaid-viewer__toolbar, .mermaid-viewer__hint { display: none !important; }
  .mermaid-viewer__canvas { height: auto !important; min-height: 0; overflow: visible; border: 0; }
  .mermaid-viewer__stage { position: static; padding: 0 !important; transform: none !important; }
  .mermaid-viewer__stage > svg { width: 100% !important; height: auto !important; max-width: 100% !important; }
}`.trim();
}

function embeddedViewerScript() {
  return `(function () {
  'use strict';
  var MIN = 0.1, MAX = 8, PAD = 24, STEP = 1.25;
  var registry = window.__mermaidViewers = window.__mermaidViewers || [];

  function clamp(value) { return Math.min(MAX, Math.max(MIN, value)); }
  function initialize(root) {
    if (root.dataset.viewerReady === 'true') return null;
    var viewport = root.querySelector('.mermaid-viewer__canvas');
    var stage = root.querySelector('.mermaid-viewer__stage');
    var svg = stage && stage.querySelector('svg');
    var label = root.querySelector('.mermaid-viewer__level');
    if (!viewport || !stage || !svg || !label) return null;
    root.dataset.viewerReady = 'true';

    var vb = (svg.getAttribute('viewBox') || '').split(/[\\s,]+/).map(Number);
    var baseW = parseFloat(svg.getAttribute('width')) || vb[2] || svg.clientWidth || 800;
    var baseH = parseFloat(svg.getAttribute('height')) || vb[3] || svg.clientHeight || 600;
    svg.removeAttribute('width');
    svg.removeAttribute('height');

    var scale = 1, baked = 1, tx = 0, ty = 0, bakeTimer = null;
    function stageW(value) { return (baseW + 2 * PAD) * value; }
    function stageH(value) { return (baseH + 2 * PAD) * value; }
    function draw() {
      var residual = scale / baked;
      stage.style.transform = 'translate(' + tx + 'px,' + ty + 'px) scale(' + residual + ')';
      label.textContent = Math.round(scale * 100) + '%';
    }
    function bake() {
      baked = scale;
      svg.style.width = baseW * baked + 'px';
      svg.style.height = baseH * baked + 'px';
      stage.style.padding = PAD * baked + 'px';
      stage.style.borderRadius = 8 * Math.min(baked, 2) + 'px';
      draw();
    }
    function scheduleBake() {
      if (bakeTimer) clearTimeout(bakeTimer);
      bakeTimer = setTimeout(function () { bakeTimer = null; bake(); }, 90);
    }
    function zoomAt(next, cx, cy) {
      var target = clamp(next);
      if (target === scale) return;
      var factor = target / scale;
      tx = cx - factor * (cx - tx);
      ty = cy - factor * (cy - ty);
      scale = target;
      draw();
      scheduleBake();
    }
    function zoomBy(factor, cx, cy) {
      zoomAt(scale * factor, cx == null ? viewport.clientWidth / 2 : cx, cy == null ? viewport.clientHeight / 2 : cy);
    }
    function fit() {
      scale = clamp(Math.min((viewport.clientWidth - 16) / stageW(1), (viewport.clientHeight - 16) / stageH(1)));
      tx = (viewport.clientWidth - stageW(scale)) / 2;
      ty = (viewport.clientHeight - stageH(scale)) / 2;
      bake();
    }
    function reset() {
      scale = 1;
      tx = Math.max(0, (viewport.clientWidth - stageW(1)) / 2);
      ty = 0;
      bake();
    }
    function state() { return { scale: scale, baked: baked, tx: tx, ty: ty, baseW: baseW, baseH: baseH }; }

    viewport.addEventListener('wheel', function (event) {
      var modifier = event.ctrlKey || event.metaKey;
      if (!modifier) return;
      event.preventDefault();
      var rect = viewport.getBoundingClientRect();
      zoomAt(scale * Math.exp(-event.deltaY * 0.01), event.clientX - rect.left, event.clientY - rect.top);
    }, { passive: false });

    var dragging = false, pointerId = null, lastX = 0, lastY = 0;
    viewport.addEventListener('pointerdown', function (event) {
      if (event.button !== 0 || event.pointerType === 'touch') return;
      event.preventDefault();
      root.focus({ preventScroll: true });
      dragging = true; pointerId = event.pointerId; lastX = event.clientX; lastY = event.clientY;
      viewport.classList.add('dragging');
      if (viewport.setPointerCapture) viewport.setPointerCapture(pointerId);
    });
    viewport.addEventListener('pointermove', function (event) {
      if (!dragging || event.pointerId !== pointerId) return;
      tx += event.clientX - lastX; ty += event.clientY - lastY;
      lastX = event.clientX; lastY = event.clientY; draw();
    });
    function endDrag(event) {
      if (!dragging || (event && event.pointerId !== pointerId)) return;
      dragging = false; viewport.classList.remove('dragging');
      if (viewport.hasPointerCapture && viewport.hasPointerCapture(pointerId)) viewport.releasePointerCapture(pointerId);
      pointerId = null;
    }
    viewport.addEventListener('pointerup', endDrag);
    viewport.addEventListener('pointercancel', endDrag);

    var pinchDistance = 0, pinchScale = 1;
    function distance(touches) {
      var dx = touches[0].clientX - touches[1].clientX;
      var dy = touches[0].clientY - touches[1].clientY;
      return Math.sqrt(dx * dx + dy * dy);
    }
    viewport.addEventListener('touchstart', function (event) {
      if (event.touches.length !== 2) return;
      pinchDistance = distance(event.touches); pinchScale = scale;
    }, { passive: true });
    viewport.addEventListener('touchmove', function (event) {
      if (event.touches.length !== 2 || !pinchDistance) return;
      event.preventDefault();
      var rect = viewport.getBoundingClientRect();
      var cx = (event.touches[0].clientX + event.touches[1].clientX) / 2 - rect.left;
      var cy = (event.touches[0].clientY + event.touches[1].clientY) / 2 - rect.top;
      zoomAt(pinchScale * distance(event.touches) / pinchDistance, cx, cy);
    }, { passive: false });
    viewport.addEventListener('touchend', function (event) { if (event.touches.length < 2) pinchDistance = 0; }, { passive: true });

    root.querySelector('[data-action="zoom-in"]').addEventListener('click', function () { zoomBy(STEP); });
    root.querySelector('[data-action="zoom-out"]').addEventListener('click', function () { zoomBy(1 / STEP); });
    root.querySelector('[data-action="fit"]').addEventListener('click', fit);
    root.querySelector('[data-action="reset"]').addEventListener('click', reset);
    root.addEventListener('keydown', function (event) {
      if (!root.contains(document.activeElement) || /^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName)) return;
      if (event.key === '+' || event.key === '=') zoomBy(STEP);
      else if (event.key === '-' || event.key === '_') zoomBy(1 / STEP);
      else if (event.key === '0') reset();
      else if (event.key === 'f' || event.key === 'F') fit();
      else return;
      event.preventDefault();
    });

    var api = { element: root, state: state, fit: fit, reset: reset, zoomAt: zoomAt, zoomBy: zoomBy, bake: bake };
    registry.push(api);
    requestAnimationFrame(fit);
    return api;
  }

  function initializeAll(scope) {
    (scope || document).querySelectorAll('[data-mermaid-viewer]').forEach(initialize);
    if (document.body && document.body.classList.contains('mermaid-standalone') && registry[0]) window.__mermaidViewer = registry[0];
    return registry;
  }
  window.MermaidEmbeddedViewer = { init: initializeAll };
  initializeAll(document);
})();`;
}

function embeddedFigure(svg, options = {}) {
  const label = options.label || 'Mermaid diagram';
  const caption = options.caption || '';
  const hint = options.hint || 'Drag to pan · Ctrl/Cmd + wheel or pinch to zoom · focused: f / 0 / + / −';
  const key = options.key || `${crypto.createHash('sha1').update(svg).digest('hex').slice(0, 8)}-${fragmentSerial++}`;
  const namespaced = namespaceSVG(svg, `mv-${String(key).replace(/[^a-zA-Z0-9_-]/g, '-')}`);
  return `<figure class="mermaid-viewer${options.standalone ? ' mermaid-viewer--standalone' : ''}" data-mermaid-viewer tabindex="0" aria-label="${escapeHTML(label)}">
  <div class="mermaid-viewer__toolbar" role="group" aria-label="Diagram zoom controls">
    <button type="button" data-action="zoom-out" aria-label="Zoom out" title="Zoom out (−)">−</button>
    <span class="mermaid-viewer__level" aria-live="polite">100%</span>
    <button type="button" data-action="zoom-in" aria-label="Zoom in" title="Zoom in (+)">+</button>
    <button type="button" data-action="fit" aria-label="Fit diagram" title="Fit diagram (f)">Fit</button>
    <button type="button" data-action="reset" aria-label="Reset to 1:1" title="Reset to 1:1 (0)">1:1</button>
  </div>
  <div class="mermaid-viewer__canvas">
    <div class="mermaid-viewer__stage">${namespaced}</div>
  </div>
  <p class="mermaid-viewer__hint">${escapeHTML(hint)}</p>
  ${caption ? `<figcaption>${escapeHTML(caption)}</figcaption>` : ''}
</figure>`;
}

function embeddedDocument(figures, options = {}) {
  const title = options.title || 'Embedded Mermaid viewers';
  const offline = options.offline !== false;
  const body = figures.map((item, index) => embeddedFigure(item.svg, { ...item, key: item.key || `figure-${index + 1}` })).join('\n');
  return `<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${escapeHTML(title)}</title><style>
* { box-sizing: border-box; } html { overflow-x: hidden; } body { margin: 0; padding: 32px 20px 80px; font-family: ${fontStack(offline)}; color: #27272a; background: #fff; }
main { width: min(960px, 100%); margin: 0 auto; } h1 { font-size: 28px; } .showcase-spacer { height: 45vh; }
${embeddedViewerCSS()}
</style></head><body><main><h1>${escapeHTML(title)}</h1>
<noscript><p>JavaScript is optional: diagrams remain readable as static SVG; pan and zoom controls are unavailable.</p></noscript>
${body}<div class="showcase-spacer" aria-hidden="true"></div></main><script>${embeddedViewerScript()}</script></body></html>`;
}

function staticHTML(svg, { presetName, themeName, offline }) {
  const dark = isDark(presetName, themeName);
  const c = palette(dark);
  return `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mermaid Diagram — ${escapeHTML(presetName)}</title><style>
:root { color-scheme: ${dark ? 'dark' : 'light'}; } body { margin:0; padding:48px 24px; font-family:${fontStack(offline)}; background:${dark ? '#18181b' : '#fff'}; color:${c.ink}; }
main { max-width:1100px; margin:0 auto; } figcaption { font-size:12px; color:${c.muted}; margin-bottom:16px; } svg { max-width: 100%; height: auto; display: block; }
</style></head><body><main><figure style="margin:0"><figcaption>preset: ${escapeHTML(presetName)} · theme: ${escapeHTML(themeName)}</figcaption>${svg}</figure></main></body></html>`;
}

/** Standalone viewer is a full-page shell around the same canonical embedded runtime. */
function interactiveHTML(svg, { presetName, themeName, offline }) {
  const dark = isDark(presetName, themeName);
  const c = palette(dark);
  const figure = embeddedFigure(svg, {
    label: `Mermaid diagram — ${presetName}`,
    standalone: true,
    key: 'standalone',
    hint: 'Drag to pan · Ctrl/Cmd + wheel or pinch to zoom · f fit · 0 reset · + / −',
  });
  return `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mermaid Diagram — ${escapeHTML(presetName)}</title><style>
* { box-sizing:border-box; } html,body { margin:0; height:100%; overflow:hidden; font-family:${fontStack(offline)}; background:${c.page}; color:${c.ink}; color-scheme:${dark ? 'dark' : 'light'}; }
.mermaid-viewer { --mv-surface:${c.surface}; --mv-ink:${c.ink}; --mv-muted:${c.muted}; --mv-rule:${c.rule}; }
${embeddedViewerCSS()}
</style></head><body class="mermaid-standalone"><noscript>${svg}</noscript>${figure}<script>${embeddedViewerScript()}</script></body></html>`;
}

module.exports = {
  staticHTML,
  interactiveHTML,
  embeddedFigure,
  embeddedViewerCSS,
  embeddedViewerScript,
  embeddedDocument,
  namespaceSVG,
  isDark,
  palette,
};
