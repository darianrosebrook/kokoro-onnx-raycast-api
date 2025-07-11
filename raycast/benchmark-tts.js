#!/usr/bin/env node

/**
 * Standalone TTS Benchmark Script
 *
 * This script provides a command-line interface for benchmarking TTS performance
 * without needing to run the full Raycast extension.
 *
 * Usage:
 *   node benchmark-tts.js [options]
 *
 * Options:
 *   --server <url>     TTS server URL (default: http://localhost:8000)
 *   --text <text>      Text to synthesize (default: test phrases)
 *   --voice <voice>    Voice to use (default: af_heart)
 *   --speed <speed>    Speech speed (default: 1.0)
 *   --iterations <n>   Number of iterations (default: 1)
 *   --suite            Run full benchmark suite
 *
 * Examples:
 *   node benchmark-tts.js --text "Hello world"
 *   node benchmark-tts.js --suite
 *   node benchmark-tts.js --server http://remote:8000 --text "Test" --iterations 5
 *
 * @author @darianrosebrook
 */

import https from "https";
import http from "http";
import { performance } from "perf_hooks";

// Configuration
const DEFAULT_SERVER = "http://localhost:8000";
const DEFAULT_TEXT = "Hello world, this is a test of the TTS system performance.";
const DEFAULT_VOICE = "af_heart";
const DEFAULT_SPEED = 1.0;

// Available voices will be fetched dynamically from the server
let AVAILABLE_VOICES = [];

/**
 * Fetch available voices from the server
 */
async function fetchAvailableVoices(serverUrl) {
  try {
    const response = await makeRequest(`${serverUrl}/voices`, { method: "GET" });

    if (response.statusCode === 200) {
      const voicesData = JSON.parse(response.body.toString());
      AVAILABLE_VOICES = voicesData.voices || [];
      console.log(`✅ Fetched ${AVAILABLE_VOICES.length} available voices from server`);
      return AVAILABLE_VOICES;
    } else {
      throw new Error(`Failed to fetch voices: ${response.statusCode}`);
    }
  } catch (error) {
    console.warn(`⚠️ Could not fetch voices from server: ${error.message}`);
    console.warn(`⚠️ Using fallback voice list`);

    // Fallback to a minimal set of common voices
    AVAILABLE_VOICES = ["af_heart", "af_sky", "bm_fable", "bm_daniel", "am_adam"];
    return AVAILABLE_VOICES;
  }
}

/**
 * Get a random voice from available voices by category
 */
function getVoiceByCategory(category) {
  const categoryVoices = AVAILABLE_VOICES.filter((voice) => voice.startsWith(category + "_"));
  if (categoryVoices.length === 0) {
    // Fallback to any available voice
    return AVAILABLE_VOICES[0] || DEFAULT_VOICE;
  }
  return categoryVoices[Math.floor(Math.random() * categoryVoices.length)];
}

/**
 * Get a safe selection of voices for testing
 */
function getTestVoices() {
  const testVoices = [];

  // Try to get one voice from each major category
  const categories = ["af", "am", "bm", "bf"];

  for (const category of categories) {
    const voice = getVoiceByCategory(category);
    if (voice && !testVoices.includes(voice)) {
      testVoices.push(voice);
    }
  }

  // Ensure we have at least 2 voices for testing
  while (testVoices.length < 2 && testVoices.length < AVAILABLE_VOICES.length) {
    const randomVoice = AVAILABLE_VOICES[Math.floor(Math.random() * AVAILABLE_VOICES.length)];
    if (!testVoices.includes(randomVoice)) {
      testVoices.push(randomVoice);
    }
  }

  return testVoices.slice(0, 4); // Limit to 4 voices for reasonable test time
}

// Test phrases of different lengths
const TEST_PHRASES = [
  "Hi there!",
  "Hello world, this is a test.",
  "This is a medium length sentence for testing TTS performance and caching capabilities.",
  "This is a longer piece of text that will be used to test the performance of the TTS system with larger payloads and more complex processing requirements.",
  "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.",
];

/**
 * Parse command line arguments
 */
function parseArgs() {
  const args = process.argv.slice(2);
  const options = {
    server: DEFAULT_SERVER,
    text: DEFAULT_TEXT,
    voice: DEFAULT_VOICE,
    speed: DEFAULT_SPEED,
    iterations: 1,
    suite: false,
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    const nextArg = args[i + 1];

    switch (arg) {
      case "--server":
        options.server = nextArg;
        i++;
        break;
      case "--text":
        options.text = nextArg;
        i++;
        break;
      case "--voice":
        options.voice = nextArg;
        i++;
        break;
      case "--speed":
        options.speed = parseFloat(nextArg) || DEFAULT_SPEED;
        i++;
        break;
      case "--iterations":
        options.iterations = parseInt(nextArg) || 1;
        i++;
        break;
      case "--suite":
        options.suite = true;
        break;
      case "--help":
      case "-h":
        printHelp();
        process.exit(0);
        break;
      default:
        console.error(`Unknown option: ${arg}`);
        printHelp();
        process.exit(1);
    }
  }

  return options;
}

