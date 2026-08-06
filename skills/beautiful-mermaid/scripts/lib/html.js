'use strict';

/**
 * HTML wrappers for rendered SVG.
 *
 * - `staticHTML`      : plain embedded SVG, no script (for further embedding).
 * - `interactiveHTML` : offline pan/zoom viewer, zero dependencies.
 *
 * Sharpness note (see references/integration-guide.md): CSS `transform: scale()`
 * rasterizes the composited layer once at 1x and then stretches the bitmap, so
 * text goes blurry when zoomed in. The viewer therefore *bakes* the zoom into
 * the SVG's real layout size (`style.width/height`) and only uses a residual
 * transform (`scale(scale / baked)`) for in-flight gesture feedback.
 */

const SYSTEM_STACK = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';

function fontStack(offline) {
  return offline ? SYSTEM_STACK : `Inter, ${SYSTEM_STACK}`;
}

/** Dark chrome when the preset/theme is dark. */
function isDark(presetName = '', themeName = '') {
  return presetName.includes('dark') || /dark|night|mocha|dracula/.test(themeName);
}

function palette(dark) {
  return dark
    ? { page: '#09090b', surface: '#18181b', ink: '#e4e4e7', muted: '#a1a1aa', rule: '#3f3f46', hover: '#27272a' }
    : { page: '#f4f4f5', surface: '#ffffff', ink: '#27272a', muted: '#71717a', rule: '#e4e4e7', hover: '#f4f4f5' };
}

