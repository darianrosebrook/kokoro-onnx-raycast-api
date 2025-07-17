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
import { logger } from "./src/utils/core/logger.js";
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
  logger.consoleInfo("🧪 Testing TTS server directly...");

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

    logger.consoleInfo("📡 Server response:", {
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

    logger.consoleInfo("✅ Server test successful - streaming supported");
    return true;
  } catch (error) {
    logger.consoleError("❌ Server test failed:", error);
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
  logger.consoleInfo("🚀 Starting TTS Integration Test");
  logger.consoleInfo("==================================");

  // Add overall test timeout
  const testTimeout = setTimeout(() => {
    logger.consoleError("❌ Test timeout exceeded. Forcing exit.");
    process.exit(1);
  }, TEST_CONFIG.timeoutMs);

  let processor: TTSSpeechProcessor | null = null;

  try {
    // First, test the TTS server directly
    logger.consoleInfo("🔍 Step 1: Testing TTS server connectivity...");
    const serverTestPassed = await testTTSServerDirectly();

    if (!serverTestPassed) {
      logger.consoleError("❌ TTS server test failed. Cannot proceed with integration test.");
      process.exit(1);
    }

    logger.consoleInfo("✅ TTS server test passed. Proceeding with full integration test...");

    // Create TTS processor
    logger.consoleInfo("🔍 Step 2: Creating TTS processor...");
    processor = new TTSSpeechProcessor({
      voice: TEST_CONFIG.voice,
      speed: TEST_CONFIG.speed,
      serverUrl: TEST_CONFIG.serverUrl,
      daemonPort: TEST_CONFIG.daemonPort,
      useStreaming: TEST_CONFIG.useStreaming,
      developmentMode: TEST_CONFIG.developmentMode,
      onStatusUpdate: (status) => {
        logger.consoleInfo("📊 Status:", status.message);
      },
    });

    logger.consoleInfo("✅ TTS Processor created");

    // Test text
    const testText =
      "Hello, this is a test of the audio daemon integration. Can you hear this audio playing through the daemon?";

    logger.consoleInfo(`📝 Processing text: "${testText}"`);
    logger.consoleInfo(`🎵 Voice: ${TEST_CONFIG.voice}, Speed: ${TEST_CONFIG.speed}`);

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

    logger.consoleInfo("✅ Text processing completed");
    logger.consoleInfo("🔊 Audio should be playing through the daemon now!");

    // Wait a bit for audio to finish playing
    logger.consoleInfo("⏳ Waiting for audio playback to complete...");
    await new Promise((resolve) => setTimeout(resolve, 2000));

    logger.consoleInfo("✅ Test completed successfully!");
  } catch (error) {
    logger.consoleError("❌ Test failed:", error);

    // Provide more detailed error information
    if (error instanceof Error) {
      logger.consoleError("Error details:", {
        name: error.name,
        message: error.message,
        stack: error.stack,
      });
    }

    process.exit(1);
  } finally {
    clearTimeout(testTimeout);

    // Clean up the processor to stop heartbeat and daemon
    logger.consoleInfo("🧹 Cleaning up TTS processor...");
    try {
      await processor?.stop();
      logger.consoleInfo("✅ TTS processor cleaned up");
    } catch (cleanupError) {
      logger.consoleWarn("⚠️ Error during cleanup:", cleanupError);
    }

    // Force exit after cleanup to ensure no hanging processes
    logger.consoleInfo("🚪 Exiting test...");
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

    logger.consoleInfo("\n🛑 Received interrupt signal, cleaning up...");
    try {
      // The processor will be cleaned up in the finally block
      process.exit(0);
    } catch (error) {
      logger.consoleError("❌ Error during cleanup:", error);
      process.exit(1);
    }
  };

  process.on("SIGINT", cleanup);
  process.on("SIGTERM", cleanup);

  runTTSTest();
}
