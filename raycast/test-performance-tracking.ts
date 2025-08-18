/**
 * Test script for the new performance tracking system
 *
 * This script validates that the new performance tracking system
 * provides accurate metrics and proper end-to-end request flow tracking.
 *
 * @author @darianrosebrook
 * @version 1.0.0
 */

import { PerformanceTracker } from "./src/utils/core/performance-tracker.js";

async function testPerformanceTracking() {
  console.log("🧪 Testing Performance Tracking System");
  console.log("=".repeat(50));

  const tracker = PerformanceTracker.getInstance();

  // Test 1: Basic request flow
  console.log("\n📋 Test 1: Basic Request Flow");
  const requestId = "test-request-001";
  const text = "Hello world, this is a test of the performance tracking system.";

  // Start request
  tracker.startRequest(requestId, text, "af_heart", 1.0);

  // Simulate request flow
  await simulateRequestFlow(tracker, requestId);

  // Complete request
  const metrics = tracker.completeRequest(requestId);

  if (metrics) {
    console.log("✅ Request completed successfully");
    console.log("📊 Final Metrics:");
    console.log(`   TTFA: ${metrics.totalTimeToFirstAudio.toFixed(2)}ms`);
    console.log(`   Server Response: ${metrics.requestStartToFirstByte.toFixed(2)}ms`);
    console.log(`   Streaming Efficiency: ${(metrics.streamingEfficiency * 100).toFixed(1)}%`);
    console.log(`   Chunks: ${metrics.chunkCount}`);
    console.log(`   Audio Duration: ${metrics.audioDuration.toFixed(2)}s`);
    console.log(`   Cache Hit: ${metrics.cacheHit}`);
    console.log(`   Provider: ${metrics.providerUsed}`);

    // Validate metrics
    validateMetrics(metrics);
  } else {
    console.log("❌ Request completion failed");
  }

  // Test 2: Error handling
  console.log("\n📋 Test 2: Error Handling");
  const errorRequestId = "test-error-001";

  tracker.startRequest(errorRequestId, "Error test", "af_heart", 1.0);
  tracker.logEvent(errorRequestId, "REQUEST_SENT", {});
  tracker.logEvent(errorRequestId, "ERROR", {
    error: "Simulated server error",
    status: 500,
  });

  const errorMetrics = tracker.completeRequest(errorRequestId);

  if (errorMetrics && errorMetrics.errors.length > 0) {
    console.log("✅ Error handling works correctly");
    console.log(`   Errors: ${errorMetrics.errors.join(", ")}`);
  } else {
    console.log("❌ Error handling failed");
  }

  // Test 3: Multiple requests
  console.log("\n📋 Test 3: Multiple Concurrent Requests");
  const requests = [];

  for (let i = 0; i < 3; i++) {
    const reqId = `concurrent-${i + 1}`;
    tracker.startRequest(reqId, `Request ${i + 1}`, "af_heart", 1.0);
    requests.push(reqId);
  }

  // Simulate concurrent processing
  await Promise.all(requests.map((reqId) => simulateRequestFlow(tracker, reqId)));

  // Complete all requests
  const allMetrics = requests.map((reqId) => tracker.completeRequest(reqId));

  console.log(`✅ Completed ${allMetrics.filter((m) => m !== null).length} concurrent requests`);

  // Test 4: Performance analysis
  console.log("\n📋 Test 4: Performance Analysis");
  const completedFlows = tracker.getCompletedFlows();
  console.log(`   Total completed flows: ${completedFlows.length}`);

  if (completedFlows.length > 0) {
    const avgTTFA =
      completedFlows.reduce((sum, flow) => {
        const firstAudio = flow.events.find((e) => e.stage === "FIRST_AUDIO_CHUNK");
        return sum + (firstAudio ? firstAudio.timestamp - flow.startTime : 0);
      }, 0) / completedFlows.length;

    console.log(`   Average TTFA: ${avgTTFA.toFixed(2)}ms`);
  }

  console.log("\n🎉 Performance tracking tests completed!");
}

async function simulateRequestFlow(tracker: PerformanceTracker, requestId: string) {
  // Simulate realistic request timing
  await delay(100); // Network delay
  tracker.logEvent(requestId, "REQUEST_SENT", {});

  await delay(1500); // Server processing time (simulating the 1836ms we saw)
  tracker.logEvent(requestId, "FIRST_BYTE_RECEIVED", {
    responseTimeMs: 1500,
    status: 200,
  });

  await delay(50); // First chunk processing
  tracker.logEvent(requestId, "FIRST_AUDIO_CHUNK", {
    ttfaMs: 1550,
    chunkSize: 16384,
  });

  // Simulate multiple chunks
  for (let i = 1; i <= 5; i++) {
    await delay(100); // Chunk processing time
    tracker.logEvent(requestId, "AUDIO_CHUNK_RECEIVED", {
      chunkIndex: i + 1,
      chunkSize: 12000 + Math.random() * 4000,
      totalBytesReceived: 50000 + i * 15000,
      elapsedTimeMs: 1550 + i * 100,
    });
  }

  await delay(50); // Final processing
  tracker.logEvent(requestId, "LAST_AUDIO_CHUNK", {
    totalChunks: 6,
    totalBytesReceived: 120000,
    streamingDurationMs: 27390, // Simulating the 27.39s we saw in logs
    efficiency: 0.25, // Simulating the 25.2% efficiency we saw
    audioDurationMs: 6890, // Simulating the 6.89s audio duration we saw
  });
}

function validateMetrics(metrics: any) {
  console.log("\n🔍 Validating Metrics:");

  // Check TTFA calculation
  if (metrics.totalTimeToFirstAudio > 0) {
    console.log("   ✅ TTFA calculation is working (not 0ms)");
  } else {
    console.log("   ❌ TTFA calculation is wrong (showing 0ms)");
  }

  // Check streaming efficiency
  if (metrics.streamingEfficiency < 1.0) {
    console.log("   ✅ Streaming efficiency calculation is realistic");
  } else {
    console.log("   ❌ Streaming efficiency calculation is wrong (showing 100%)");
  }

  // Check server response time
  if (metrics.requestStartToFirstByte > 1000) {
    console.log("   ⚠️  Server response time is high (expected for simulation)");
  } else {
    console.log("   ✅ Server response time is reasonable");
  }

  // Check chunk count
  if (metrics.chunkCount > 0) {
    console.log("   ✅ Chunk tracking is working");
  } else {
    console.log("   ❌ Chunk tracking is not working");
  }
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Run the test
testPerformanceTracking().catch(console.error);