/**
 * Print help information
 */
function printHelp() {
  console.log(`
TTS Benchmark Script

Usage: node benchmark-tts.js [options]

Options:
  --server <url>     TTS server URL (default: ${DEFAULT_SERVER})
  --text <text>      Text to synthesize (default: test phrases)
  --voice <voice>    Voice to use (default: ${DEFAULT_VOICE})
  --speed <speed>    Speech speed (default: ${DEFAULT_SPEED})
  --iterations <n>   Number of iterations (default: 1)
  --suite            Run full benchmark suite
  --help, -h         Show this help message

Examples:
  node benchmark-tts.js --text "Hello world"
  node benchmark-tts.js --suite
  node benchmark-tts.js --server http://remote:8000 --text "Test" --iterations 5

Available voices: Fetched dynamically from server (/voices endpoint)
  `);
}

/**
 * Make HTTP/HTTPS request
 */
function makeRequest(url, options, data) {
  return new Promise((resolve, reject) => {
    const isHttps = url.startsWith("https:");
    const client = isHttps ? https : http;

    // Add timeout to options
    const requestOptions = {
      ...options,
      timeout: 60000, // 60 second timeout
    };

    const req = client.request(url, requestOptions, (res) => {
      const chunks = [];

      res.on("data", (chunk) => {
        chunks.push(chunk);
      });

      res.on("end", () => {
        const body = Buffer.concat(chunks);
        resolve({
          statusCode: res.statusCode,
          headers: res.headers,
          body: body,
        });
      });

      res.on("error", (error) => {
        reject(new Error(`Response error: ${error.message}`));
      });
    });

    req.on("error", (error) => {
      reject(new Error(`Request error: ${error.message}`));
    });

    req.on("timeout", () => {
      req.destroy();
      reject(new Error("Request timeout after 30 seconds"));
    });

    // Set overall timeout as backup
    const timeoutId = setTimeout(() => {
      req.destroy();
      reject(new Error("Request timeout (backup timer)"));
    }, 35000); // 35 seconds

    req.on("close", () => {
      clearTimeout(timeoutId);
    });

    if (data) {
      req.write(data);
    }

    req.end();
  });
}

/**
 * Benchmark a single TTS request
 */
async function benchmarkRequest(serverUrl, request, requestId) {
  const timer = {
    start: performance.now(),
    marks: {},

    mark(label) {
      const elapsed = performance.now() - this.start;
      this.marks[label] = elapsed;
      return elapsed;
    },

    getElapsed(label) {
      return label ? this.marks[label] : performance.now() - this.start;
    },
  };

  const metrics = {
    requestId,
    timestamp: Date.now(),
    textLength: request.text.length,
    voice: request.voice,
    speed: request.speed,
    success: false,
    networkLatency: 0,
    timeToFirstByte: 0,
    timeToFirstAudioChunk: 0,
    totalResponseTime: 0,
    audioProcessingTime: 0,
    audioDataSize: 0,
    cacheHit: false,
    errorMessage: null,
  };

  try {
    console.log(
      `\n🧪 Test ${requestId}: "${request.text.substring(0, 50)}${request.text.length > 50 ? "..." : ""}"`
    );
    console.log(`   Voice: ${request.voice}, Speed: ${request.speed}`);

    // Measure network latency
    const latencyStart = performance.now();
    try {
      await makeRequest(`${serverUrl}/health`, { method: "GET" });
      metrics.networkLatency = timer.mark("network-latency");
      console.log(`   📊 Network latency: ${metrics.networkLatency.toFixed(2)}ms`);
    } catch (error) {
      metrics.networkLatency = performance.now() - latencyStart;
      console.log(`   📊 Network latency: ${metrics.networkLatency.toFixed(2)}ms (failed)`);
    }

    // Make TTS request
    const ttsUrl = `${serverUrl}/v1/audio/speech`;
    const requestBody = JSON.stringify(request);

    const response = await makeRequest(
      ttsUrl,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "audio/wav",
        },
      },
      requestBody
    );

    metrics.timeToFirstByte = timer.mark("first-byte");
    console.log(`   📊 Time to first byte: ${metrics.timeToFirstByte.toFixed(2)}ms`);

    if (response.statusCode !== 200) {
      let errorMessage = `TTS request failed: ${response.statusCode}`;
      try {
        const errorBody = response.body.toString();
        if (errorBody) {
          const errorData = JSON.parse(errorBody);
          errorMessage += ` - ${errorData.detail || errorData.message || errorBody}`;
        }
      } catch (parseError) {
        // If we can't parse the error body, use the raw response
        errorMessage += ` - ${response.body.toString().substring(0, 100)}`;
      }
      throw new Error(errorMessage);
    }

    metrics.audioDataSize = response.body.length;
    metrics.timeToFirstAudioChunk = metrics.timeToFirstByte; // Simplified for this script
    metrics.audioProcessingTime = 1; // Minimal processing time
    metrics.totalResponseTime = timer.mark("complete");
    metrics.success = true;

    console.log(`   📊 Audio data size: ${(metrics.audioDataSize / 1024).toFixed(2)}KB`);
    console.log(`   📊 Total response time: ${metrics.totalResponseTime.toFixed(2)}ms`);
    console.log(`   ✅ Success`);
  } catch (error) {
    metrics.success = false;
    metrics.errorMessage = error.message;
    metrics.totalResponseTime = timer.getElapsed();
    console.log(`   ❌ Error: ${error.message}`);
  }

  return metrics;
}

