#!/usr/bin/env node

/**
 * Test script for audio daemon dependencies
 * @author @darianrosebrook
 */

console.log("Testing audio daemon dependencies...");

try {
  console.log("1. Testing WebSocket import...");
  const { WebSocket, WebSocketServer } = await import("ws");
  console.log("✅ WebSocket import successful");
  
  console.log("2. Testing speaker import...");
  const speaker = await import("speaker");
  console.log("✅ Speaker import successful");
  
  console.log("3. Testing wav-decoder import...");
  const wavDecoder = await import("wav-decoder");
  console.log("✅ WAV decoder import successful");
  
  console.log("4. Testing HTTP module...");
  const http = await import("http");
  console.log("✅ HTTP module import successful");
  
  console.log("5. Testing child_process module...");
  const { spawn } = await import("child_process");
  console.log("✅ Child process module import successful");
  
  console.log("6. Testing events module...");
  const { EventEmitter } = await import("events");
  console.log("✅ Events module import successful");
  
  console.log("\n🎉 All dependencies are working correctly!");
  console.log("Node.js version:", process.version);
  console.log("Current working directory:", process.cwd());
  console.log("Module resolution working properly.");
  
} catch (error) {
  console.error("❌ Dependency test failed:", error.message);
  console.error("Error details:", error);
  process.exit(1);
}
