'use strict';

/**
 * Shared presets and helpers for the beautiful-mermaid skill.
 *
 * A preset separates *presentation* (colors, spacing, font, transparency)
 * from *Mermaid semantics* (the .mmd source). Diagram sources should never
 * carry colors; the preset owns all visual decisions.
 */

const SYSTEM_FONT_STACK =
  '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';

/** Craft-style spacing used by https://agents.craft.do/mermaid */
const CRAFT_SPACING = {
  padding: 40,
  nodeSpacing: 28,
  layerSpacing: 48,
};

/**
 * Preset definitions.
 * `theme` names a built-in THEMES entry; remaining keys are RenderOptions.
 */
const PRESETS = {
  // Default: monochrome light, transparent, Inter — matches the Craft sample.
  craft: {
    description: 'Craft mono light, transparent, Inter (default)',
    theme: 'zinc-light',
    transparent: true,
    font: 'Inter',
    ...CRAFT_SPACING,
  },
  // Same restraint for dark containers.
  'craft-dark': {
    description: 'Craft mono dark, transparent, Inter',
    theme: 'zinc-dark',
    transparent: true,
    font: 'Inter',
    ...CRAFT_SPACING,
  },
  // Backwards-compatible opaque colored output (pre-refresh behavior).
  legacy: {
    description: 'Pre-refresh default: opaque tokyo-night',
    theme: 'tokyo-night',
    transparent: false,
    font: 'Inter',
    padding: 40,
  },
};

const DEFAULT_PRESET = 'craft';

/** Load the ESM package from CJS. Throws a friendly error when missing. */
async function loadPackage() {
  try {
    return await import('beautiful-mermaid');
  } catch (error) {
    if (
      error.code === 'ERR_MODULE_NOT_FOUND' ||
      /Cannot find package/.test(error.message || '')
    ) {
      const hint = new Error(
        'beautiful-mermaid is not installed. Run: node scripts/setup_check.js --install'
      );
      hint.code = 'BM_NOT_INSTALLED';
      throw hint;
    }
    throw error;
  }
}

/**
 * Resolve final RenderOptions.
 *
 * Precedence: preset < explicit --theme < explicit overrides (font/spacing/…).
 */
function resolveRenderOptions(THEMES, opts = {}) {
  const presetName = opts.preset || DEFAULT_PRESET;
  const preset = PRESETS[presetName];
  if (!preset) {
    throw new Error(
      `Unknown preset '${presetName}'. Available: ${Object.keys(PRESETS).join(', ')}`
    );
  }

  const themeName = opts.theme || preset.theme;
  const themeColors = THEMES[themeName];
  if (!themeColors) {
    throw new Error(
      `Unknown theme '${themeName}'. Available: ${Object.keys(THEMES).join(', ')}`
    );
  }

  const { description: _d, theme: _t, ...presetOptions } = preset;
  const resolved = { ...themeColors, ...presetOptions };

  if (opts.transparent !== undefined) resolved.transparent = opts.transparent;
  if (opts.font) resolved.font = opts.font;
  if (opts.padding !== undefined) resolved.padding = opts.padding;
  if (opts.nodeSpacing !== undefined) resolved.nodeSpacing = opts.nodeSpacing;
  if (opts.layerSpacing !== undefined) resolved.layerSpacing = opts.layerSpacing;
  if (opts.componentSpacing !== undefined) {
    resolved.componentSpacing = opts.componentSpacing;
  }
  if (opts.interactive !== undefined) resolved.interactive = opts.interactive;

  // Offline output must not depend on Google Fonts.
  if (opts.offline) resolved.font = SYSTEM_FONT_STACK;

  return { presetName, themeName, options: resolved };
}

/** Remove remote @import font rules so the SVG is fully self-contained. */
function stripRemoteFontImports(svg) {
  return svg.replace(/@import\s+url\((['"]?)https?:\/\/[^)]*\1\);?/g, '');
}

/** Render SVG through the primary synchronous API. */
async function renderSVG(source, opts = {}) {
  const { renderMermaidSVG, THEMES } = await loadPackage();
  const resolved = resolveRenderOptions(THEMES, opts);
  let svg = renderMermaidSVG(source, resolved.options);
  if (opts.offline) svg = stripRemoteFontImports(svg);
  return { svg, ...resolved };
}

/** Render ASCII/Unicode through the primary synchronous API. */
async function renderASCII(source, opts = {}) {
  const { renderMermaidASCII } = await loadPackage();
  return renderMermaidASCII(source, {
    useAscii: Boolean(opts.useAscii),
    colorMode: opts.colorMode || 'none',
  });
}

module.exports = {
  PRESETS,
  DEFAULT_PRESET,
  CRAFT_SPACING,
  SYSTEM_FONT_STACK,
  loadPackage,
  resolveRenderOptions,
  stripRemoteFontImports,
  renderSVG,
  renderASCII,
};
