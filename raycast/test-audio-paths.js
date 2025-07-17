#!/usr/bin/env node

/**
 * Audio Path Comparison Test
 *
 * This test compares different audio output paths to identify where
 * audio playback fails in the Raycast environment.
 *
 * Tests:
 * 1. Direct sox playback (simple path)
 * 2. Direct ffplay playback (simple path)
 * 3. Daemon path with sox
 * 4. Daemon path with ffplay
 *
 * @author @darianrosebrook
 * @version 1.0.0
 * @since 2025-01-20
 */

import { spawn } from "child_process";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import fs from "fs";
import { promisify } from "util";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const writeFileAsync = promisify(fs.writeFile);
const unlinkAsync = promisify(fs.unlink);

/**
 * Test configuration
 */
const TEST_CONFIG = {
  daemonPath: join(__dirname, "bin/audio-daemon.js"),
  port: 8082, // Different port to avoid conflicts
  sampleRate: 24000,
  channels: 1,
  bitDepth: 16,
  duration: 2000, // 2 seconds
};

/**
 * Generate test audio data (440Hz sine wave)
 */
function generateTestAudio(durationMs = 1000) {
  const samples = Math.floor((durationMs / 1000) * TEST_CONFIG.sampleRate);
  const buffer = Buffer.alloc(samples * TEST_CONFIG.channels * (TEST_CONFIG.bitDepth / 8));

  // Generate a simple sine wave (440Hz)
  const frequency = 440;
  const amplitude = 0.3;

  for (let i = 0; i < samples; i++) {
    const sample = Math.sin((2 * Math.PI * frequency * i) / TEST_CONFIG.sampleRate) * amplitude;
    const intSample = Math.round(sample * 32767);
    buffer.writeInt16LE(intSample, i * TEST_CONFIG.channels * (TEST_CONFIG.bitDepth / 8));
  }

  return buffer;
}

/**
 * Test 1: Direct sox playback (simple path)
 */
async function testDirectSox() {
  console.log("\n🔊 TEST 1: Direct Sox Playback");
  console.log("=================================");

  const audioData = generateTestAudio(TEST_CONFIG.duration);
  const tempFile = join(__dirname, `temp-audio-${Date.now()}.raw`);

  try {
    // Write audio data to temp file
    await writeFileAsync(tempFile, audioData);
    console.log(`✅ Wrote ${audioData.length} bytes to ${tempFile}`);

    // Play with sox
    const soxArgs = [
      "-t",
      "raw",
      "-e",
      "signed-integer",
      "-b",
      TEST_CONFIG.bitDepth.toString(),
      "-c",
      TEST_CONFIG.channels.toString(),
      "-r",
      TEST_CONFIG.sampleRate.toString(),
      tempFile,
      "-d", // Output to default audio device
      "--no-show-progress",
    ];

    console.log("🎵 Playing with sox:", soxArgs.join(" "));

    return new Promise((resolve, reject) => {
      const soxProcess = spawn("sox", soxArgs, {
        stdio: ["ignore", "pipe", "pipe"],
      });

      let stdout = "";
      let stderr = "";

      soxProcess.stdout.on("data", (data) => {
        stdout += data.toString();
      });

      soxProcess.stderr.on("data", (data) => {
        stderr += data.toString();
      });

      soxProcess.on("close", async (code) => {
        console.log(`✅ Sox process exited with code ${code}`);
        if (stdout) console.log("Sox stdout:", stdout);
        if (stderr) console.log("Sox stderr:", stderr);

        // Cleanup temp file AFTER sox finishes
        try {
          await unlinkAsync(tempFile);
          console.log("🧹 Cleaned up temp file");
        } catch (error) {
          console.warn("⚠️ Failed to cleanup temp file:", error.message);
        }

        resolve({ success: code === 0, stdout, stderr });
      });

      soxProcess.on("error", (error) => {
        console.error("❌ Sox process error:", error.message);
        reject(error);
      });

      // Timeout after 5 seconds
      setTimeout(() => {
        soxProcess.kill("SIGTERM");
        resolve({ success: false, stdout, stderr, timeout: true });
      }, 5000);
    });
  } catch (error) {
    console.error("❌ Test setup failed:", error.message);
    return { success: false, error: error.message };
  }
}

/**
 * Test 2: Direct ffplay playback (simple path)
 */
async function testDirectFfplay() {
  console.log("\n🔊 TEST 2: Direct Ffplay Playback");
  console.log("===================================");

  const audioData = generateTestAudio(TEST_CONFIG.duration);
  const tempFile = join(__dirname, `temp-audio-${Date.now()}.raw`);

  try {
    // Write audio data to temp file
    await writeFileAsync(tempFile, audioData);
    console.log(`✅ Wrote ${audioData.length} bytes to ${tempFile}`);

    // Play with ffplay - FIXED syntax
    const ffplayArgs = [
      "-f",
      "s16le",
      "-ar",
      TEST_CONFIG.sampleRate.toString(),
      "-ac",
      TEST_CONFIG.channels.toString(),
      "-i",
      tempFile,
      "-nodisp",
      "-autoexit",
      "-hide_banner",
      "-loglevel",
      "error", // Reduce noise
    ];

    console.log("🎵 Playing with ffplay:", ffplayArgs.join(" "));

    return new Promise((resolve, reject) => {
      const ffplayProcess = spawn("ffplay", ffplayArgs, {
        stdio: ["ignore", "pipe", "pipe"],
      });

      let stdout = "";
      let stderr = "";

      ffplayProcess.stdout.on("data", (data) => {
        stdout += data.toString();
      });

      ffplayProcess.stderr.on("data", (data) => {
        stderr += data.toString();
      });

      ffplayProcess.on("close", async (code) => {
        console.log(`✅ Ffplay process exited with code ${code}`);
        if (stdout) console.log("Ffplay stdout:", stdout);
        if (stderr) console.log("Ffplay stderr:", stderr);

        // Cleanup temp file AFTER ffplay finishes
        try {
          await unlinkAsync(tempFile);
          console.log("🧹 Cleaned up temp file");
        } catch (error) {
          console.warn("⚠️ Failed to cleanup temp file:", error.message);
        }

        resolve({ success: code === 0, stdout, stderr });
      });

      ffplayProcess.on("error", (error) => {
        console.error("❌ Ffplay process error:", error.message);
        reject(error);
      });

      // Timeout after 5 seconds
      setTimeout(() => {
        ffplayProcess.kill("SIGTERM");
        resolve({ success: false, stdout, stderr, timeout: true });
      }, 5000);
    });
  } catch (error) {
    console.error("❌ Test setup failed:", error.message);
    return { success: false, error: error.message };
  }
}

