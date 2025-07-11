/**
 * Test script to verify dynamic streaming fix
 */

const SERVER_URL = "http://localhost:8000";

async function testDynamicStreaming() {
  console.log("🎯 Testing Dynamic Streaming Fix");
  console.log("================================");

  // Test with short text that caused the original issue
  const shortText =
    "The issue wasn't the stream ending too quickly - it was the client waiting for the entire stream before starting playback. Our fix now:1.";

  // Test with longer text to see dynamic pacing
  const longText =
    "This is a much longer text that should demonstrate the dynamic streaming pacing fix. Each chunk should be paced based on its actual audio duration rather than fixed delays. The streaming should now properly match the audio playback duration. When we have 12 seconds of audio, the stream should take approximately 12 seconds to complete, not just 140ms with artificial delays.";

  console.log("📋 Test Cases:");
  console.log(`1. Short text (${shortText.length} chars)`);
  console.log(`2. Long text (${longText.length} chars)`);
  console.log("");

  for (const [testName, text] of [
    ["Short Text", shortText],
    ["Long Text", longText],
  ]) {
    console.log(`🧪 Testing ${testName}:`);
    console.log(`Text: "${text.substring(0, 60)}..."`);
    console.log(`Length: ${text.length} characters`);

    const startTime = performance.now();
    let firstChunkTime = null;
    let lastChunkTime = null;
    let chunkCount = 0;
    let totalBytes = 0;

    try {
      const response = await fetch(`${SERVER_URL}/v1/audio/speech`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "audio/wav",
        },
        body: JSON.stringify({
          text: text,
          voice: "af_heart",
          speed: 1.0,
          lang: "en-us",
          stream: true,
          format: "wav",
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body.getReader();

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          lastChunkTime = performance.now();
          break;
        }

        if (value) {
          if (firstChunkTime === null) {
            firstChunkTime = performance.now();
          }

          chunkCount++;
          totalBytes += value.length;

          // Log chunk details every 5 chunks
          if (chunkCount % 5 === 0) {
            const elapsedTime = performance.now() - startTime;
            console.log(
              `  Chunk ${chunkCount}: ${value.length} bytes at ${elapsedTime.toFixed(0)}ms`
            );
          }
        }
      }

      const totalTime = lastChunkTime - startTime;
      const firstChunkLatency = firstChunkTime - startTime;
      const streamingWindow = lastChunkTime - firstChunkTime;

      console.log(`✅ ${testName} Results:`);
      console.log(`  First chunk: ${firstChunkLatency.toFixed(2)}ms`);
      console.log(`  Streaming window: ${streamingWindow.toFixed(2)}ms`);
      console.log(`  Total time: ${totalTime.toFixed(2)}ms`);
      console.log(`  Chunks: ${chunkCount}`);
      console.log(`  Total bytes: ${totalBytes}`);
      console.log(`  Average chunk size: ${(totalBytes / chunkCount).toFixed(0)} bytes`);
      console.log(
        `  Average chunk rate: ${(chunkCount / (streamingWindow / 1000)).toFixed(1)} chunks/sec`
      );

      // Estimate audio duration from total bytes
      const SAMPLE_RATE = 24000;
      const BYTES_PER_SAMPLE = 2;
      const estimatedAudioDuration = (totalBytes / BYTES_PER_SAMPLE / SAMPLE_RATE) * 1000;

      console.log(`  Estimated audio duration: ${estimatedAudioDuration.toFixed(0)}ms`);
      console.log(
        `  Streaming efficiency: ${((streamingWindow / estimatedAudioDuration) * 100).toFixed(1)}% of audio duration`
      );

      // Check if streaming window is reasonable relative to estimated audio duration
      const streamingRatio = streamingWindow / estimatedAudioDuration;
      if (streamingRatio > 0.5 && streamingRatio < 1.5) {
        console.log(
          `  ✅ Good streaming pacing (${(streamingRatio * 100).toFixed(0)}% of audio duration)`
        );
      } else if (streamingRatio < 0.1) {
        console.log(
          `  ⚠️  Very fast streaming (${(streamingRatio * 100).toFixed(0)}% of audio duration)`
        );
      } else {
        console.log(
          `  ⚠️  Unusual streaming ratio (${(streamingRatio * 100).toFixed(0)}% of audio duration)`
        );
      }

      console.log("");
    } catch (error) {
      console.error(`❌ ${testName} failed:`, error.message);
      console.log("");
    }
  }
}

// Run the test
testDynamicStreaming().catch(console.error);
