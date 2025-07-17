#!/usr/bin/env node

/**
 * Dynamic Buffer Management Benchmark
 *
 * This test benchmarks the timing between server write and daemon read
 * to auto-configure optimal buffer settings for smooth playback.
 *
 * Tests:
 * 1. Network latency measurement
 * 2. Chunk processing timing
 * 3. Buffer underrun analysis
 * 4. Auto-configuration of optimal settings
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
 * Benchmark configuration
 */
const BENCHMARK_CONFIG = {
  daemonPath: join(__dirname, "bin/audio-daemon.js"),
  basePort: 8083, // Base port, will increment for each test
  sampleRate: 24000,
  channels: 1,
  bitDepth: 16,
  testDuration: 5000, // 5 seconds
  chunkSizes: [1200, 2400, 4800, 9600], // Different chunk sizes to test
  deliveryRates: [5, 10, 20, 50], // Different delivery rates (ms)
  daemonStartTimeout: 5000, // 5 seconds to start daemon
};

/**
 * Generate test audio data
 */
function generateTestAudio(durationMs = 1000) {
  const samples = Math.floor((durationMs / 1000) * BENCHMARK_CONFIG.sampleRate);
  const buffer = Buffer.alloc(
    samples * BENCHMARK_CONFIG.channels * (BENCHMARK_CONFIG.bitDepth / 8)
  );

  // Generate a simple sine wave (440Hz)
  const frequency = 440;
  const amplitude = 0.3;

  for (let i = 0; i < samples; i++) {
    const sample =
      Math.sin((2 * Math.PI * frequency * i) / BENCHMARK_CONFIG.sampleRate) * amplitude;
    const intSample = Math.round(sample * 32767);
    buffer.writeInt16LE(intSample, i * BENCHMARK_CONFIG.channels * (BENCHMARK_CONFIG.bitDepth / 8));
  }

  return buffer;
}

/**
 * Benchmark result structure
 */
class BenchmarkResult {
  constructor() {
    this.chunkSize = 0;
    this.deliveryRate = 0;
    this.networkLatency = [];
    this.processingTimes = [];
    this.bufferUnderruns = 0;
    this.totalChunks = 0;
    this.successfulChunks = 0;
    this.audioDuration = 0;
    this.startTime = 0;
    this.endTime = 0;
  }

  get averageLatency() {
    return this.networkLatency.reduce((a, b) => a + b, 0) / this.networkLatency.length;
  }

  get averageProcessingTime() {
    return this.processingTimes.reduce((a, b) => a + b, 0) / this.processingTimes.length;
  }

  get successRate() {
    return this.successfulChunks / this.totalChunks;
  }

  get efficiency() {
    return this.audioDuration / (this.endTime - this.startTime);
  }
}

/**
 * Run a single benchmark test
 */
async function runBenchmark(chunkSize, deliveryRate, testIndex) {
  const port = BENCHMARK_CONFIG.basePort + testIndex;
  console.log(`\n🔬 Benchmarking: ${chunkSize} bytes, ${deliveryRate}ms delivery (port ${port})`);
  console.log("=".repeat(50));

  return new Promise(async (resolve, reject) => {
    try {
      const result = new BenchmarkResult();
      result.chunkSize = chunkSize;
      result.deliveryRate = deliveryRate;
      result.startTime = performance.now();

      // Start daemon
      const daemon = spawn("node", [BENCHMARK_CONFIG.daemonPath, "--port", port.toString()], {
        stdio: ["pipe", "pipe", "pipe"],
      });

      let daemonStarted = false;
      let ws = null;
      let audioStartTime = 0;
      let audioEndTime = 0;
      let startupTimeout = null;

      daemon.stdout.on("data", (data) => {
        const output = data.toString();
        if (output.includes("Audio Daemon listening on port")) {
          daemonStarted = true;
          if (startupTimeout) {
            clearTimeout(startupTimeout);
            startupTimeout = null;
          }
        }
        if (output.includes("Sufficient data buffered, starting audio processing")) {
          audioStartTime = performance.now();
        }
      });

      daemon.stderr.on("data", (data) => {
        const output = data.toString();
        if (output.includes("Buffer underrun")) {
          result.bufferUnderruns++;
        }
      });

      // Set startup timeout
      startupTimeout = setTimeout(() => {
        if (!daemonStarted) {
          daemon.kill("SIGTERM");
          reject(
            new Error(`Daemon failed to start within ${BENCHMARK_CONFIG.daemonStartTimeout}ms`)
          );
        }
      }, BENCHMARK_CONFIG.daemonStartTimeout);

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
        // Send start message
        const startMessage = {
          type: "control",
          timestamp: Date.now(),
          data: { action: "play" },
        };
        ws.send(JSON.stringify(startMessage));

        // Generate and send audio chunks
        const audioData = generateTestAudio(BENCHMARK_CONFIG.testDuration);
        const chunks = [];

        for (let i = 0; i < audioData.length; i += chunkSize) {
          chunks.push(audioData.slice(i, i + chunkSize));
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
                sampleRate: BENCHMARK_CONFIG.sampleRate,
                channels: BENCHMARK_CONFIG.channels,
                bitDepth: BENCHMARK_CONFIG.bitDepth,
              },
              sequence: i,
            },
          };

          ws.send(JSON.stringify(audioMessage));
          result.totalChunks++;

          // Measure network latency
          ws.once("message", (data) => {
            try {
              const message = JSON.parse(data.toString());
              if (message.type === "status") {
                const receiveTime = performance.now();
                const latency = receiveTime - sendTime;
                result.networkLatency.push(latency);
                result.successfulChunks++;
              }
            } catch (error) {
              // Ignore parsing errors
            }
          });

          await new Promise((resolve) => setTimeout(resolve, deliveryRate));
        }

        // Send stop message
        setTimeout(() => {
          const stopMessage = {
            type: "control",
            timestamp: Date.now(),
            data: { action: "stop" },
          };
          ws.send(JSON.stringify(stopMessage));

          // Wait for audio to finish
          setTimeout(() => {
            audioEndTime = performance.now();
            result.endTime = performance.now();
            result.audioDuration = audioEndTime - audioStartTime;

            // Cleanup
            ws.close();
            daemon.kill("SIGTERM");

            console.log(`✅ Benchmark completed`);
            console.log(`   Network latency: ${result.averageLatency.toFixed(2)}ms avg`);
            console.log(`   Success rate: ${(result.successRate * 100).toFixed(1)}%`);
            console.log(`   Buffer underruns: ${result.bufferUnderruns}`);
            console.log(`   Audio duration: ${result.audioDuration.toFixed(0)}ms`);

            resolve(result);
          }, 1000);
        }, BENCHMARK_CONFIG.testDuration + 1000);
      });

      ws.on("error", (error) => {
        reject(error);
      });
    } catch (error) {
      console.error("❌ Benchmark failed:", error.message);
      reject(error);
    }
  });
}

