'use strict';

/**
 * Semantic render assertions. Run: node --test tests/
 *
 * These lock the contract that matters for visual parity:
 * preset defaults, single render path, structural output, portability.
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const {
  PRESETS,
  DEFAULT_PRESET,
  renderSVG,
  renderASCII,
  resolveRenderOptions,
  loadPackage,
} = require('../scripts/lib/presets');
const { staticHTML, interactiveHTML } = require('../scripts/lib/html');

const SKILL_DIR = path.resolve(__dirname, '..');
const EXAMPLES = path.join(SKILL_DIR, 'assets', 'examples');
const read = (file) => fs.readFileSync(path.join(EXAMPLES, file), 'utf8');
const count = (haystack, needle) => haystack.split(needle).length - 1;

/** Craft hero reference: observed on https://agents.craft.do/mermaid */
const HERO = {
  viewBox: '0 0 1181.9379999999999 182.5',
  nodes: 9,
  edges: 9,
  edgeLabels: ['DSL', 'AST', 'Vector', 'Text'],
};

test('default preset is craft: mono zinc-light, transparent, Inter, 40/28/48', async () => {
  const { THEMES } = await loadPackage();
  const { presetName, themeName, options } = resolveRenderOptions(THEMES, {});
  assert.equal(presetName, DEFAULT_PRESET);
  assert.equal(themeName, 'zinc-light');
  assert.equal(options.bg, '#FFFFFF');
  assert.equal(options.fg, '#27272A');
  assert.equal(options.transparent, true);
  assert.equal(options.font, 'Inter');
  assert.equal(options.padding, 40);
  assert.equal(options.nodeSpacing, 28);
  assert.equal(options.layerSpacing, 48);
});

test('explicit --theme overrides preset colors but keeps preset spacing', async () => {
  const { THEMES } = await loadPackage();
  const { themeName, options } = resolveRenderOptions(THEMES, { theme: 'nord' });
  assert.equal(themeName, 'nord');
  assert.equal(options.bg, THEMES.nord.bg);
  assert.equal(options.nodeSpacing, 28);
});

test('unknown preset and theme fail loudly', async () => {
  const { THEMES } = await loadPackage();
  assert.throws(() => resolveRenderOptions(THEMES, { preset: 'nope' }), /Unknown preset/);
  assert.throws(() => resolveRenderOptions(THEMES, { theme: 'nope' }), /Unknown theme/);
});

test('hero fixture matches the Craft reference structure', async () => {
  const { svg } = await renderSVG(read('hero.mmd'));
  assert.match(svg, new RegExp(`viewBox="${HERO.viewBox}"`));
  assert.equal(count(svg, 'class="node"'), HERO.nodes);
  assert.equal(count(svg, 'class="edge"'), HERO.edges);
  for (const label of HERO.edgeLabels) {
    assert.ok(svg.includes(`>${label}<`), `missing edge label ${label}`);
  }
  assert.ok(svg.includes('--bg:#FFFFFF') || svg.includes('#FFFFFF'), 'mono bg missing');
});

test('craft output is transparent; legacy keeps an opaque background', async () => {
  const craft = await renderSVG(read('flowchart.mmd'), { preset: 'craft' });
  const legacy = await renderSVG(read('flowchart.mmd'), { preset: 'legacy' });
  assert.ok(!/<svg[^>]*style="[^"]*background/.test(craft.svg));
  assert.ok(/<svg[^>]*style="[^"]*background/.test(legacy.svg));
});

