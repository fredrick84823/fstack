#!/usr/bin/env node
// Render every `<figure class="viz" data-mmd="...">` in an HTML file into an inlined,
// pan/zoom-ready SVG, then inject the viewer runtime once. Idempotent: re-run after
// editing any .mmd source.
//
//   node inline_diagrams.mjs page.html [--preset craft|craft-dark]

import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const RENDERER = resolve(HERE, '../../beautiful-mermaid/scripts/render_mermaid.js');
const RUNTIME = resolve(HERE, '../assets/zoompan.html');

const args = process.argv.slice(2);
const htmlPath = args.find((a) => !a.startsWith('--'));
const defaultPreset = (args.find((a) => a.startsWith('--preset')) || '').split('=')[1] || 'craft';

if (!htmlPath) {
  console.error('usage: inline_diagrams.mjs <file.html> [--preset=craft|craft-dark]');
  process.exit(2);
}
if (!existsSync(RENDERER)) {
  console.error(`beautiful-mermaid renderer not found at ${RENDERER}`);
  process.exit(2);
}

const baseDir = dirname(resolve(htmlPath));
let html = readFileSync(htmlPath, 'utf8');

const attr = (tag, name) => (tag.match(new RegExp(`${name}="([^"]*)"`)) || [])[1];
const FIGURE = /<figure\b([^>]*\bdata-mmd="[^"]+"[^>]*)>([\s\S]*?)<\/figure>/g;

let count = 0;
const problems = [];

html = html.replace(FIGURE, (whole, tag, body) => {
  const src = attr(tag, 'data-mmd');
  const mmdPath = resolve(baseDir, src);
  if (!existsSync(mmdPath)) {
    problems.push(`missing source: ${src}`);
    return whole;
  }

  let svg;
  try {
    svg = execFileSync('node', [RENDERER, '-i', '-', '-p', attr(tag, 'data-preset') || defaultPreset, '--offline'], {
      input: readFileSync(mmdPath, 'utf8'),
      encoding: 'utf8',
      maxBuffer: 32 * 1024 * 1024,
    });
  } catch (e) {
    problems.push(`${src}: ${String(e.stderr || e.message).trim().split('\n').pop()}`);
    return whole;
  }

  const label = attr(tag, 'data-alt');
  if (label) svg = svg.replace('<svg ', `<svg role="img" aria-label="${label.replace(/"/g, '&quot;')}" `);

  const height = attr(tag, 'data-h');
  const stage =
    `<div class="viz-stage"${height ? ` style="height:${height}px"` : ''}>` +
    `<div class="viz-canvas">${svg.trim()}</div></div>`;

  // Drop a previously injected stage; keep the hand-written figcaption and friends.
  const rest = body.replace(/<div class="viz-stage"[\s\S]*?<\/div>\s*<\/div>/, '').trim();
  count += 1;
  return `<figure${tag}>\n${stage}\n${rest}\n</figure>`;
});

if (!/id="viz-runtime"/.test(html)) {
  const runtime = readFileSync(RUNTIME, 'utf8');
  if (!html.includes('</body>')) {
    problems.push('no </body> in the page — viewer runtime not injected');
  } else {
    html = html.replace('</body>', `${runtime}\n</body>`);
  }
}

writeFileSync(htmlPath, html);

console.log(`${count} diagram(s) inlined into ${htmlPath}`);
for (const p of problems) console.error(`  ! ${p}`);
process.exit(problems.length ? 1 : 0);
