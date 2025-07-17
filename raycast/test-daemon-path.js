#!/usr/bin/env node

/**
 * Test script for daemon path resolution
 * This script tests the daemon path resolution logic to ensure it works correctly
 * in the Raycast extension environment.
 */

import { join } from "path";
import { existsSync } from "fs";

console.log("🧪 Testing daemon path resolution...");

// Simulate the path resolution logic from AudioPlaybackDaemon
function testDaemonPathResolution() {
  // Detect if we're running in Raycast extension environment
  const isRaycastExtension =
    process.cwd().includes("raycast/extensions") || process.cwd().includes(".config/raycast");

  console.log("📁 Current working directory:", process.cwd());
  console.log("🔍 Is Raycast extension environment:", isRaycastExtension);

  // Define the project root path for Raycast extension environment
  let projectRoot = process.cwd();
  if (isRaycastExtension) {
    // Try to find the project root by looking for the kokoro-onnx project
    const possibleProjectRoots = [
      "/Users/darianrosebrook/Desktop/Projects/kokoro-onnx",
      process.env.KOKORO_PROJECT_ROOT,
      process.env.HOME + "/Desktop/Projects/kokoro-onnx",
      process.env.HOME + "/Projects/kokoro-onnx",
    ].filter(Boolean);

    console.log("🔍 Possible project roots:", possibleProjectRoots);

    for (const root of possibleProjectRoots) {
      const daemonPath = join(root, "raycast/bin/audio-daemon.js");
      console.log("🔍 Checking:", daemonPath);
      if (existsSync(daemonPath)) {
        projectRoot = root;
        console.log("✅ Found project root:", projectRoot);
        break;
      }
    }
  }

  const possiblePaths = [
    // Configuration path (highest priority)
    // ...(configDaemonPath ? [configDaemonPath] : []),
    // Environment variable path (second priority)
    ...(process.env.KOKORO_AUDIO_DAEMON_PATH ? [process.env.KOKORO_AUDIO_DAEMON_PATH] : []),
    // Absolute paths for Raycast extension environment
    ...(isRaycastExtension
      ? [join(projectRoot, "raycast/bin/audio-daemon.js"), join(projectRoot, "bin/audio-daemon.js")]
      : []),
    // Local extension directory paths
    join(process.cwd(), "audio-daemon.js"), // Local copy in extension directory
    // Relative paths (fallback)
    join(process.cwd(), "bin/audio-daemon.js"), // Relative to working directory
    join(process.cwd(), "raycast/bin/audio-daemon.js"), // Raycast subdirectory
  ];

  console.log("🔍 Checking possible paths:");
  possiblePaths.forEach((path, index) => {
    const exists = existsSync(path);
    console.log(`  ${index + 1}. ${path} - ${exists ? "✅ EXISTS" : "❌ NOT FOUND"}`);
  });

  // Find the first existing path
  let daemonScriptPath = "";
  for (const path of possiblePaths) {
    if (existsSync(path)) {
      daemonScriptPath = path;
      console.log("✅ Found daemon script at:", daemonScriptPath);
      break;
    }
  }

  if (!daemonScriptPath) {
    console.log("❌ No daemon script found in any expected location");
    return false;
  }

  return true;
}

// Run the test
const success = testDaemonPathResolution();

if (success) {
  console.log("🎉 Daemon path resolution test passed!");
  process.exit(0);
} else {
  console.log("❌ Daemon path resolution test failed!");
  process.exit(1);
}
