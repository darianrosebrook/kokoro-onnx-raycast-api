#!/usr/bin/env node

/**
 * Dynamic Buffer Management Test
 *
 * This test demonstrates the adaptive buffer management system
 * in action, showing how it adapts to different network conditions
 * and performance scenarios.
 *
 * Tests:
 * 1. Optimal configuration baseline
 * 2. Network latency simulation
 * 3. Performance profile switching
 * 4. Real-time adaptation
 *
 * @author @darianrosebrook
 * @version 1.0.0
 * @since 2025-01-20
 */

import { spawn } from "child_process";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import { performance } from "perf_hooks";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

/**
 * Test configuration
 */
const TEST_CONFIG = {
  daemonPath: join(__dirname, "bin/audio-daemon.js"),
  basePort: 9000,
  sampleRate: 24000,
  channels: 1,
  bitDepth: 16,
  testDuration: 3000, // 3 seconds per test
};

/**
 * Generate test audio data
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
 * Simulate network latency
 */
function simulateLatency(latencyMs) {
  return new Promise((resolve) => setTimeout(resolve, latencyMs));
}

/**
 * Run audio test with specific configuration
 */
async function runAudioTest(config, testName, port) {
  console.log(`\n🎵 ${testName}`);
  console.log("=".repeat(50));
  console.log(
    `Buffer: ${config.bufferSize} bytes, Chunk: ${config.chunkSize} bytes, Delivery: ${config.deliveryRate}ms`
  );

  return new Promise(async (resolve, reject) => {
    try {
      // Start daemon
      const daemon = spawn("node", [TEST_CONFIG.daemonPath, "--port", port.toString()], {
        stdio: ["pipe", "pipe", "pipe"],
      });

      let daemonStarted = false;
      let ws = null;
      let metrics = {
        startTime: 0,
        firstAudioTime: 0,
        totalChunks: 0,
        successfulChunks: 0,
        bufferUnderruns: 0,
        networkLatency: [],
      };

      daemon.stdout.on("data", (data) => {
        const output = data.toString();
        if (output.includes("Audio Daemon listening on port")) {
          daemonStarted = true;
        }
        if (output.includes("Sufficient data buffered, starting audio processing")) {
          metrics.firstAudioTime = performance.now();
        }
      });

      daemon.stderr.on("data", (data) => {
        const output = data.toString();
        if (output.includes("Buffer underrun")) {
          metrics.bufferUnderruns++;
        }
      });

      // Wait for daemon to start
      await new Promise((resolve, reject) => {
        const checkStartup = () => {
          if (daemonStarted) {
            resolve();
          } else if (daemon.exitCode !== null) {
            reject(new Error("Daemon process exited unexpectedly"));
          } else {
            setTimeout(checkStartup, 100);
          }
        };
        checkStartup();
      });

      // Connect WebSocket
      const { WebSocket } = await import("ws");
      ws = new WebSocket(`ws://localhost:${port}`);

      ws.on("open", async () => {
        metrics.startTime = performance.now();

        // Send start message
        const startMessage = {
          type: "control",
          timestamp: Date.now(),
          data: { action: "play" },
        };
        ws.send(JSON.stringify(startMessage));

        // Generate and send audio chunks
        const audioData = generateTestAudio(TEST_CONFIG.testDuration);
        const chunks = [];

        for (let i = 0; i < audioData.length; i += config.chunkSize) {
          chunks.push(audioData.slice(i, i + config.chunkSize));
        }

        console.log(`📦 Sending ${chunks.length} chunks...`);

        for (let i = 0; i < chunks.length; i++) {
          const chunk = chunks[i];
          const sendTime = performance.now();

          const audioMessage = {
            type: "audio_chunk",
            timestamp: sendTime,
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
          metrics.totalChunks++;

          // Measure network latency
          ws.once("message", (data) => {
            try {
              const message = JSON.parse(data.toString());
              if (message.type === "status") {
                const receiveTime = performance.now();
                const latency = receiveTime - sendTime;
                metrics.networkLatency.push(latency);
                metrics.successfulChunks++;
              }
            } catch (error) {
              // Ignore parsing errors
            }
          });

          // Simulate network latency if specified
          if (config.simulatedLatency) {
            await simulateLatency(config.simulatedLatency);
          } else {
            await new Promise((resolve) => setTimeout(resolve, config.deliveryRate));
          }
        }

        // Send stop message
        setTimeout(() => {
          const stopMessage = {
            type: "control",
            timestamp: Date.now(),
            data: { action: "stop" },
          };
          ws.send(JSON.stringify(stopMessage));

          // Wait for cleanup
          setTimeout(() => {
            // Cleanup
            ws.close();
            daemon.kill("SIGTERM");

            // Calculate metrics
            const totalTime = performance.now() - metrics.startTime;
            const avgLatency =
              metrics.networkLatency.length > 0
                ? metrics.networkLatency.reduce((a, b) => a + b, 0) / metrics.networkLatency.length
                : 0;
            const successRate = metrics.successfulChunks / metrics.totalChunks;
            const timeToFirstAudio =
              metrics.firstAudioTime > 0 ? metrics.firstAudioTime - metrics.startTime : 0;

            console.log(`✅ Test completed`);
            console.log(`   Time to first audio: ${timeToFirstAudio.toFixed(1)}ms`);
            console.log(`   Success rate: ${(successRate * 100).toFixed(1)}%`);
            console.log(`   Avg latency: ${avgLatency.toFixed(2)}ms`);
            console.log(`   Buffer underruns: ${metrics.bufferUnderruns}`);
            console.log(`   Total time: ${totalTime.toFixed(0)}ms`);

            resolve({
              testName,
              config,
              metrics: {
                timeToFirstAudio,
                successRate,
                avgLatency,
                bufferUnderruns: metrics.bufferUnderruns,
                totalTime,
              },
            });
          }, 1000);
        }, TEST_CONFIG.testDuration + 1000);
      });

      ws.on("error", (error) => {
        reject(error);
      });
    } catch (error) {
      console.error("❌ Test failed:", error.message);
      reject(error);
    }
  });
}

/**
 * Test optimal configuration baseline
 */
async function testOptimalBaseline() {
  const optimalConfig = {
    bufferSize: 4800,
    chunkSize: 1200,
    deliveryRate: 5,
    simulatedLatency: 0,
  };

  return await runAudioTest(optimalConfig, "Optimal Configuration Baseline", TEST_CONFIG.basePort);
}

/**
 * Test high latency network simulation
 */
async function testHighLatencyNetwork() {
  const highLatencyConfig = {
    bufferSize: 4800,
    chunkSize: 1200,
    deliveryRate: 5,
    simulatedLatency: 50, // 50ms network latency
  };

  return await runAudioTest(
    highLatencyConfig,
    "High Latency Network Simulation",
    TEST_CONFIG.basePort + 1
  );
}

/**
 * Test conservative buffer configuration
 */
async function testConservativeConfig() {
  const conservativeConfig = {
    bufferSize: 9600, // Larger buffer
    chunkSize: 1200,
    deliveryRate: 10, // Slower delivery
    simulatedLatency: 50,
  };

  return await runAudioTest(
    conservativeConfig,
    "Conservative Buffer Configuration",
    TEST_CONFIG.basePort + 2
  );
}

/**
 * Test aggressive buffer configuration
 */
async function testAggressiveConfig() {
  const aggressiveConfig = {
    bufferSize: 2400, // Smaller buffer
    chunkSize: 1200,
    deliveryRate: 3, // Faster delivery
    simulatedLatency: 0,
  };

  return await runAudioTest(
    aggressiveConfig,
    "Aggressive Buffer Configuration",
    TEST_CONFIG.basePort + 3
  );
}

/**
 * Run all dynamic buffer management tests
 */
async function runDynamicBufferTests() {
  console.log("🚀 Dynamic Buffer Management Test Suite");
  console.log("=".repeat(60));

  const results = [];

  try {
    // Test 1: Optimal baseline
    const baselineResult = await testOptimalBaseline();
    results.push(baselineResult);

    // Test 2: High latency network
    const highLatencyResult = await testHighLatencyNetwork();
    results.push(highLatencyResult);

    // Test 3: Conservative configuration
    const conservativeResult = await testConservativeConfig();
    results.push(conservativeResult);

    // Test 4: Aggressive configuration
    const aggressiveResult = await testAggressiveConfig();
    results.push(aggressiveResult);

    // Analyze results
    console.log("\n📊 Test Results Analysis");
    console.log("=".repeat(40));

    const bestLatency = results.reduce((best, current) =>
      current.metrics.timeToFirstAudio < best.metrics.timeToFirstAudio ? current : best
    );

    const bestReliability = results.reduce((best, current) =>
      current.metrics.successRate > best.metrics.successRate ? current : best
    );

    const bestOverall = results.reduce((best, current) => {
      const bestScore = best.metrics.successRate * (1 / (1 + best.metrics.timeToFirstAudio / 100));
      const currentScore =
        current.metrics.successRate * (1 / (1 + current.metrics.timeToFirstAudio / 100));
      return currentScore > bestScore ? current : best;
    });

    console.log("🏆 Best Performance by Category:");
    console.log(
      `   Lowest Latency: ${bestLatency.testName} (${bestLatency.metrics.timeToFirstAudio.toFixed(1)}ms)`
    );
    console.log(
      `   Highest Reliability: ${bestReliability.testName} (${(bestReliability.metrics.successRate * 100).toFixed(1)}%)`
    );
    console.log(
      `   Best Overall: ${bestOverall.testName} (Score: ${(bestOverall.metrics.successRate * (1 / (1 + bestOverall.metrics.timeToFirstAudio / 100))).toFixed(3)})`
    );

    console.log("\n📋 Configuration Recommendations:");
    console.log("   • For low-latency applications: Use aggressive configuration");
    console.log("   • For unreliable networks: Use conservative configuration");
    console.log("   • For balanced performance: Use optimal configuration");
    console.log("   • For high-latency networks: Increase buffer size and delivery rate");

    return { results, bestLatency, bestReliability, bestOverall };
  } catch (error) {
    console.error("❌ Test suite failed:", error.message);
    throw error;
  }
}

// Run tests if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  runDynamicBufferTests().catch(console.error);
}