/**
 * Test 3: Daemon path with sox
 */
async function testDaemonSox() {
  console.log("\n🔊 TEST 3: Daemon Path with Sox");
  console.log("=================================");

  return new Promise(async (resolve, reject) => {
    try {
      // Start daemon
      console.log("🚀 Starting daemon...");
      const daemon = spawn(
        "node",
        [TEST_CONFIG.daemonPath, "--port", TEST_CONFIG.port.toString()],
        {
          stdio: ["pipe", "pipe", "pipe"],
        }
      );

      let daemonStarted = false;
      let ws = null;

      daemon.stdout.on("data", (data) => {
        const output = data.toString();
        console.log("Daemon stdout:", output.trim());
        if (output.includes("Audio Daemon listening on port")) {
          daemonStarted = true;
        }
      });

      daemon.stderr.on("data", (data) => {
        console.log("Daemon stderr:", data.toString().trim());
      });

      // Wait for daemon to start
      await new Promise((resolve) => setTimeout(resolve, 2000));

      if (!daemonStarted) {
        throw new Error("Daemon failed to start");
      }

      // Connect WebSocket
      console.log("🔌 Connecting WebSocket...");
      const { WebSocket } = await import("ws");
      ws = new WebSocket(`ws://localhost:${TEST_CONFIG.port}`);

      ws.on("open", async () => {
        console.log("✅ WebSocket connected");

        // Send start message
        const startMessage = {
          type: "control",
          timestamp: Date.now(),
          data: { action: "play" },
        };
        ws.send(JSON.stringify(startMessage));

        // Send audio chunks
        const audioData = generateTestAudio(TEST_CONFIG.duration);
        const chunkSize = 1200; // 50ms chunks (optimal from benchmark)
        const chunkDelay = 5; // 5ms delivery rate (optimal from benchmark)
        const chunks = [];

        for (let i = 0; i < audioData.length; i += chunkSize) {
          chunks.push(audioData.slice(i, i + chunkSize));
        }

        console.log(`📦 Sending ${chunks.length} audio chunks...`);

        for (let i = 0; i < chunks.length; i++) {
          const chunk = chunks[i];
          const audioMessage = {
            type: "audio_chunk",
            timestamp: Date.now(),
            data: {
              chunk: chunk.toString("base64"),
              format: {
                format: "pcm",
                sampleRate: TEST_CONFIG.sampleRate,
                channels: TEST_CONFIG.channels,
                bitDepth: TEST_CONFIG.bitDepth,
              },
              sequence: i,
            },
          };

          ws.send(JSON.stringify(audioMessage));
          await new Promise((resolve) => setTimeout(resolve, chunkDelay)); // 5ms delay between chunks
        }

        // Send stop message
        setTimeout(() => {
          const stopMessage = {
            type: "control",
            timestamp: Date.now(),
            data: { action: "stop" },
          };
          ws.send(JSON.stringify(stopMessage));

          // Cleanup
          setTimeout(() => {
            ws.close();
            daemon.kill("SIGTERM");
            resolve({ success: true });
          }, 1000);
        }, 3000);
      });

      ws.on("message", (data) => {
        try {
          const message = JSON.parse(data.toString());
          console.log("📨 Received:", message.type);
        } catch (error) {
          console.error("❌ Failed to parse message:", error);
        }
      });

      ws.on("error", (error) => {
        console.error("❌ WebSocket error:", error.message);
        reject(error);
      });
    } catch (error) {
      console.error("❌ Test failed:", error.message);
      reject(error);
    }
  });
}

/**
 * Run all tests
 */
async function runAllTests() {
  console.log("🚀 Starting Audio Path Comparison Tests");
  console.log("========================================");

  const results = {};

  try {
    // Test 1: Direct sox
    results.directSox = await testDirectSox();

    // Wait between tests
    await new Promise((resolve) => setTimeout(resolve, 2000));

    // Test 2: Direct ffplay
    results.directFfplay = await testDirectFfplay();

    // Wait between tests
    await new Promise((resolve) => setTimeout(resolve, 2000));

    // Test 3: Daemon path
    results.daemonSox = await testDaemonSox();
  } catch (error) {
    console.error("❌ Test suite failed:", error.message);
  }

  // Summary
  console.log("\n📊 TEST RESULTS SUMMARY");
  console.log("========================");
  console.log("Direct Sox:", results.directSox?.success ? "✅ PASS" : "❌ FAIL");
  console.log("Direct Ffplay:", results.directFfplay?.success ? "✅ PASS" : "❌ FAIL");
  console.log("Daemon Sox:", results.daemonSox?.success ? "✅ PASS" : "❌ FAIL");

  return results;
}

// Run tests if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  runAllTests().catch(console.error);
}