test('--offline output has no remote dependency', async () => {
  const { svg } = await renderSVG(read('hero.mmd'), { offline: true });
  assert.ok(!svg.includes('fonts.googleapis.com'));
  assert.ok(!/@import/.test(svg));
  const remote = svg.match(/https?:\/\/[^"')\s]+/g) || [];
  assert.deepEqual(
    remote.filter((url) => !url.startsWith('http://www.w3.org/')),
    []
  );
});

test('all six diagram families render through the package', async () => {
  const fixtures = [
    ['flowchart.mmd', 'graph'],
    ['state.mmd', 'stateDiagram-v2'],
    ['sequence.mmd', 'sequenceDiagram'],
    ['class.mmd', 'classDiagram'],
    ['er.mmd', 'erDiagram'],
    ['xychart.mmd', 'xychart-beta'],
  ];
  for (const [file, header] of fixtures) {
    const source = read(file);
    assert.ok(source.trim().startsWith(header), `${file} header drift`);
    const { svg } = await renderSVG(source);
    assert.ok(svg.startsWith('<svg'), `${file} did not render`);
    assert.match(svg, /viewBox="0 0 [\d.]+ [\d.]+"/);
  }
});

test('mmd fixtures stay monochrome and emoji-free', () => {
  const files = fs.readdirSync(EXAMPLES).filter((f) => f.endsWith('.mmd'));
  assert.ok(files.length >= 6);
  for (const file of files) {
    const source = read(file);
    assert.ok(!/fill:#|stroke:#/.test(source), `${file} carries inline colors`);
    assert.ok(
      !/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u.test(source),
      `${file} carries emoji`
    );
  }
});

test('ASCII output uses the sync primary API', async () => {
  const ascii = await renderASCII(read('hero.mmd'));
  assert.ok(ascii.includes('Input'));
  assert.ok(ascii.includes('DSL'));
  assert.ok(!ascii.includes('\u001b['), 'colorMode none should emit no ANSI');
});

test('showcase HTML is package-rendered and self-contained', () => {
  const html = fs.readFileSync(path.join(EXAMPLES, 'all-diagrams-showcase.html'), 'utf8');
  assert.ok(!html.includes('cdn.jsdelivr.net'), 'showcase must not load Mermaid.js');
  assert.ok(!html.includes('mermaid.esm'), 'showcase must not load Mermaid.js');
  assert.ok(!html.includes('fonts.googleapis.com'));
  assert.ok(!/<link[^>]+href="https?:/.test(html));
  assert.ok(!/<script[^>]+src=/.test(html));
  const remote = (html.match(/https?:\/\/[^"')\s]+/g) || []).filter(
    (url) => !url.startsWith('http://www.w3.org/')
  );
  assert.deepEqual(remote, []);
  assert.ok(count(html, '<svg') >= 24, 'expected 8 diagrams × 3 presets');
});

test('showcase is up to date with the generator', () => {
  const file = path.join(EXAMPLES, 'all-diagrams-showcase.html');
  const before = fs.readFileSync(file, 'utf8');
  execFileSync('node', [path.join(SKILL_DIR, 'scripts', 'build_showcase.js')], {
    cwd: SKILL_DIR,
    stdio: 'ignore',
  });
  assert.equal(fs.readFileSync(file, 'utf8'), before, 'run node scripts/build_showcase.js');
});

test('interactive HTML template is self-contained and complete', async () => {
  const { svg, presetName, themeName } = await renderSVG(read('hero.mmd'), { offline: true });
  const html = interactiveHTML(svg, { presetName, themeName, offline: true });

  // structure
  for (const id of ['id="viewport"', 'id="stage"', 'id="hud"', 'id="hint"', 'id="zoomLevel"']) {
    assert.ok(html.includes(id), `missing ${id}`);
  }
  for (const id of ['zoomIn', 'zoomOut', 'zoomFit', 'zoomReset']) {
    assert.ok(html.includes(`id="${id}"`), `missing HUD control ${id}`);
  }

  // behavior contract
  assert.match(html, /MIN = 0\.1, MAX = 8/);
  assert.ok(html.includes("addEventListener('wheel'"));
  assert.ok(html.includes("addEventListener('pointerdown'"));
  assert.ok(html.includes('setPointerCapture'));
  assert.ok(html.includes("addEventListener('dblclick'"));
  assert.ok(html.includes("addEventListener('keydown'"));
  assert.ok(/fit\(\);\s*\n/.test(html), 'must auto-fit on load');

  // sharpness contract: bake into real SVG size, residual transform, debounce
  assert.ok(html.includes("svg.removeAttribute('width')"));
  assert.ok(html.includes('svg.style.width = baseW * baked'));
  assert.ok(html.includes('scale / baked'));
  assert.match(html, /setTimeout\(function \(\) \{ bakeTimer = null; bake\(\); \}, 90\)/);
  assert.ok(html.includes('#viewport.dragging #stage { will-change: transform; }'));
  const stageRule = html.match(/\n  #stage \{[\s\S]*?\n  \}/);
  assert.ok(stageRule, '#stage rule not found');
  assert.ok(!/will-change/.test(stageRule[0]), 'will-change must not be permanent');
  assert.ok(html.includes('#stage > svg { display: block; max-width: none;'));

  // zero dependencies
  assert.ok(!/<script[^>]+src=/.test(html));
  assert.ok(!/<link[^>]+href=/.test(html));
  const remote = (html.match(/https?:\/\/[^"')\s]+/g) || []).filter(
    (url) => !url.startsWith('http://www.w3.org/')
  );
  assert.deepEqual(remote, []);
});

test('static HTML has no script and keeps document flow', async () => {
  const { svg, presetName, themeName } = await renderSVG(read('hero.mmd'), { offline: true });
  const html = staticHTML(svg, { presetName, themeName, offline: true });
  assert.ok(!html.includes('<script'));
  assert.ok(!html.includes('id="viewport"'));
  assert.ok(html.includes('<figcaption>'));
  assert.ok(html.includes('svg { max-width: 100%; height: auto; display: block; }'));
});

test('CLI: -f html defaults to interactive, --static opts out, -f svg unchanged', () => {
  const dir = fs.mkdtempSync('/tmp/bm-html-');
  const cli = (...args) =>
    execFileSync('node', [path.join(SKILL_DIR, 'scripts', 'render_mermaid.js'), ...args], {
      cwd: SKILL_DIR,
      stdio: ['ignore', 'pipe', 'ignore'],
      encoding: 'utf8',
    });
  const hero = path.join(EXAMPLES, 'hero.mmd');

  const interactive = path.join(dir, 'i.html');
  cli('-i', hero, '-o', interactive, '-f', 'html');
  assert.ok(fs.readFileSync(interactive, 'utf8').includes('__mermaidViewer'));

  const explicit = path.join(dir, 'e.html');
  cli('-i', hero, '-o', explicit, '-f', 'html', '--interactive');
  assert.equal(fs.readFileSync(explicit, 'utf8'), fs.readFileSync(interactive, 'utf8'));

  const staticOut = path.join(dir, 's.html');
  cli('-i', hero, '-o', staticOut, '-f', 'html', '--static');
  const staticHtml = fs.readFileSync(staticOut, 'utf8');
  assert.ok(!staticHtml.includes('<script'));

  // -f svg must be untouched by the HTML flags
  const plain = cli('-i', hero);
  const withFlags = cli('-i', hero, '--interactive');
  assert.ok(plain.startsWith('<svg'));
  assert.equal(plain, withFlags);
});

test('CLI renders with craft defaults and reports presets', () => {
  const out = path.join(fs.mkdtempSync('/tmp/bm-'), 'out.svg');
  execFileSync(
    'node',
    [path.join(SKILL_DIR, 'scripts', 'render_mermaid.js'), '-i', path.join(EXAMPLES, 'hero.mmd'), '-o', out],
    { cwd: SKILL_DIR, stdio: 'ignore' }
  );
  const svg = fs.readFileSync(out, 'utf8');
  assert.match(svg, new RegExp(`viewBox="${HERO.viewBox}"`));

  const presets = execFileSync(
    'node',
    [path.join(SKILL_DIR, 'scripts', 'render_mermaid.js'), '--list-presets'],
    { cwd: SKILL_DIR, encoding: 'utf8' }
  );
  for (const name of Object.keys(PRESETS)) assert.ok(presets.includes(name));
});
