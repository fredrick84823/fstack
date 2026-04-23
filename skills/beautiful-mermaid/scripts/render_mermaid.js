#!/usr/bin/env node

/**
 * Beautiful Mermaid Renderer
 * 
 * Renders Mermaid diagrams to SVG using the beautiful-mermaid package.
 * Supports both themed SVG output and standalone SVG files.
 */

const fs = require('fs');
const path = require('path');

// Parse command line arguments
const args = process.argv.slice(2);
const options = {
  input: null,
  output: null,
  theme: 'tokyo-night',
  format: 'svg', // 'svg' or 'html'
  transparent: false,
};

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
    case '--help':
    case '-h':
      printHelp();
      process.exit(0);
      break;
    default:
      console.error(`Unknown option: ${arg}`);
      printHelp();
      process.exit(1);
  }
}

function printHelp() {
  console.log(`
Beautiful Mermaid Renderer

Usage:
  node render_mermaid.js --input <file> --output <file> [options]

Options:
  -i, --input <file>       Input Mermaid file (.mmd or .txt)
  -o, --output <file>      Output file (.svg or .html)
  -t, --theme <name>       Theme name (default: tokyo-night)
  -f, --format <type>      Output format: 'svg' or 'html' (default: svg)
  --transparent            Make background transparent
  -h, --help               Show this help message

Available themes:
  zinc-light, zinc-dark, tokyo-night, tokyo-night-storm, tokyo-night-light,
  catppuccin-mocha, catppuccin-latte, nord, nord-light, dracula,
  github-light, github-dark, solarized-light, solarized-dark, one-dark

Examples:
  # Render with default theme
  node render_mermaid.js -i diagram.mmd -o diagram.svg

  # Render with specific theme
  node render_mermaid.js -i diagram.mmd -o diagram.svg -t nord

  # Render as HTML with embedded SVG
  node render_mermaid.js -i diagram.mmd -o diagram.html -f html

  # Render with transparent background
  node render_mermaid.js -i diagram.mmd -o diagram.svg --transparent
`);
}

async function main() {
  // Validate required arguments
  if (!options.input || !options.output) {
    console.error('Error: --input and --output are required');
    printHelp();
    process.exit(1);
  }

  // Check if input file exists
  if (!fs.existsSync(options.input)) {
    console.error(`Error: Input file not found: ${options.input}`);
    process.exit(1);
  }

  try {
    // Dynamically import beautiful-mermaid
    const { renderMermaid, THEMES } = await import('beautiful-mermaid');

    // Read Mermaid source
    const mermaidCode = fs.readFileSync(options.input, 'utf8');

    // Get theme configuration
    let themeConfig;
    if (THEMES[options.theme]) {
      themeConfig = THEMES[options.theme];
    } else {
      console.error(`Warning: Theme '${options.theme}' not found. Using tokyo-night.`);
      themeConfig = THEMES['tokyo-night'];
    }

    // Apply transparent background if requested
    if (options.transparent) {
      themeConfig = { ...themeConfig, transparent: true };
    }

    // Render to SVG
    console.log(`Rendering diagram with theme: ${options.theme}`);
    const svg = await renderMermaid(mermaidCode, themeConfig);

    // Generate output based on format
    let outputContent;
    if (options.format === 'html') {
      outputContent = generateHTML(svg, options.theme);
    } else {
      outputContent = svg;
    }

    // Write output file
    fs.writeFileSync(options.output, outputContent, 'utf8');
    console.log(`✅ Successfully rendered to: ${options.output}`);

  } catch (error) {
    if (error.code === 'ERR_MODULE_NOT_FOUND' || error.message.includes('Cannot find package')) {
      console.error(`
❌ Error: beautiful-mermaid package not found.

Please install it first:
  npm install beautiful-mermaid
  # or
  npm install -g beautiful-mermaid
  # or
  pnpm add beautiful-mermaid
  # or
  bun add beautiful-mermaid

Then try again.
`);
      process.exit(1);
    } else {
      console.error(`Error rendering diagram: ${error.message}`);
      console.error(error.stack);
      process.exit(1);
    }
  }
}

function generateHTML(svg, themeName) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Mermaid Diagram - ${themeName}</title>
  <style>
    body {
      margin: 0;
      padding: 20px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      background: #f5f5f5;
    }
    .container {
      background: white;
      padding: 30px;
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    svg {
      max-width: 100%;
      height: auto;
    }
  </style>
</head>
<body>
  <div class="container">
    ${svg}
  </div>
</body>
</html>`;
}

main();
