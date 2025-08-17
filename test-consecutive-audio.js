#!/usr/bin/env node

/**
 * Test consecutive audio streaming requests
 * Simulates dashboard AudioClient behavior to identify potential issues
 */

const testConsecutiveAudio = async () => {
  console.log(
    "📡 Testing consecutive audio streaming through dashboard AudioClient logic..."
  );

  // Simulate the TTS request the dashboard makes
  const testRequest = {
    text: "Hello world test",
    voice: "af_heart",
    speed: 1.0,
    format: "pcm",
    stream: true,
  };

  for (let i = 1; i <= 3; i++) {
    console.log(`\n🔄 Test run ${i}:`);
    const startTime = performance.now();

    try {
      const response = await fetch("http://localhost:8000/v1/audio/speech", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "audio/pcm",
        },
        body: JSON.stringify(testRequest),
      });

      if (!response.ok) {
        console.log(`❌ HTTP Error: ${response.status}`);
        continue;
      }

      let totalBytes = 0;
      let chunkCount = 0;
      const reader = response.body.getReader();

      console.log("📦 Reading chunks...");
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          console.log("✅ Stream ended");
          break;
        }

        totalBytes += value.length;
        chunkCount++;

        if (chunkCount <= 5 || chunkCount % 10 === 0) {
          console.log(`   Chunk ${chunkCount}: ${value.length} bytes`);
        }
      }

      const duration = performance.now() - startTime;
      console.log(
        `✅ Success: ${totalBytes} bytes in ${chunkCount} chunks, ${duration.toFixed(
          2
        )}ms`
      );
    } catch (error) {
      console.log(`❌ Error: ${error.message}`);
    }

    // Small delay between requests
    await new Promise((resolve) => setTimeout(resolve, 200));
  }

  console.log("\n🎯 Testing with different text...");

  // Test with different text to see if it's a caching issue
  const testRequest2 = {
    text: "Different text for testing consecutive runs",
    voice: "af_heart",
    speed: 1.0,
    format: "pcm",
    stream: true,
  };

  try {
    const response = await fetch("http://localhost:8000/v1/audio/speech", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "audio/pcm",
      },
      body: JSON.stringify(testRequest2),
    });

    if (response.ok) {
      let totalBytes = 0;
      const reader = response.body.getReader();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        totalBytes += value.length;
      }
      console.log(`✅ Different text: ${totalBytes} bytes`);
    }
  } catch (error) {
    console.log(`❌ Different text error: ${error.message}`);
  }
};

testConsecutiveAudio().catch(console.error);
