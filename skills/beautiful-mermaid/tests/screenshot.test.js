'use strict';

/**
 * Chromium screenshot regression.
 *
 * Skips automatically when no Chromium/Chrome binary is found.
 * Refresh baselines with:  BM_UPDATE_BASELINES=1 node --test "tests/*.test.js"
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');
const { renderSVG } = require('../scripts/lib/presets');

const SKILL_DIR = path.resolve(__dirname, '..');
const EXAMPLES = path.join(SKILL_DIR, 'assets', 'examples');
const BASELINES = path.join(__dirname, 'baselines');
const UPDATE = process.env.BM_UPDATE_BASELINES === '1';

const CASES = [
  ['hero.mmd', 'craft'],
  ['hero.mmd', 'craft-dark'],
  ['flowchart.mmd', 'craft'],
];

function findChrome() {
  if (process.env.BM_CHROME) return process.env.BM_CHROME;
  const candidates = [
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/usr/bin/google-chrome',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  ];
  // Prefer playwright's chrome-headless-shell: fast, deterministic, no profile UI.
  const pwCache = path.join(os.homedir(), 'Library/Caches/ms-playwright');
  if (fs.existsSync(pwCache)) {
    for (const dir of fs.readdirSync(pwCache)) {
      const root = path.join(pwCache, dir);
      for (const rel of [
        'chrome-headless-shell-mac-arm64/chrome-headless-shell',
        'chrome-headless-shell-mac-x64/chrome-headless-shell',
        'chrome-headless-shell-linux64/chrome-headless-shell',
        'chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing',
        'chrome-linux/chrome',
      ]) {
        const bin = path.join(root, rel);
        if (fs.existsSync(bin)) candidates.push(bin);
      }
    }
  }
  return candidates.find((p) => fs.existsSync(p)) || null;
}

/** Page wrapper: container owns the background, SVG stays transparent. */
function page(svg, preset) {
  const dark = preset.includes('dark') || preset === 'legacy';
  return `<!DOCTYPE html><meta charset="utf-8">
<style>
  html,body{margin:0;background:${dark ? '#18181b' : '#ffffff'};}
  body{padding:24px;font-family:-apple-system,sans-serif;}
  svg{max-width:100%;height:auto;display:block;}
</style>${svg}`;
}

const chrome = findChrome();

test('screenshot regression', { skip: chrome ? false : 'no Chromium/Chrome found' }, async (t) => {
  fs.mkdirSync(BASELINES, { recursive: true });
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'bm-shot-'));

  for (const [file, preset] of CASES) {
    const name = `${path.basename(file, '.mmd')}-${preset}`;
    await t.test(name, async () => {
      const source = fs.readFileSync(path.join(EXAMPLES, file), 'utf8');
      const { svg } = await renderSVG(source, { preset, offline: true });
      const html = path.join(tmp, `${name}.html`);
      const shot = path.join(tmp, `${name}.png`);
      fs.writeFileSync(html, page(svg, preset), 'utf8');

      try {
        execFileSync(
          chrome,
          [
            '--headless=new',
            '--disable-gpu',
            '--hide-scrollbars',
            '--force-device-scale-factor=1',
            '--window-size=1280,600',
            `--screenshot=${shot}`,
            `--user-data-dir=${path.join(tmp, `profile-${name}`)}`,
            `file://${html}`,
          ],
          { stdio: 'ignore', timeout: 10_000 }
        );
      } catch (error) {
        // Some macOS Chrome builds write the requested screenshot but retain a
        // background process. A completed artifact is success; any other error is real.
        if (!fs.existsSync(shot)) throw error;
      }

      assert.ok(fs.existsSync(shot), 'chrome produced no screenshot');
      const actual = fs.readFileSync(shot);
      const baseline = path.join(BASELINES, `${name}.png`);

      if (UPDATE || !fs.existsSync(baseline)) {
        fs.copyFileSync(shot, baseline);
        t.diagnostic(`baseline written: ${baseline}`);
        return;
      }

      const hash = (buf) => crypto.createHash('sha256').update(buf).digest('hex');
      const expected = fs.readFileSync(baseline);
      if (hash(actual) !== hash(expected)) {
        const failed = path.join(BASELINES, `${name}.actual.png`);
        fs.copyFileSync(shot, failed);
        assert.fail(
          `screenshot drift for ${name}\n  baseline: ${baseline}\n  actual:   ${failed}\n` +
            '  If the change is intended: BM_UPDATE_BASELINES=1 node --test "tests/*.test.js"'
        );
      }
    });
  }
});
