#!/usr/bin/env node

/**
 * Quick test to verify the timing fix
 *
 * This test sends a small amount of audio data to the daemon and checks
 * if it completes naturally without premature termination.
 *
 * @author @darianrosebrook
 */

import { spawn } from "child_process";
import { WebSocket } from "ws";

const TEST_CONFIG = {
  daemonPort: 8081,
  testDuration: 5000, // 5 seconds
};

async function testTimingFix() {
  console.log("🧪 Testing timing fix...");

  let daemonProcess = null;
  let ws = null;

  // Add signal handlers for graceful shutdown
  const cleanup = () => {
    console.log("\n🛑 Cleaning up...");
    if (ws) {
      ws.close();
    }
    if (daemonProcess) {
      daemonProcess.kill("SIGTERM");
    }
    process.exit(0);
  };

  process.on("SIGINT", cleanup);
  process.on("SIGTERM", cleanup);

  // Start the daemon
  console.log("🚀 Starting audio daemon...");
  daemonProcess = spawn(
    "node",
    ["bin/audio-daemon.js", "--port", TEST_CONFIG.daemonPort.toString()],
    {
      stdio: ["ignore", "pipe", "pipe"],
    }
  );

  // Wait for daemon to start
  await new Promise((resolve) => setTimeout(resolve, 2000));

  // Connect to daemon
  console.log("🔌 Connecting to daemon...");
  ws = new WebSocket(`ws://localhost:${TEST_CONFIG.daemonPort}`);

  await new Promise((resolve, reject) => {
    ws.on("open", resolve);
    ws.on("error", reject);
    setTimeout(() => reject(new Error("WebSocket connection timeout")), 5000);
  });

  console.log("✅ Connected to daemon");

  // Start audio playback
  console.log("🎵 Starting audio playback...");
  ws.send(
    JSON.stringify({
      type: "control",
      timestamp: Date.now(),
      data: { action: "play" },
    })
  );

  // Send some test audio data (simulate 2 seconds of audio)
  const sampleRate = 24000;
  const channels = 1;
  const bitDepth = 16;
  const bytesPerSecond = sampleRate * channels * (bitDepth / 8);
  const testDurationMs = 2000; // 2 seconds
  const totalBytes = Math.floor((bytesPerSecond * testDurationMs) / 1000);

  console.log(`📊 Sending ${totalBytes} bytes of test audio (${testDurationMs}ms duration)`);

  // Send audio in chunks
  const chunkSize = 1024;
  let bytesSent = 0;
  const startTime = Date.now();

  while (bytesSent < totalBytes) {
    const remainingBytes = totalBytes - bytesSent;
    const currentChunkSize = Math.min(chunkSize, remainingBytes);

    // Create dummy audio data (silence)
    const chunk = Buffer.alloc(currentChunkSize, 0);

    ws.send(
      JSON.stringify({
        type: "audio_chunk",
        timestamp: Date.now(),
        data: {
          chunk: chunk.toString("base64"),
          format: {
            sampleRate,
            channels,
            bitDepth,
          },
          sequence: Math.floor(bytesSent / chunkSize),
        },
      })
    );

    bytesSent += currentChunkSize;

    // Small delay between chunks
    await new Promise((resolve) => setTimeout(resolve, 10));
  }

  console.log(`✅ Sent ${bytesSent} bytes in ${Date.now() - startTime}ms`);

  // Send end_stream message
  console.log("🛑 Sending end_stream message...");
  ws.send(
    JSON.stringify({
      type: "control",
      timestamp: Date.now(),
      data: { action: "end_stream" },
    })
  );

  // Wait for completion
  let completed = false;
  let timeout = false;

  const completionPromise = new Promise((resolve) => {
    ws.on("message", (data) => {
      const message = JSON.parse(data.toString());
      console.log("📨 Received message:", message.type);

      if (message.type === "completed") {
        console.log("✅ Received completion message!");
        completed = true;
        resolve();
      }
    });
  });

  const timeoutPromise = new Promise((resolve) => {
    setTimeout(() => {
      console.log("⏰ Timeout waiting for completion");
      timeout = true;
      resolve();
    }, 10000); // 10 second timeout
  });

  await Promise.race([completionPromise, timeoutPromise]);

  // Cleanup
  console.log("🧹 Cleaning up...");
  ws.close();
  daemonProcess.kill("SIGTERM");

  // Wait a moment for cleanup
  await new Promise((resolve) => setTimeout(resolve, 1000));

  if (completed) {
    console.log("🎉 Timing fix test PASSED - audio completed naturally!");
    process.exit(0);
  } else {
    console.log("❌ Timing fix test FAILED - audio did not complete naturally");
    process.exit(1);
  }
}

testTimingFix().catch((error) => {
  console.error("❌ Test failed:", error);
  process.exit(1);
});
