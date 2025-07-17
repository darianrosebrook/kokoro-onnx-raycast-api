#!/usr/bin/env node

/**
 * TTS Integration Test
 *
 * This test verifies that the TTS processor can successfully
 * stream audio through the audio daemon and produce audible output.
 *
 * @author @darianrosebrook
 * @version 1.0.0
 * @since 2025-01-20
 */

import { TTSSpeechProcessor } from "./src/utils/tts/tts-processor.js";

/**
 * Test configuration
 */
const TEST_CONFIG = {
  voice: "bm_fable",
  speed: "1.2", // String as expected by the processor
  serverUrl: "http://localhost:8000",
  daemonPort: "8081",
  useStreaming: true,
  developmentMode: true,
  // Add timeout configuration
  timeoutMs: 30000, // 30 seconds timeout
  healthCheckTimeoutMs: 10000, // 10 seconds for health check
};

/**
 * Test TTS server directly without daemon
 */
async function testTTSServerDirectly() {
  console.log("🧪 Testing TTS server directly...");

  const testText = "Hello, this is a direct server test.";
  const url = `${TEST_CONFIG.serverUrl}/v1/audio/speech`;

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "audio/pcm",
      },
      body: JSON.stringify({
        text: testText,
        voice: TEST_CONFIG.voice,
        speed: parseFloat(TEST_CONFIG.speed),
        lang: "en-us",
        stream: true,
        format: "pcm",
      }),
    });

    console.log("📡 Server response:", {
      status: response.status,
      statusText: response.statusText,
      ok: response.ok,
      headers: Object.fromEntries(response.headers.entries()),
    });

    if (!response.ok) {
      throw new Error(`Server error: ${response.status} ${response.statusText}`);
    }

    if (!response.body) {
      throw new Error("No response body - streaming not supported");
    }

    console.log("✅ Server test successful - streaming supported");
    return true;
  } catch (error) {
    console.error("❌ Server test failed:", error);
    return false;
  }
}

/**
 * Wait for a condition with timeout
 */
function waitForCondition(
  condition: () => boolean,
  timeoutMs: number,
  checkIntervalMs: number = 100
): Promise<boolean> {
  return new Promise((resolve) => {
    const startTime = Date.now();

    const check = () => {
      if (condition()) {
        resolve(true);
        return;
      }

      if (Date.now() - startTime > timeoutMs) {
        resolve(false);
        return;
      }

      setTimeout(check, checkIntervalMs);
    };

    check();
  });
}

/**
 * Run TTS integration test
 */
async function runTTSTest() {
  console.log("🚀 Starting TTS Integration Test");
  console.log("==================================");

  // Add overall test timeout
  const testTimeout = setTimeout(() => {
    console.error("❌ Test timeout exceeded. Forcing exit.");
    process.exit(1);
  }, TEST_CONFIG.timeoutMs);

  let processor: TTSSpeechProcessor | null = null;

  try {
    // First, test the TTS server directly
    console.log("🔍 Step 1: Testing TTS server connectivity...");
    const serverTestPassed = await testTTSServerDirectly();

    if (!serverTestPassed) {
      console.error("❌ TTS server test failed. Cannot proceed with integration test.");
      process.exit(1);
    }

    console.log("✅ TTS server test passed. Proceeding with full integration test...");

    // Create TTS processor
    console.log("🔍 Step 2: Creating TTS processor...");
    processor = new TTSSpeechProcessor({
      voice: TEST_CONFIG.voice,
      speed: TEST_CONFIG.speed,
      serverUrl: TEST_CONFIG.serverUrl,
      daemonPort: TEST_CONFIG.daemonPort,
      useStreaming: TEST_CONFIG.useStreaming,
      developmentMode: TEST_CONFIG.developmentMode,
      onStatusUpdate: (status) => {
        console.log("📊 Status:", status.message);
      },
    });

    console.log("✅ TTS Processor created");

    // Test text
    const testText =
      "Hello, this is a test of the audio daemon integration. Can you hear this audio playing through the daemon?";

    console.log(`📝 Processing text: "${testText}"`);
    console.log(`🎵 Voice: ${TEST_CONFIG.voice}, Speed: ${TEST_CONFIG.speed}`);

    // Create a promise that resolves when processing completes
    const processingPromise = processor.speak(testText);

    // Add timeout to the processing
    const timeoutPromise = new Promise((_, reject) => {
      setTimeout(() => {
        reject(new Error(`TTS processing timed out after ${TEST_CONFIG.timeoutMs}ms`));
      }, TEST_CONFIG.timeoutMs);
    });

    // Race between processing and timeout
    await Promise.race([processingPromise, timeoutPromise]);

    console.log("✅ Text processing completed");
    console.log("🔊 Audio should be playing through the daemon now!");

    // Wait a bit for audio to finish playing
    console.log("⏳ Waiting for audio playback to complete...");
    await new Promise((resolve) => setTimeout(resolve, 2000));

    console.log("✅ Test completed successfully!");
  } catch (error) {
    console.error("❌ Test failed:", error);

    // Provide more detailed error information
    if (error instanceof Error) {
      console.error("Error details:", {
        name: error.name,
        message: error.message,
        stack: error.stack,
      });
    }

    process.exit(1);
  } finally {
    clearTimeout(testTimeout);

    // Clean up the processor to stop heartbeat and daemon
    console.log("🧹 Cleaning up TTS processor...");
    try {
      await processor?.stop();
      console.log("✅ TTS processor cleaned up");
    } catch (cleanupError) {
      console.warn("⚠️ Error during cleanup:", cleanupError);
    }

    // Force exit after cleanup to ensure no hanging processes
    console.log("🚪 Exiting test...");
    process.exit(0);
  }
}

// Run the test if this file is executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  // Add signal handlers for graceful shutdown
  let cleanupInProgress = false;

  const cleanup = async () => {
    if (cleanupInProgress) return;
    cleanupInProgress = true;

    console.log("\n🛑 Received interrupt signal, cleaning up...");
    try {
      // The processor will be cleaned up in the finally block
      process.exit(0);
    } catch (error) {
      console.error("❌ Error during cleanup:", error);
      process.exit(1);
    }
  };

  process.on("SIGINT", cleanup);
  process.on("SIGTERM", cleanup);

  runTTSTest();
}
