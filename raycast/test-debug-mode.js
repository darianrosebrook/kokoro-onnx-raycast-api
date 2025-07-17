#!/usr/bin/env node

/**
 * Test script to demonstrate debug mode functionality
 *
 * Usage:
 *   node test-debug-mode.js              # Normal mode
 *   node test-debug-mode.js --debug      # Debug mode
 *   DEBUG=true node test-debug-mode.js   # Debug mode via env var
 */

// Simulate the logger import
const logger = {
  consoleDebug: (message, ...args) => {
    if (process.argv.includes("--debug") || process.env.DEBUG === "true") {
      console.log(`[DEBUG] ${message}`, ...args);
    }
  },
  consoleInfo: (message, ...args) => {
    console.log(message, ...args);
  },
  consoleWarn: (message, ...args) => {
    console.warn(message, ...args);
  },
  consoleError: (message, ...args) => {
    console.error(message, ...args);
  },
};

console.log("🔧 Testing Debug Mode Functionality");
console.log("=====================================");

// Test normal info output (always shows)
logger.consoleInfo("This is important information that always shows");

// Test debug output (only shows in debug mode)
logger.consoleDebug("This is debug information that only shows in debug mode");
logger.consoleDebug("Debug mode can be enabled with --debug flag or DEBUG=true");

// Test warning output (always shows)
logger.consoleWarn("This is a warning that always shows");

// Test error output (always shows)
logger.consoleError("This is an error that always shows");

console.log("\n📋 Debug Mode Status:");
console.log("  --debug flag:", process.argv.includes("--debug"));
console.log("  DEBUG env var:", process.env.DEBUG);
console.log("  NODE_ENV:", process.env.NODE_ENV);
console.log("  KOKORO_DEBUG:", process.env.KOKORO_DEBUG);

console.log("\n💡 To enable debug mode, run:");
console.log("  node test-debug-mode.js --debug");
console.log("  DEBUG=true node test-debug-mode.js");
console.log("  KOKORO_DEBUG=true node test-debug-mode.js");
