#!/usr/bin/env node

/**
 * Test consecutive audio runs through the audio daemon
 * This simulates what the dashboard does when making multiple TTS requests
 */

const WebSocket = require("ws");

const testConsecutiveDaemonRuns = async () => {
  console.log("🎵 Testing consecutive audio runs through audio daemon...");

  const testRequest = {
    text: "Hello world test",
    voice: "af_heart",
    speed: 1.0,
    format: "pcm",
    stream: true,
  };

  for (let run = 1; run <= 3; run++) {
    console.log(`\n🔄 Run ${run}: Testing audio daemon state reset`);

    // Check initial state
    try {
      const healthResponse = await fetch("http://localhost:8081/health");
      const health = await healthResponse.json();
      console.log(
        `   Initial state: chunks=${
          health.audioProcessor.stats.chunksReceived
        }, buffer=${health.audioProcessor.stats.bufferUtilization.toFixed(3)}`
      );
    } catch (error) {
      console.log(`   ❌ Health check failed: ${error.message}`);
      continue;
    }

    // Connect to WebSocket
    const ws = new WebSocket("ws://localhost:8081");

    await new Promise((resolve, reject) => {
      let totalChunks = 0;
      let totalBytes = 0;
      const startTime = performance.now();

      ws.on("open", async () => {
        console.log("   📡 Connected to audio daemon");

        try {
          // Get audio data from TTS server
          const response = await fetch(
            "http://localhost:8000/v1/audio/speech",
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                Accept: "audio/pcm",
              },
              body: JSON.stringify(testRequest),
            }
          );

          if (!response.ok) {
            throw new Error(`TTS Error: ${response.status}`);
          }

          const reader = response.body.getReader();
          let sequenceNumber = 0;

          // Stream audio chunks to daemon
          while (true) {
            const { done, value } = await reader.read();
            if (done) {
              console.log("   📦 Sending end_stream to daemon");
              ws.send(
                JSON.stringify({
                  type: "end_stream",
                  timestamp: Date.now(),
                  data: {},
                })
              );
              break;
            }

            // Send chunk to daemon
            ws.send(
              JSON.stringify({
                type: "audio_chunk",
                timestamp: Date.now(),
                data: {
                  chunk: value,
                  format: {
                    format: "pcm",
                    sampleRate: 24000,
                    channels: 1,
                    bitDepth: 16,
                  },
                  sequence: sequenceNumber++,
                },
              })
            );

            totalChunks++;
            totalBytes += value.length;
          }

          // Wait a bit for processing
          setTimeout(() => {
            ws.close();
            resolve();
          }, 500);
        } catch (error) {
          console.log(`   ❌ Audio streaming error: ${error.message}`);
          ws.close();
          reject(error);
        }
      });

      ws.on("message", (data) => {
        try {
          const message = JSON.parse(data);
          if (message.type === "status") {
            console.log(
              `   📊 Status: chunks=${
                message.data.performance?.stats?.chunksReceived || 0
              }, buffer=${(message.data.bufferUtilization * 100).toFixed(1)}%`
            );
          } else if (message.type === "completed") {
            console.log("   ✅ Audio playback completed");
          }
        } catch (e) {
          // Ignore parsing errors
        }
      });

      ws.on("error", (error) => {
        console.log(`   ❌ WebSocket error: ${error.message}`);
        reject(error);
      });

      ws.on("close", () => {
        const duration = performance.now() - startTime;
        console.log(
          `   ✅ Run ${run} completed: ${totalChunks} chunks, ${totalBytes} bytes, ${duration.toFixed(
            2
          )}ms`
        );
        resolve();
      });
    });

    // Check final state
    try {
      await new Promise((resolve) => setTimeout(resolve, 1000)); // Wait for state to settle
      const healthResponse = await fetch("http://localhost:8081/health");
      const health = await healthResponse.json();
      console.log(
        `   Final state: chunks=${
          health.audioProcessor.stats.chunksReceived
        }, buffer=${health.audioProcessor.stats.bufferUtilization.toFixed(
          3
        )}, playing=${health.audioProcessor.isPlaying}`
      );
    } catch (error) {
      console.log(`   ❌ Final health check failed: ${error.message}`);
    }
  }

  console.log("\n🎯 Consecutive runs test completed!");
};

testConsecutiveDaemonRuns().catch(console.error);
