#!/usr/bin/env node

/**
 * Standalone TTS Streaming Benchmark Test
 *
 * This script runs comprehensive streaming benchmarks to analyze performance
 * and diagnose timing issues in the TTS pipeline.
 */

import { performance } from "perf_hooks";
import http from "http";

// Test configuration
const CONFIG = {
  serverUrl: "http://localhost:8000",
  voice: "bm_fable",
  speed: 1.2,
  testTexts: [
    "Hello world",
    "The process that leads to a final decision",
    "This is a comprehensive streaming test with a longer piece of text that will help us understand how streaming performance scales with content length. We want to measure the time from request initiation to first audio chunk, and analyze the stream-to-play delay to identify potential bottlenecks in the audio processing pipeline.",
  ],
};

/**
 * Make HTTP request using Node.js http module
 */
function makeRequest(url, options, postData) {
  return new Promise((resolve, reject) => {
    const req = http.request(url, options, (res) => {
      resolve(res);
    });

    req.on("error", reject);

    if (postData) {
      req.write(postData);
    }

    req.end();
  });
}

/**
 * Measure streaming performance with detailed timing
 */
async function measureStreamingPerformance(text, config) {
  console.log(`\n🧪 Testing: "${text.substring(0, 50)}${text.length > 50 ? "..." : ""}"`);
  console.log(`   Voice: ${config.voice}, Speed: ${config.speed}`);
  console.log(`   Server: ${config.serverUrl}`);
  console.log(`   ${"─".repeat(60)}`);

  const timingMetrics = {
    startTime: performance.now(),
    sendTime: 0,
    timeToFirstByte: 0,
    timeToFirstChunk: 0,
    streamEndTime: 0,
    totalTime: 0,
    chunkCount: 0,
    totalBytes: 0,
  };

  const request = {
    text: text,
    voice: config.voice,
    speed: config.speed,
    lang: "en-us",
    stream: true,
    format: "wav",
  };

  try {
    // Measure send time
    timingMetrics.sendTime = performance.now() - timingMetrics.startTime;

    // Start streaming request
    const postData = JSON.stringify(request);
    const options = {
      hostname: "localhost",
      port: 8000,
      path: "/v1/audio/speech",
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "audio/wav",
        "Content-Length": Buffer.byteLength(postData),
      },
    };

    const response = await makeRequest(`${config.serverUrl}/v1/audio/speech`, options, postData);

    // Measure time to first byte
    timingMetrics.timeToFirstByte = performance.now() - timingMetrics.startTime;

    if (response.statusCode !== 200) {
      throw new Error(`TTS request failed: ${response.statusCode} ${response.statusMessage}`);
    }

    // Read stream and measure performance
    const chunks = [];
    let firstChunkReceived = false;

    response.on("data", (chunk) => {
      if (!firstChunkReceived) {
        timingMetrics.timeToFirstChunk = performance.now() - timingMetrics.startTime;
        firstChunkReceived = true;
        console.log(`   📊 First chunk received: ${timingMetrics.timeToFirstChunk.toFixed(2)}ms`);
      }

      chunks.push(chunk);
      timingMetrics.chunkCount++;
      timingMetrics.totalBytes += chunk.length;
    });

    return new Promise((resolve) => {
      response.on("end", () => {
        timingMetrics.streamEndTime = performance.now() - timingMetrics.startTime;
        console.log(`   📊 Stream ended: ${timingMetrics.streamEndTime.toFixed(2)}ms`);

        timingMetrics.totalTime = performance.now() - timingMetrics.startTime;

        // Print detailed timing analysis
        console.log(`\n   📈 DETAILED TIMING BREAKDOWN:`);
        console.log(`      Send Time:              ${timingMetrics.sendTime.toFixed(2)}ms`);
        console.log(
          `      Processing Time:        ${(timingMetrics.timeToFirstByte - timingMetrics.sendTime).toFixed(2)}ms`
        );
        console.log(`      Time to First Chunk:    ${timingMetrics.timeToFirstChunk.toFixed(2)}ms`);
        console.log(
          `      Stream Duration:        ${(timingMetrics.streamEndTime - timingMetrics.timeToFirstChunk).toFixed(2)}ms`
        );
        console.log(`      Total Time:             ${timingMetrics.totalTime.toFixed(2)}ms`);

        console.log(`\n   📊 STREAM ANALYSIS:`);
        console.log(`      Chunks Received:        ${timingMetrics.chunkCount}`);
        console.log(
          `      Total Bytes:            ${(timingMetrics.totalBytes / 1024).toFixed(2)} KB`
        );
        console.log(
          `      Avg Chunk Size:         ${(timingMetrics.totalBytes / timingMetrics.chunkCount / 1024).toFixed(2)} KB`
        );

        console.log(`\n   🎯 PERFORMANCE INSIGHTS:`);

        if (timingMetrics.timeToFirstChunk < 200) {
          console.log(
            `      ✅ Excellent streaming latency - First chunk in ${timingMetrics.timeToFirstChunk.toFixed(2)}ms`
          );
        } else if (timingMetrics.timeToFirstChunk < 500) {
          console.log(
            `      ✅ Good streaming latency - First chunk in ${timingMetrics.timeToFirstChunk.toFixed(2)}ms`
          );
        } else {
          console.log(
            `      ⚠️  High streaming latency - First chunk in ${timingMetrics.timeToFirstChunk.toFixed(2)}ms`
          );
        }

        if (timingMetrics.chunkCount > 1) {
          console.log(
            `      ✅ Multi-chunk streaming - ${timingMetrics.chunkCount} chunks received`
          );
        } else {
          console.log(`      ⚠️  Single chunk response - No true streaming benefit`);
        }

        const streamingWindow = timingMetrics.streamEndTime - timingMetrics.timeToFirstChunk;
        if (streamingWindow > 50) {
          console.log(
            `      ✅ Good streaming window - ${streamingWindow.toFixed(2)}ms of streaming data`
          );
        } else {
          console.log(
            `      ⚠️  Short streaming window - ${streamingWindow.toFixed(2)}ms streaming duration`
          );
        }

        resolve(timingMetrics);
      });

      response.on("error", (error) => {
        console.error(`   ❌ Error: ${error.message}`);
        resolve(null);
      });
    });
  } catch (error) {
    console.error(`   ❌ Error: ${error.message}`);
    return null;
  }
}

