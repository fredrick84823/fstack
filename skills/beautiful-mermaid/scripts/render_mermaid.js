#!/usr/bin/env node
'use strict';

/**
 * Beautiful Mermaid Renderer (CLI)
 *
 * Single render path: beautiful-mermaid `renderMermaidSVG()` / `renderMermaidASCII()`.
 * Presentation comes from a preset; the default `craft` preset reproduces the
 * Craft sample look (mono zinc-light, transparent, Inter, 40/28/48 spacing).
 */

const fs = require('fs');
const path = require('path');
const {
  PRESETS,
  DEFAULT_PRESET,
  renderSVG,
  renderASCII,
  loadPackage,
} = require('./lib/presets');
const { staticHTML, interactiveHTML } = require('./lib/html');

const options = {
  input: null,
  output: null,
  preset: DEFAULT_PRESET,
  theme: null,
  format: 'svg', // svg | html | ascii
  transparent: undefined,
  offline: false,
  font: null,
  padding: undefined,
  nodeSpacing: undefined,
  layerSpacing: undefined,
  useAscii: false,
  // HTML interactivity (pan/zoom). null = default per format.
  htmlInteractive: null,
};

function num(value, flag) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    fail(`Option ${flag} expects a number, got '${value}'`);
  }
  return parsed;
}

function fail(message) {
  console.error(`Error: ${message}`);
  process.exit(1);
}

function printHelp() {
  const presetList = Object.entries(PRESETS)
    .map(([name, p]) => `  ${name.padEnd(12)} ${p.description}`)
    .join('\n');
  console.log(`
Beautiful Mermaid Renderer

Usage:
  node render_mermaid.js --input <file> [--output <file>] [options]

Options:
  -i, --input <file>       Input Mermaid file (.mmd or .txt); '-' reads stdin
  -o, --output <file>      Output file; omit to write to stdout
  -p, --preset <name>      Presentation preset (default: ${DEFAULT_PRESET})
  -t, --theme <name>       Theme override (explicit opt-in, kept for compatibility)
  -f, --format <type>      svg | html | ascii (default: svg)
      --interactive        HTML output: pan/zoom viewer (default for -f html)
      --static             HTML output: plain embedded SVG, no script
      --transparent        Force transparent background
      --opaque             Force opaque background
      --offline            No remote fonts: system font stack, strip @import
      --font <family>      Font family override
      --padding <px>       Canvas padding
      --node-spacing <px>  Spacing between sibling nodes
      --layer-spacing <px> Spacing between layers
      --ascii-chars        ASCII format: use +-|> instead of box-drawing
      --list-presets       Print presets and exit
      --list-themes        Print available theme names and exit
  -h, --help               Show this help

Presets:
${presetList}

Examples:
  # Default Craft look (mono, transparent, Inter)
  node render_mermaid.js -i diagram.mmd -o diagram.svg

  # Dark container
  node render_mermaid.js -i diagram.mmd -o diagram.svg -p craft-dark

  # Explicit theme override (backwards compatible)
  node render_mermaid.js -i diagram.mmd -o diagram.svg -t nord

  # Fully offline SVG (no Google Fonts import)
  node render_mermaid.js -i diagram.mmd -o diagram.svg --offline

  # Interactive HTML viewer (wheel zoom, drag pan, f/0/+/-)
  node render_mermaid.js -i diagram.mmd -o diagram.html -f html

  # Static HTML (no script, e.g. for further embedding)
  node render_mermaid.js -i diagram.mmd -o diagram.html -f html --static

  # Terminal preview
  node render_mermaid.js -i diagram.mmd -f ascii
`);
}

async function parseArgs(args) {
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    switch (arg) {
      case '--input':
      case '-i':
        options.input = args[++i];
        break;
      case '--output':
      case '-o':
        options.output = args[++i];
        break;
      case '--preset':
      case '-p':
        options.preset = args[++i];
        break;
      case '--theme':
      case '-t':
        options.theme = args[++i];
        break;
      case '--format':
      case '-f':
        options.format = args[++i];
        break;
      case '--transparent':
        options.transparent = true;
        break;
      case '--opaque':
        options.transparent = false;
        break;
      case '--offline':
        options.offline = true;
        break;
      case '--font':
        options.font = args[++i];
        break;
      case '--padding':
        options.padding = num(args[++i], '--padding');
        break;
      case '--node-spacing':
        options.nodeSpacing = num(args[++i], '--node-spacing');
        break;
      case '--layer-spacing':
        options.layerSpacing = num(args[++i], '--layer-spacing');
        break;
      case '--ascii-chars':
        options.useAscii = true;
        break;
      case '--interactive':
        options.htmlInteractive = true;
        break;
      case '--static':
        options.htmlInteractive = false;
        break;
      case '--list-presets':
        Object.entries(PRESETS).forEach(([name, p]) =>
          console.log(`${name}\t${p.description}`)
        );
        process.exit(0);
        break;
      case '--list-themes': {
        const { THEMES } = await loadPackage();
        Object.keys(THEMES).forEach((t) => console.log(t));
        process.exit(0);
        break;
      }
      case '--help':
      case '-h':
        printHelp();
        process.exit(0);
        break;
      default:
        fail(`Unknown option: ${arg}`);
    }
  }
}

function readSource() {
  if (options.input === '-') return fs.readFileSync(0, 'utf8');
  if (!fs.existsSync(options.input)) {
    fail(`Input file not found: ${options.input}`);
  }
  return fs.readFileSync(options.input, 'utf8');
}

/**
 * HTML wrapper selection. `-f html` defaults to the interactive viewer;
 * `--static` falls back to the plain embedded-SVG document.
 */
function generateHTML(svg, ctx) {
  const interactive = options.htmlInteractive !== false;
  return interactive ? interactiveHTML(svg, ctx) : staticHTML(svg, ctx);
}

function write(content) {
  if (options.output) {
    fs.mkdirSync(path.dirname(path.resolve(options.output)), { recursive: true });
    fs.writeFileSync(options.output, content, 'utf8');
    console.error(`Wrote ${options.output}`);
  } else {
    process.stdout.write(content.endsWith('\n') ? content : `${content}\n`);
  }
}

async function main() {
  await parseArgs(process.argv.slice(2));

  if (!options.input) fail('--input is required (use - for stdin)');
  if (!['svg', 'html', 'ascii'].includes(options.format)) {
    fail(`--format must be svg, html or ascii (got '${options.format}')`);
  }

  const source = readSource();

  try {
    if (options.format === 'ascii') {
      write(await renderASCII(source, options));
      return;
    }

    const { svg, presetName, themeName } = await renderSVG(source, options);
    write(
      options.format === 'html'
        ? generateHTML(svg, { presetName, themeName, offline: options.offline })
        : svg
    );
  } catch (error) {
    if (error.code === 'BM_NOT_INSTALLED') fail(error.message);
    fail(`${error.message}\n${error.stack || ''}`);
  }
}

main();
