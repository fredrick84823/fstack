#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { renderSVG } = require('./lib/presets');
const { embeddedDocument } = require('./lib/html');

const SKILL_DIR = path.resolve(__dirname, '..');
const EXAMPLES = path.join(SKILL_DIR, 'assets', 'examples');
const OUT = path.join(EXAMPLES, 'embedded-viewer-showcase.html');

async function main() {
  const flow = await renderSVG(fs.readFileSync(path.join(EXAMPLES, 'flowchart.mmd'), 'utf8'), { offline: true });
  const sequence = await renderSVG(fs.readFileSync(path.join(EXAMPLES, 'sequence.mmd'), 'utf8'), { offline: true });
  const html = embeddedDocument([
    { svg: flow.svg, label: 'Authentication decision flow', caption: 'Flowchart viewer: zooming or panning here must not change the sequence viewer.' },
    { svg: sequence.svg, label: 'API request sequence', caption: 'Sequence viewer: independent state and controls.' },
  ], { title: 'Embedded Mermaid multi-viewer showcase', offline: true });
  fs.writeFileSync(OUT, html, 'utf8');
  console.log(`Wrote ${OUT}`);
}

main().catch((error) => { console.error(error); process.exit(1); });