/**
 * Run benchmark suite
 */
async function runBenchmarkSuite(serverUrl) {
  console.log("\n🚀 Running TTS Benchmark Suite");
  console.log("=".repeat(60));

  // Fetch available voices first
  await fetchAvailableVoices(serverUrl);
  const testVoices = getTestVoices();

  console.log(`📋 Using ${testVoices.length} voices for testing: ${testVoices.join(", ")}`);
  console.log(`📊 Total available voices: ${AVAILABLE_VOICES.length}`);

  // Primary voice (first available or fallback)
  const primaryVoice = testVoices[0] || DEFAULT_VOICE;
  const secondaryVoice = testVoices[1] || primaryVoice;

  const testCases = [
    // Short texts
    { text: TEST_PHRASES[0], voice: primaryVoice, speed: 1.0 },
    { text: TEST_PHRASES[1], voice: secondaryVoice, speed: 1.0 },

    // Medium texts
    { text: TEST_PHRASES[2], voice: primaryVoice, speed: 1.0 },
    { text: TEST_PHRASES[2], voice: primaryVoice, speed: 1.2 },

    // Long text
    { text: TEST_PHRASES[3], voice: primaryVoice, speed: 1.0 },

    // Speed variations
    { text: TEST_PHRASES[1], voice: primaryVoice, speed: 0.8 },
    { text: TEST_PHRASES[1], voice: primaryVoice, speed: 1.5 },

    // Voice variations (use available test voices)
    { text: TEST_PHRASES[1], voice: testVoices[2] || primaryVoice, speed: 1.0 },
    { text: TEST_PHRASES[1], voice: testVoices[3] || secondaryVoice, speed: 1.0 },
  ];

  const results = [];

  for (let i = 0; i < testCases.length; i++) {
    const testCase = testCases[i];
    const request = {
      text: testCase.text,
      voice: testCase.voice,
      speed: testCase.speed,
      lang: "en-us",
      stream: true,
      format: "wav",
    };

    const metrics = await benchmarkRequest(serverUrl, request, `suite-${i + 1}`);
    results.push(metrics);

    // Small delay between tests
    await new Promise((resolve) => setTimeout(resolve, 100));
  }

  // Generate statistics
  const successful = results.filter((r) => r.success);
  const failed = results.filter((r) => !r.success);

  if (successful.length === 0) {
    console.log("\n❌ No successful requests");
    return;
  }

  const avg = (numbers) => numbers.reduce((sum, n) => sum + n, 0) / numbers.length;

  const stats = {
    totalRequests: results.length,
    successfulRequests: successful.length,
    failedRequests: failed.length,
    successRate: (successful.length / results.length) * 100,

    averageLatency: avg(successful.map((r) => r.networkLatency)),
    averageTTFB: avg(successful.map((r) => r.timeToFirstByte)),
    averageTotalTime: avg(successful.map((r) => r.totalResponseTime)),

    totalDataTransferred: successful.reduce((sum, r) => sum + r.audioDataSize, 0),
    averageResponseSize: avg(successful.map((r) => r.audioDataSize)),

    minResponseTime: Math.min(...successful.map((r) => r.totalResponseTime)),
    maxResponseTime: Math.max(...successful.map((r) => r.totalResponseTime)),
  };

  // Print report
  console.log("\n" + "=".repeat(60));
  console.log("📊 TTS BENCHMARK REPORT");
  console.log("=".repeat(60));

  console.log(`\n📈 OVERALL STATISTICS:`);
  console.log(`   Total Requests: ${stats.totalRequests}`);
  console.log(`   Successful: ${stats.successfulRequests} (${stats.successRate.toFixed(1)}%)`);
  console.log(`   Failed: ${stats.failedRequests}`);

  console.log(`\n⏱️  TIMING PERFORMANCE:`);
  console.log(`   Average Network Latency: ${stats.averageLatency.toFixed(2)}ms`);
  console.log(`   Average Time to First Byte: ${stats.averageTTFB.toFixed(2)}ms`);
  console.log(`   Average Total Response Time: ${stats.averageTotalTime.toFixed(2)}ms`);
  console.log(`   Min Response Time: ${stats.minResponseTime.toFixed(2)}ms`);
  console.log(`   Max Response Time: ${stats.maxResponseTime.toFixed(2)}ms`);

  console.log(`\n📦 DATA TRANSFER:`);
  console.log(`   Total Data Transferred: ${(stats.totalDataTransferred / 1024).toFixed(2)} KB`);
  console.log(`   Average Response Size: ${(stats.averageResponseSize / 1024).toFixed(2)} KB`);

  if (failed.length > 0) {
    console.log(`\n❌ FAILED REQUESTS:`);
    failed.forEach((f) => {
      console.log(`   ${f.requestId}: ${f.errorMessage}`);
    });
  }

  console.log("\n" + "=".repeat(60));

  return stats;
}

