#!/usr/bin/env node
'use strict';

/**
 * Beautiful Mermaid Setup Checker / Bootstrapper
 *
 * `node scripts/setup_check.js`            verify only
 * `node scripts/setup_check.js --install`  deterministic install (npm ci) then verify
 */

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { PRESETS, DEFAULT_PRESET } = require('./lib/presets');

const SKILL_DIR = path.resolve(__dirname, '..');
const REQUIRED_EXPORTS = [
  'renderMermaidSVG',
  'renderMermaidASCII',
  'renderMermaidSVGAsync',
  'THEMES',
  'DEFAULTS',
  'parseMermaid',
];

function bootstrap() {
  const hasLock = fs.existsSync(path.join(SKILL_DIR, 'package-lock.json'));
  const cmd = hasLock ? ['ci'] : ['install'];
  console.log(`Installing dependencies: npm ${cmd.join(' ')} (cwd: ${SKILL_DIR})`);
  execFileSync('npm', [...cmd, '--no-audit', '--no-fund'], {
    cwd: SKILL_DIR,
    stdio: 'inherit',
  });
}

async function verify() {
  let pkg;
  try {
    pkg = await import('beautiful-mermaid');
  } catch (error) {
    console.log('beautiful-mermaid is NOT importable.\n');
    console.log('Deterministic fix (recommended):');
    console.log('  node scripts/setup_check.js --install');
    console.log('\nManual alternatives:');
    console.log(`  cd ${SKILL_DIR} && npm ci      # honors package-lock.json`);
    console.log(`  cd ${SKILL_DIR} && npm install # updates the lockfile`);
    return false;
  }

  const missing = REQUIRED_EXPORTS.filter((name) => !(name in pkg));
  const version = readInstalledVersion();

  console.log(`beautiful-mermaid ${version || '(version unknown)'} is installed.`);
  if (missing.length) {
    console.log(`\nMissing expected exports: ${missing.join(', ')}`);
    console.log('The skill targets beautiful-mermaid 1.1.x API.');
    return false;
  }
  console.log('API check: renderMermaidSVG / renderMermaidASCII available.');

  console.log(`\nPresets (default: ${DEFAULT_PRESET}):`);
  Object.entries(PRESETS).forEach(([name, p]) => {
    console.log(`  ${name.padEnd(12)} ${p.description}`);
  });

  console.log('\nThemes (explicit --theme override only):');
  console.log(`  ${Object.keys(pkg.THEMES).join(', ')}`);

  // Smoke render through the primary sync API.
  const svg = pkg.renderMermaidSVG('graph LR\n  A --> B', {
    ...pkg.THEMES['zinc-light'],
    transparent: true,
  });
  const ok = svg.startsWith('<svg') && svg.includes('class="node"');
  console.log(`\nSmoke render: ${ok ? 'ok' : 'FAILED'}`);
  return ok;
}

function readInstalledVersion() {
  try {
    return require(
      path.join(SKILL_DIR, 'node_modules', 'beautiful-mermaid', 'package.json')
    ).version;
  } catch {
    return null;
  }
}

async function main() {
  const args = process.argv.slice(2);
  if (args.includes('--help') || args.includes('-h')) {
    console.log('Usage: node scripts/setup_check.js [--install]');
    return;
  }
  if (args.includes('--install')) bootstrap();

  const ok = await verify();
  process.exit(ok ? 0 : 1);
}

main();