/**
 * Auto-configure optimal buffer settings
 */
function autoConfigureBuffer(results) {
  console.log("\n Auto-Configuring Optimal Buffer Settings");
  console.log("=".repeat(50));

  // Filter successful results (success rate > 80%)
  const successfulResults = results.filter((r) => r.successRate > 0.8);

  if (successfulResults.length === 0) {
    console.log("❌ No successful configurations found");
    return null;
  }

  // Find the configuration with the best balance of:
  // 1. High success rate
  // 2. Low latency
  // 3. Few underruns
  // 4. Good efficiency
  const bestResult = successfulResults.reduce((best, current) => {
    const bestScore =
      best.successRate * (1 / (1 + best.averageLatency)) * (1 / (1 + best.bufferUnderruns));
    const currentScore =
      current.successRate *
      (1 / (1 + current.averageLatency)) *
      (1 / (1 + current.bufferUnderruns));
    return currentScore > bestScore ? current : best;
  });

  console.log("🏆 Optimal Configuration Found:");
  console.log(`   Chunk Size: ${bestResult.chunkSize} bytes`);
  console.log(`   Delivery Rate: ${bestResult.deliveryRate}ms`);
  console.log(`   Success Rate: ${(bestResult.successRate * 100).toFixed(1)}%`);
  console.log(`   Avg Latency: ${bestResult.averageLatency.toFixed(2)}ms`);
  console.log(`   Buffer Underruns: ${bestResult.bufferUnderruns}`);
  console.log(`   Efficiency: ${(bestResult.efficiency * 100).toFixed(1)}%`);

  // Calculate recommended buffer settings
  const recommendedBufferSize = Math.max(
    bestResult.chunkSize * 4, // At least 4 chunks
    ((bestResult.averageLatency * bestResult.chunkSize) / bestResult.deliveryRate) * 2 // 2x latency buffer
  );

  const recommendedChunkSize = bestResult.chunkSize;
  const recommendedDeliveryRate = bestResult.deliveryRate;

  console.log("\n📋 Recommended Settings:");
  console.log(`   Buffer Size: ${recommendedBufferSize} bytes`);
  console.log(`   Chunk Size: ${recommendedChunkSize} bytes`);
  console.log(`   Delivery Rate: ${recommendedDeliveryRate}ms`);
  console.log(`   Min Buffer Chunks: ${Math.ceil(recommendedBufferSize / recommendedChunkSize)}`);

  return {
    bufferSize: recommendedBufferSize,
    chunkSize: recommendedChunkSize,
    deliveryRate: recommendedDeliveryRate,
    minBufferChunks: Math.ceil(recommendedBufferSize / recommendedChunkSize),
    benchmark: bestResult,
  };
}

/**
 * Run all benchmarks
 */
async function runAllBenchmarks() {
  console.log("🚀 Starting Dynamic Buffer Management Benchmark");
  console.log("=".repeat(60));

  const results = [];

  // Test different configurations
  for (const chunkSize of BENCHMARK_CONFIG.chunkSizes) {
    for (const deliveryRate of BENCHMARK_CONFIG.deliveryRates) {
      try {
        const result = await runBenchmark(chunkSize, deliveryRate, results.length);
        results.push(result);

        // Wait between tests
        await new Promise((resolve) => setTimeout(resolve, 2000));
      } catch (error) {
        console.error(
          `❌ Benchmark failed for ${chunkSize} bytes, ${deliveryRate}ms:`,
          error.message
        );
      }
    }
  }

  // Auto-configure optimal settings
  const optimalConfig = autoConfigureBuffer(results);

  // Summary
  console.log("\n📊 Benchmark Summary");
  console.log("=".repeat(30));
  console.log(`Total tests: ${results.length}`);
  console.log(`Successful tests: ${results.filter((r) => r.successRate > 0.8).length}`);
  console.log(
    `Best success rate: ${Math.max(...results.map((r) => r.successRate * 100)).toFixed(1)}%`
  );
  console.log(`Lowest latency: ${Math.min(...results.map((r) => r.averageLatency)).toFixed(2)}ms`);

  return { results, optimalConfig };
}

// Run benchmarks if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  runAllBenchmarks().catch(console.error);
}
