#!/usr/bin/env node

/**
 * Beautiful Mermaid Setup Checker
 * 
 * Checks if beautiful-mermaid is installed and provides installation guidance.
 */

async function checkInstallation() {
  console.log('🔍 Checking beautiful-mermaid installation...\n');

  try {
    // Try to import beautiful-mermaid
    const { renderMermaid, THEMES } = await import('beautiful-mermaid');
    
    console.log('✅ beautiful-mermaid is installed!\n');
    console.log('Available themes:');
    Object.keys(THEMES).forEach(theme => {
      console.log(`  - ${theme}`);
    });
    console.log('\n✨ You are ready to render beautiful diagrams!');
    
    return true;
  } catch (error) {
    console.log('❌ beautiful-mermaid is NOT installed.\n');
    console.log('Please choose an installation method:\n');
    console.log('1. Global installation (available everywhere):');
    console.log('   npm install -g beautiful-mermaid\n');
    console.log('2. Project local installation (current directory):');
    console.log('   npm install beautiful-mermaid\n');
    console.log('3. Using pnpm:');
    console.log('   pnpm add beautiful-mermaid\n');
    console.log('4. Using bun:');
    console.log('   bun add beautiful-mermaid\n');
    console.log('After installation, run this check again to verify.');
    
    return false;
  }
}

checkInstallation();
