#!/usr/bin/env node

// Simple debug test script
const DEBUG_MODE = process.argv.includes('--debug');

console.log('Debug test starting...');

if (DEBUG_MODE) {
  console.log('DEBUG: Debug mode is enabled');
  console.log('DEBUG: Current working directory:', process.cwd());
  console.log('DEBUG: Node version:', process.version);
  console.log('DEBUG: Platform:', process.platform);
  console.log('DEBUG: Arguments:', process.argv);
}

console.log('Debug test completed successfully');
process.exit(0);