/**
 * Run comprehensive streaming benchmark
 */
async function runStreamingBenchmark() {
  console.log("🚀 TTS STREAMING PERFORMANCE BENCHMARK");
  console.log("=".repeat(80));

  const results = [];

  for (const text of CONFIG.testTexts) {
    const result = await measureStreamingPerformance(text, CONFIG);
    if (result) {
      results.push({ text, ...result });
    }

    // Small delay between tests
    await new Promise((resolve) => setTimeout(resolve, 500));
  }

  // Generate summary report
  if (results.length > 0) {
    console.log("\n📊 SUMMARY REPORT");
    console.log("=".repeat(80));

    const avgFirstChunk = results.reduce((sum, r) => sum + r.timeToFirstChunk, 0) / results.length;
    const avgStreamDuration =
      results.reduce((sum, r) => sum + (r.streamEndTime - r.timeToFirstChunk), 0) / results.length;
    const avgChunkCount = results.reduce((sum, r) => sum + r.chunkCount, 0) / results.length;
    const totalBytes = results.reduce((sum, r) => sum + r.totalBytes, 0);

    console.log(`\n📈 PERFORMANCE METRICS:`);
    console.log(`   Average Time to First Chunk: ${avgFirstChunk.toFixed(2)}ms`);
    console.log(`   Average Stream Duration:     ${avgStreamDuration.toFixed(2)}ms`);
    console.log(`   Average Chunks per Request:  ${avgChunkCount.toFixed(1)}`);
    console.log(`   Total Data Transferred:      ${(totalBytes / 1024).toFixed(2)} KB`);

    console.log(`\n🎯 STREAMING ANALYSIS:`);
    if (avgFirstChunk < 200) {
      console.log(
        `   ✅ Excellent streaming performance - Avg first chunk: ${avgFirstChunk.toFixed(2)}ms`
      );
    } else if (avgFirstChunk < 500) {
      console.log(
        `   ✅ Good streaming performance - Avg first chunk: ${avgFirstChunk.toFixed(2)}ms`
      );
    } else {
      console.log(
        `   ⚠️  Streaming performance needs improvement - Avg first chunk: ${avgFirstChunk.toFixed(2)}ms`
      );
    }

    if (avgChunkCount > 2) {
      console.log(
        `   ✅ True streaming achieved - Avg ${avgChunkCount.toFixed(1)} chunks per request`
      );
    } else {
      console.log(`   ⚠️  Limited streaming - Avg ${avgChunkCount.toFixed(1)} chunks per request`);
    }
  }

  console.log("\n🎉 Benchmark completed!");
  console.log("=".repeat(80));
}

// Run the benchmark
runStreamingBenchmark().catch(console.error);
