'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('node:child_process');

const {
  embeddedFigure,
  embeddedViewerCSS,
  embeddedViewerScript,
  embeddedDocument,
} = require('../scripts/lib/html');
const { renderSVG } = require('../scripts/lib/presets');

const SKILL_DIR = path.resolve(__dirname, '..');
const EXAMPLES = path.join(SKILL_DIR, 'assets', 'examples');
const source = (name) => fs.readFileSync(path.join(EXAMPLES, name), 'utf8');

async function fixture() {
  const a = await renderSVG(source('flowchart.mmd'), { offline: true });
  const b = await renderSVG(source('sequence.mmd'), { offline: true });
  return embeddedDocument([
    { svg: a.svg, label: 'Decision flow', caption: 'First independent viewer.' },
    { svg: b.svg, label: 'Request sequence', caption: 'Second independent viewer.' },
  ], { title: 'Embedded viewer test' });
}

test('embedded API emits reusable class/data markup with unique SVG IDs', async () => {
  const { svg } = await renderSVG(source('flowchart.mmd'), { offline: true });
  const one = embeddedFigure(svg, { label: 'Flow', caption: 'A flow.' });
  const two = embeddedFigure(svg, { label: 'Flow copy', caption: 'Another flow.' });
  const html = one + two;

  assert.equal((html.match(/data-mermaid-viewer(?:=|\s)/g) || []).length, 2);
  assert.equal((html.match(/<figure/g) || []).length, 2);
  const ids = [...html.matchAll(/\sid="([^"]+)"/g)].map((match) => match[1]);
  assert.equal(new Set(ids).size, ids.length, 'two fragments must not contain duplicate IDs');
  assert.ok(!/<(?:figure|div|button|span)[^>]+\sid=/.test(html), 'viewer chrome uses classes/data attributes');
  for (const action of ['zoom-in', 'zoom-out', 'fit', 'reset']) {
    assert.equal((html.match(new RegExp(`data-action="${action}"`, 'g')) || []).length, 2);
  }
  for (const label of ['Zoom in', 'Zoom out', 'Fit diagram', 'Reset to 1:1']) {
    assert.equal((html.match(new RegExp(`aria-label="${label}"`, 'g')) || []).length, 2);
  }
  assert.match(html, /tabindex="0"/);
  assert.match(html, /<figcaption>A flow\.<\/figcaption>/);
});

test('canonical assets encode embedded interaction, touch, fallback, and print contracts', () => {
  const css = embeddedViewerCSS();
  const js = embeddedViewerScript();

  assert.match(css, /touch-action:\s*pan-y/);
  assert.match(css, /@media print/);
  assert.match(css, /\.mermaid-viewer__toolbar[^}]*display:\s*none/s);
  assert.match(css, /data-viewer-ready[^}]+\.mermaid-viewer__stage\s*>\s*svg[^}]*max-width:\s*none/s);
  assert.match(css, /\.mermaid-viewer__stage\s*>\s*svg[^}]*max-width:\s*100%/s);
  assert.doesNotMatch(css, /(^|[},\s])#[A-Za-z_][\w-]*\s*[{,]/m, 'canonical CSS must not rely on ID selectors');

  assert.match(js, /window\.__mermaidViewers/);
  assert.match(js, /ctrlKey\s*\|\|\s*event\.metaKey/);
  assert.match(js, /if\s*\(!modifier\)\s*return/);
  assert.match(js, /event\.preventDefault\(\)/);
  assert.match(js, /pointerType\s*===\s*['"]touch['"]/);
  assert.match(js, /touches\.length\s*!==\s*2/);
  assert.match(js, /scale\s*\/\s*baked/);
  assert.match(js, /svg\.style\.width\s*=\s*baseW\s*\*\s*baked/);
  for (const method of ['state', 'fit', 'reset', 'zoomAt', 'zoomBy']) {
    assert.match(js, new RegExp(`${method}:`), `automation API missing ${method}`);
  }
});

test('embedded document is offline, multi-instance, readable without JS, and self-contained', async () => {
  const html = await fixture();
  assert.equal((html.match(/data-mermaid-viewer(?:=|\s)/g) || []).length, 2);
  assert.equal((html.match(/<svg/g) || []).length, 2);
  const ids = [...html.matchAll(/\sid="([^"]+)"/g)].map((match) => match[1]);
  assert.equal(new Set(ids).size, ids.length);
  assert.ok(!/<(?:figure|div|button|span)[^>]+\sid=/.test(html));
  assert.equal((html.match(/<script>/g) || []).length, 1, 'runtime appears once');
  assert.equal((html.match(/window\.__mermaidViewers\s*=/g) || []).length, 1);
  assert.ok(!/<script[^>]+src=/.test(html));
  assert.ok(!/<link[^>]+href=/.test(html));
  assert.ok(!/https?:\/\/(?!www\.w3\.org)/.test(html));
  assert.match(html, /<noscript>/);
  assert.match(html, /JavaScript is optional/);
});

test('CLI interactive HTML uses canonical multi-instance runtime; static remains script-free', () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'bm-embedded-cli-'));
  const cli = path.join(SKILL_DIR, 'scripts', 'render_mermaid.js');
  const input = path.join(EXAMPLES, 'flowchart.mmd');
  const interactive = path.join(tmp, 'interactive.html');
  const staticOut = path.join(tmp, 'static.html');

  execFileSync('node', [cli, '-i', input, '-o', interactive, '-f', 'html', '--offline']);
  execFileSync('node', [cli, '-i', input, '-o', staticOut, '-f', 'html', '--static', '--offline']);

  const html = fs.readFileSync(interactive, 'utf8');
  assert.match(html, /data-mermaid-viewer/);
  assert.match(html, /window\.__mermaidViewers/);
  assert.match(html, /window\.__mermaidViewer\s*=/, 'standalone compatibility alias remains');
  assert.ok(!/<(?:figure|div|button|span)[^>]+\sid=/.test(html));
  assert.ok(!fs.readFileSync(staticOut, 'utf8').includes('<script'));
});

test('embedded showcase is fresh and doc-to-html points to the canonical runtime', () => {
  const showcase = path.join(EXAMPLES, 'embedded-viewer-showcase.html');
  const before = fs.readFileSync(showcase, 'utf8');
  execFileSync('node', [path.join(SKILL_DIR, 'scripts', 'build_embedded_showcase.js')], { cwd: SKILL_DIR, stdio: 'ignore' });
  assert.equal(fs.readFileSync(showcase, 'utf8'), before);

  const docSkill = fs.readFileSync(path.resolve(SKILL_DIR, '..', 'doc-to-html', 'SKILL.md'), 'utf8');
  for (const token of ['MUST', 'embeddedFigure()', 'embeddedViewerCSS()', 'embeddedViewerScript()', 'window.__mermaidViewers', '390px', '普通 wheel', 'print']) {
    assert.ok(docSkill.includes(token), `doc-to-html contract missing ${token}`);
  }
  const refs = ['vercel-docs.md', 'stripe-docs.md', 'notion-docs.md'].map((name) =>
    fs.readFileSync(path.resolve(SKILL_DIR, '..', 'doc-to-html', 'references', name), 'utf8')
  );
  for (const ref of refs) {
    assert.ok(!ref.includes('themeVariables'), 'style references must not provide alternate Mermaid runtimes/themes');
    assert.ok(!ref.includes('window.__mermaid'), 'style references must not redefine viewer interaction');
  }
});
