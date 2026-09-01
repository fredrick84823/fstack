'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { pathToFileURL } = require('node:url');

const SKILL_DIR = path.resolve(__dirname, '..');
const FIXTURE = path.join(SKILL_DIR, 'assets', 'examples', 'embedded-viewer-showcase.html');
const CHROME = process.env.BM_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function waitFor(predicate, message, timeout = 10_000) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    const value = await predicate();
    if (value) return value;
    await delay(40);
  }
  throw new Error(message);
}

class CDP {
  constructor(url) { this.ws = new WebSocket(url); this.id = 0; this.pending = new Map(); }
  async open() {
    await new Promise((resolve, reject) => {
      this.ws.addEventListener('open', resolve, { once: true });
      this.ws.addEventListener('error', reject, { once: true });
    });
    this.ws.addEventListener('message', (event) => {
      const message = JSON.parse(event.data);
      if (!message.id || !this.pending.has(message.id)) return;
      const { resolve, reject } = this.pending.get(message.id);
      this.pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message));
      else resolve(message.result);
    });
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
  close() { this.ws.close(); }
}

async function evaluate(cdp, expression) {
  const result = await cdp.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
  return result.result.value;
}

async function launch() {
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'bm-browser-'));
  const child = spawn(CHROME, [
    '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank',
  ], { stdio: 'ignore' });
  const active = path.join(profile, 'DevToolsActivePort');
  const lines = await waitFor(() => fs.existsSync(active) && fs.readFileSync(active, 'utf8').trim().split('\n'), 'Chrome did not expose DevTools');
  const port = lines[0];
  const target = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(pathToFileURL(FIXTURE).href)}`, { method: 'PUT' }).then((response) => response.json());
  const cdp = new CDP(target.webSocketDebuggerUrl);
  await cdp.open();
  await cdp.send('Runtime.enable');
  await cdp.send('Page.enable');
  return { child, cdp, profile };
}

test('embedded viewers have deterministic independent browser behavior', { skip: fs.existsSync(CHROME) ? false : 'Chrome not found' }, async (t) => {
  const { child, cdp, profile } = await launch();
  t.after(() => { cdp.close(); child.kill(); fs.rmSync(profile, { recursive: true, force: true }); });
  await waitFor(() => evaluate(cdp, 'window.__mermaidViewers && window.__mermaidViewers.length === 2'), 'viewers did not initialize');

  const initial = await evaluate(cdp, `(() => ({
    count: window.__mermaidViewers.length,
    states: window.__mermaidViewers.map(v => v.state()),
    ids: [...document.querySelectorAll('[id]')].map(n => n.id),
    touchAction: getComputedStyle(document.querySelector('.mermaid-viewer__canvas')).touchAction,
    overflow: document.documentElement.scrollWidth <= document.documentElement.clientWidth,
    scrollable: document.documentElement.scrollHeight > innerHeight
  }))()`);
  assert.equal(initial.count, 2);
  assert.equal(new Set(initial.ids).size, initial.ids.length);
  assert.equal(initial.touchAction, 'pan-y');
  assert.equal(initial.overflow, true);
  assert.equal(initial.scrollable, true);

  const isolated = await evaluate(cdp, `(() => {
    const a = window.__mermaidViewers[0], b = window.__mermaidViewers[1];
    const beforeB = b.state(); a.zoomBy(1.5); a.bake();
    return { a: a.state(), beforeB, afterB: b.state() };
  })()`);
  assert.ok(isolated.a.scale > initial.states[0].scale);
  assert.deepEqual(isolated.afterB, isolated.beforeB);

  const wheel = await evaluate(cdp, `(() => {
    const canvas = document.querySelector('.mermaid-viewer__canvas');
    const viewer = window.__mermaidViewers[0]; viewer.reset();
    const plain = new WheelEvent('wheel', { deltaY: 100, bubbles: true, cancelable: true });
    canvas.dispatchEvent(plain); const afterPlain = viewer.state().scale;
    const modified = new WheelEvent('wheel', { deltaY: -40, ctrlKey: true, bubbles: true, cancelable: true });
    canvas.dispatchEvent(modified);
    return { plainPrevented: plain.defaultPrevented, modifiedPrevented: modified.defaultPrevented, afterPlain, afterModified: viewer.state().scale };
  })()`);
  assert.equal(wheel.plainPrevented, false);
  assert.equal(wheel.afterPlain, 1);
  assert.equal(wheel.modifiedPrevented, true);
  assert.ok(wheel.afterModified > 1);

  const drag = await evaluate(cdp, `(() => {
    const canvas = document.querySelector('.mermaid-viewer__canvas');
    const viewer = window.__mermaidViewers[0]; viewer.reset();
    canvas.dispatchEvent(new PointerEvent('pointerdown', { pointerId: 7, pointerType: 'mouse', button: 0, clientX: 100, clientY: 100, bubbles: true, cancelable: true }));
    canvas.dispatchEvent(new PointerEvent('pointermove', { pointerId: 7, pointerType: 'mouse', buttons: 1, clientX: 140, clientY: 125, bubbles: true }));
    canvas.dispatchEvent(new PointerEvent('pointerup', { pointerId: 7, pointerType: 'mouse', button: 0, clientX: 140, clientY: 125, bubbles: true }));
    return viewer.state();
  })()`);
  assert.ok(drag.tx >= 40);
  assert.equal(drag.ty, 25);

  const keyboard = await evaluate(cdp, `(() => {
    const roots = document.querySelectorAll('[data-mermaid-viewer]');
    const a = window.__mermaidViewers[0], b = window.__mermaidViewers[1]; a.reset(); b.reset();
    roots[0].focus(); roots[0].dispatchEvent(new KeyboardEvent('keydown', { key: '+', bubbles: true, cancelable: true }));
    return { a: a.state().scale, b: b.state().scale };
  })()`);
  assert.ok(keyboard.a > 1);
  assert.equal(keyboard.b, 1);

  const controls = await evaluate(cdp, `(() => {
    const roots = document.querySelectorAll('[data-mermaid-viewer]');
    const a = window.__mermaidViewers[0], b = window.__mermaidViewers[1];
    b.reset(); const beforeB = b.state();
    roots[0].querySelector('[data-action="reset"]').click(); const reset = a.state();
    roots[0].querySelector('[data-action="fit"]').click(); const fit = a.state();
    return { reset, fit, beforeB, afterB: b.state() };
  })()`);
  assert.equal(controls.reset.scale, 1);
  assert.ok(controls.fit.scale > 0);
  assert.deepEqual(controls.afterB, controls.beforeB);

  const touch = await evaluate(cdp, `(() => {
    const canvas = document.querySelector('.mermaid-viewer__canvas');
    const event = new Event('touchmove', { bubbles: true, cancelable: true });
    Object.defineProperty(event, 'touches', { value: [{ clientX: 10, clientY: 10 }] });
    canvas.dispatchEvent(event); return event.defaultPrevented;
  })()`);
  assert.equal(touch, false, 'single-finger touch must remain page-safe');

  await cdp.send('Emulation.setEmulatedMedia', { media: 'print' });
  const print = await evaluate(cdp, `(() => ({
    toolbar: getComputedStyle(document.querySelector('.mermaid-viewer__toolbar')).display,
    svg: getComputedStyle(document.querySelector('.mermaid-viewer__stage svg')).display
  }))()`);
  assert.equal(print.toolbar, 'none');
  assert.equal(print.svg, 'block');
  await cdp.send('Emulation.setEmulatedMedia', { media: 'screen' });

  await cdp.send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  const mobile = await evaluate(cdp, `({ overflow: document.documentElement.scrollWidth <= document.documentElement.clientWidth, width: innerWidth })`);
  assert.equal(mobile.width, 390);
  assert.equal(mobile.overflow, true);

  await cdp.send('Emulation.setScriptExecutionDisabled', { value: true });
  await cdp.send('Page.reload', { ignoreCache: true });
  await delay(300);
  const noJS = await evaluate(cdp, `(() => {
    const stage = document.querySelector('.mermaid-viewer__stage');
    const svg = stage.querySelector('svg');
    return {
      svgCount: document.querySelectorAll('.mermaid-viewer svg').length,
      text: document.body.innerText.includes('Flowchart viewer'),
      stagePosition: getComputedStyle(stage).position,
      svgMaxWidth: getComputedStyle(svg).maxWidth,
      toolbar: getComputedStyle(document.querySelector('.mermaid-viewer__toolbar')).display,
      overflow: document.documentElement.scrollWidth <= document.documentElement.clientWidth
    };
  })()`);
  assert.equal(noJS.svgCount, 2);
  assert.equal(noJS.text, true);
  assert.equal(noJS.stagePosition, 'relative');
  assert.equal(noJS.svgMaxWidth, '100%');
  assert.equal(noJS.toolbar, 'none');
  assert.equal(noJS.overflow, true);
});