/**
 * Run single benchmark
 */
async function runSingleBenchmark(serverUrl, text, voice, speed, iterations) {
  console.log("\n🎯 Running Single TTS Benchmark");
  console.log("=".repeat(60));

  // Fetch available voices and validate the requested voice
  await fetchAvailableVoices(serverUrl);

  if (!AVAILABLE_VOICES.includes(voice)) {
    console.warn(`⚠️ Requested voice '${voice}' not available.`);
    console.warn(
      `📋 Available voices: ${AVAILABLE_VOICES.slice(0, 5).join(", ")}${AVAILABLE_VOICES.length > 5 ? "..." : ""}`
    );

    // Use a fallback voice from the same category if possible
    const voiceCategory = voice.split("_")[0];
    const fallbackVoice = getVoiceByCategory(voiceCategory) || AVAILABLE_VOICES[0] || DEFAULT_VOICE;
    console.warn(`🔄 Using fallback voice: ${fallbackVoice}`);
    voice = fallbackVoice;
  }

  const request = {
    text: text,
    voice: voice,
    speed: speed,
    lang: "en-us",
    stream: true,
    format: "wav",
  };

  const results = [];

  for (let i = 0; i < iterations; i++) {
    const metrics = await benchmarkRequest(serverUrl, request, `single-${i + 1}`);
    results.push(metrics);

    if (i < iterations - 1) {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }

  // Calculate statistics for multiple iterations
  if (iterations > 1) {
    const successful = results.filter((r) => r.success);
    if (successful.length > 0) {
      const avg = (numbers) => numbers.reduce((sum, n) => sum + n, 0) / numbers.length;

      console.log(`\n📊 SUMMARY (${iterations} iterations):`);
      console.log(`   Success Rate: ${((successful.length / iterations) * 100).toFixed(1)}%`);
      console.log(
        `   Average Response Time: ${avg(successful.map((r) => r.totalResponseTime)).toFixed(2)}ms`
      );
      console.log(`   Average TTFB: ${avg(successful.map((r) => r.timeToFirstByte)).toFixed(2)}ms`);
      console.log(
        `   Average Audio Size: ${(avg(successful.map((r) => r.audioDataSize)) / 1024).toFixed(2)}KB`
      );
    }
  }

  return results;
}

/**
 * Main function
 */
async function main() {
  const options = parseArgs();

  console.log("🎤 TTS Performance Benchmark");
  console.log(`Server: ${options.server}`);
  console.log(`Voice: ${options.voice}`);
  console.log(`Speed: ${options.speed}`);

  try {
    if (options.suite) {
      await runBenchmarkSuite(options.server);
    } else {
      await runSingleBenchmark(
        options.server,
        options.text,
        options.voice,
        options.speed,
        options.iterations
      );
    }
  } catch (error) {
    console.error(`\n❌ Benchmark failed: ${error.message}`);
    process.exit(1);
  }
}

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(console.error);
}
