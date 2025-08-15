#!/usr/bin/env node

/**
 * Simple WebSocket connection test for audio daemon
 */

import WebSocket from "ws";

async function testWebSocketConnection() {
  console.log("Testing WebSocket connection to audio daemon...");

  const wsUrl = "ws://localhost:8081";
  console.log(`Connecting to: ${wsUrl}`);

  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);

    ws.on("open", () => {
      console.log("✅ WebSocket connection established successfully!");

      // Send a test message
      const testMessage = {
        type: "control",
        timestamp: Date.now(),
        data: {
          action: "ping",
        },
      };

      console.log("Sending test message:", testMessage);
      ws.send(JSON.stringify(testMessage));

      // Close connection after test
      setTimeout(() => {
        ws.close();
        resolve(true);
      }, 1000);
    });

    ws.on("message", (data) => {
      try {
        const message = JSON.parse(data.toString());
        console.log("📨 Received message from daemon:", message);
      } catch (error) {
        console.log("📨 Received raw message:", data.toString());
      }
    });

    ws.on("error", (error) => {
      console.error("❌ WebSocket connection error:", error.message);
      reject(error);
    });

    ws.on("close", (code, reason) => {
      console.log(`🔌 WebSocket connection closed - code: ${code}, reason: ${reason}`);
    });

    // Set timeout
    setTimeout(() => {
      if (ws.readyState !== WebSocket.OPEN) {
        reject(new Error("WebSocket connection timeout"));
      }
    }, 5000);
  });
}

// Run the test
testWebSocketConnection()
  .then(() => {
    console.log("✅ WebSocket test completed successfully");
    process.exit(0);
  })
  .catch((error) => {
    console.error("❌ WebSocket test failed:", error.message);
    process.exit(1);
  });