/** Minimal document flow wrapper: no card chrome, no gradients, no script. */
function staticHTML(svg, { presetName, themeName, offline }) {
  const dark = isDark(presetName, themeName);
  const c = palette(dark);
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mermaid Diagram — ${presetName}</title>
<style>
  :root { color-scheme: ${dark ? 'dark' : 'light'}; }
  body {
    margin: 0;
    padding: 48px 24px;
    font-family: ${fontStack(offline)};
    background: ${dark ? '#18181b' : '#ffffff'};
    color: ${c.ink};
  }
  main { max-width: 1100px; margin: 0 auto; }
  figcaption {
    font-size: 12px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: ${c.muted};
    margin-bottom: 16px;
  }
  svg { max-width: 100%; height: auto; display: block; }
</style>
</head>
<body>
<main>
  <figure style="margin:0">
    <figcaption>preset: ${presetName} · theme: ${themeName}</figcaption>
    ${svg}
  </figure>
</main>
</body>
</html>`;
}

/** Interactive viewer: wheel/pinch zoom anchored at the cursor, drag to pan. */
function interactiveHTML(svg, { presetName, themeName, offline }) {
  const dark = isDark(presetName, themeName);
  const c = palette(dark);
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mermaid Diagram — ${presetName}</title>
<style>
  html, body {
    margin: 0;
    padding: 0;
    height: 100%;
    font-family: ${fontStack(offline)};
    background: ${c.page};
    color: ${c.ink};
    overflow: hidden;
    color-scheme: ${dark ? 'dark' : 'light'};
  }
  #viewport {
    position: fixed;
    inset: 0;
    cursor: grab;
    touch-action: none;
    overscroll-behavior: none;
  }
  #viewport.dragging { cursor: grabbing; }
  #stage {
    position: absolute;
    top: 0;
    left: 0;
    transform-origin: 0 0;
    background: ${c.surface};
    padding: 32px;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,${dark ? '0.6' : '0.10'});
  }
  /* will-change only while dragging: keeping it on forces a permanent layer. */
  #viewport.dragging #stage { will-change: transform; }
  #stage > svg { display: block; max-width: none; height: auto; }
  #hud {
    position: fixed;
    top: 12px;
    right: 12px;
    display: flex;
    gap: 6px;
    align-items: center;
    background: ${c.surface};
    border: 1px solid ${c.rule};
    border-radius: 8px;
    padding: 6px 8px;
    font-size: 12px;
    color: ${c.ink};
    box-shadow: 0 1px 3px rgba(0,0,0,${dark ? '0.5' : '0.08'});
    user-select: none;
    z-index: 10;
  }
  #hud button {
    font: inherit;
    min-width: 26px;
    padding: 2px 6px;
    cursor: pointer;
    border: 1px solid ${c.rule};
    border-radius: 5px;
    background: ${c.surface};
    color: inherit;
  }
  #hud button:hover { background: ${c.hover}; }
  #zoomLevel { min-width: 46px; text-align: center; font-variant-numeric: tabular-nums; }
  #meta { color: ${c.muted}; font-size: 11px; padding-right: 4px; }
  #hint {
    position: fixed;
    bottom: 12px;
    left: 12px;
    font-size: 11px;
    color: ${c.muted};
    background: ${c.surface};
    border: 1px solid ${c.rule};
    border-radius: 6px;
    padding: 4px 8px;
    user-select: none;
    z-index: 10;
  }
</style>
</head>
<body>
  <div id="hud">
    <span id="meta">${presetName} · ${themeName}</span>
    <button id="zoomOut" title="Zoom out (-)">−</button>
    <span id="zoomLevel">100%</span>
    <button id="zoomIn" title="Zoom in (+)">+</button>
    <button id="zoomFit" title="Fit (f)">Fit</button>
    <button id="zoomReset" title="Reset 1:1 (0)">1:1</button>
  </div>
  <div id="hint">wheel / pinch zoom · drag to pan · double-click 1:1 · f fit · 0 reset · +/−</div>
  <div id="viewport">
    <div id="stage">
${svg}
    </div>
  </div>
<script>
(function () {
  var viewport = document.getElementById('viewport');
  var stage = document.getElementById('stage');
  var svg = stage.querySelector('svg');
  var label = document.getElementById('zoomLevel');
  var MIN = 0.1, MAX = 8, PAD = 32, STEP = 1.25;

  // Base (1:1) intrinsic size, then drop the attributes so CSS size wins.
  var vb = (svg.getAttribute('viewBox') || '').split(/[\\s,]+/).map(Number);
  var baseW = parseFloat(svg.getAttribute('width')) || vb[2] || svg.clientWidth || 800;
  var baseH = parseFloat(svg.getAttribute('height')) || vb[3] || svg.clientHeight || 600;
  svg.removeAttribute('width');
  svg.removeAttribute('height');

  var scale = 1;   // logical zoom
  var baked = 1;   // zoom already baked into the SVG layout size
  var tx = 0, ty = 0;
  var bakeTimer = null;

  function stageW(s) { return (baseW + 2 * PAD) * s; }
  function stageH(s) { return (baseH + 2 * PAD) * s; }

  // Bake zoom into real SVG dimensions -> the browser re-rasterizes vectors sharply.
  function bake() {
    baked = scale;
    svg.style.width = baseW * baked + 'px';
    svg.style.height = baseH * baked + 'px';
    stage.style.padding = PAD * baked + 'px';
    stage.style.borderRadius = 8 * Math.min(baked, 2) + 'px';
    draw();
  }

  // Cheap transform for the in-flight gesture; blurry until bake() lands.
  function draw() {
    var residual = scale / baked;
    stage.style.transform = 'translate(' + tx + 'px,' + ty + 'px) scale(' + residual + ')';
    label.textContent = Math.round(scale * 100) + '%';
  }

  function scheduleBake() {
    if (bakeTimer) clearTimeout(bakeTimer);
    bakeTimer = setTimeout(function () { bakeTimer = null; bake(); }, 90);
  }

  function clamp(s) { return Math.min(MAX, Math.max(MIN, s)); }

  // Zoom keeping the given viewport point stationary.
  function zoomAt(next, cx, cy) {
    var s = clamp(next);
    if (s === scale) return;
    var k = s / scale;
    tx = cx - k * (cx - tx);
    ty = cy - k * (cy - ty);
    scale = s;
    draw();
    scheduleBake();
  }

  function zoomCenter(factor) {
    zoomAt(scale * factor, viewport.clientWidth / 2, viewport.clientHeight / 2);
  }

  function fit() {
    scale = clamp(Math.min(
      (viewport.clientWidth - 24) / stageW(1),
      (viewport.clientHeight - 24) / stageH(1)
    ));
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

  viewport.addEventListener('wheel', function (e) {
    e.preventDefault();
    var r = viewport.getBoundingClientRect();
    var intensity = e.ctrlKey ? 0.01 : 0.0018; // trackpad pinch vs wheel
    zoomAt(scale * Math.exp(-e.deltaY * intensity), e.clientX - r.left, e.clientY - r.top);
  }, { passive: false });

  var dragging = false, lastX = 0, lastY = 0, pointerId = null;

  viewport.addEventListener('pointerdown', function (e) {
    if (e.button !== 0) return;
    dragging = true;
    pointerId = e.pointerId;
    lastX = e.clientX;
    lastY = e.clientY;
    viewport.classList.add('dragging');
    if (viewport.setPointerCapture) viewport.setPointerCapture(pointerId);
  });

  viewport.addEventListener('pointermove', function (e) {
    if (!dragging || e.pointerId !== pointerId) return;
    tx += e.clientX - lastX;
    ty += e.clientY - lastY;
    lastX = e.clientX;
    lastY = e.clientY;
    draw();
  });

  function endDrag(e) {
    if (!dragging || (e && e.pointerId !== pointerId)) return;
    dragging = false;
    viewport.classList.remove('dragging');
    if (pointerId !== null && viewport.hasPointerCapture && viewport.hasPointerCapture(pointerId)) {
      viewport.releasePointerCapture(pointerId);
    }
    pointerId = null;
  }
  viewport.addEventListener('pointerup', endDrag);
  viewport.addEventListener('pointercancel', endDrag);

  viewport.addEventListener('dblclick', function () { reset(); });

  document.getElementById('zoomIn').addEventListener('click', function () { zoomCenter(STEP); });
  document.getElementById('zoomOut').addEventListener('click', function () { zoomCenter(1 / STEP); });
  document.getElementById('zoomFit').addEventListener('click', fit);
  document.getElementById('zoomReset').addEventListener('click', reset);

  document.addEventListener('keydown', function (e) {
    if (e.key === '+' || e.key === '=') zoomCenter(STEP);
    else if (e.key === '-' || e.key === '_') zoomCenter(1 / STEP);
    else if (e.key === '0') reset();
    else if (e.key === 'f' || e.key === 'F') fit();
    else return;
    e.preventDefault();
  });

  window.addEventListener('resize', function () {
    tx = Math.min(tx, viewport.clientWidth - 40);
    ty = Math.min(ty, viewport.clientHeight - 40);
    draw();
  });

  fit();

  // Test/automation hook.
  window.__mermaidViewer = {
    state: function () { return { scale: scale, baked: baked, tx: tx, ty: ty, baseW: baseW, baseH: baseH }; },
    fit: fit,
    reset: reset,
    zoomAt: zoomAt,
    bake: bake
  };
})();
</script>
</body>
</html>`;
}

module.exports = { staticHTML, interactiveHTML, isDark, palette };
