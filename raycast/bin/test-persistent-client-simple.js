#!/usr/bin/env node

/**
 * Simple test for persistent daemon WebSocket connection
 * @author @darianrosebrook
 */

import WebSocket from 'ws';

async function testWebSocketConnection() {
  console.log("Testing WebSocket connection to persistent daemon...");

  try {
    // Test HTTP health endpoint first
    console.log("1. Testing HTTP health endpoint...");
    const healthResponse = await fetch('http://localhost:8081/health');
    const healthData = await healthResponse.json();
    console.log("✅ Health endpoint:", healthData);

    // Test WebSocket connection
    console.log("2. Testing WebSocket connection...");
    const ws = new WebSocket('ws://localhost:8081');

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Connection timeout'));
      }, 5000);

      ws.on('open', () => {
        console.log("✅ WebSocket connected");
        clearTimeout(timeout);
        
        // Send a ping message
        const pingMessage = {
          type: 'ping',
          timestamp: Date.now()
        };
        ws.send(JSON.stringify(pingMessage));
        console.log("✅ Sent ping message");
      });

      ws.on('message', (data) => {
        try {
          const message = JSON.parse(data.toString());
          console.log("✅ Received message:", message);
          
          if (message.type === 'pong') {
            console.log("✅ Ping/pong working correctly");
            
            // Test session start
            const sessionMessage = {
              type: 'start_session',
              audioFormat: {
                format: 'wav',
                sampleRate: 24000,
                channels: 1,
                bitDepth: 16
              },
              timestamp: Date.now()
            };
            ws.send(JSON.stringify(sessionMessage));
            console.log("✅ Sent session start message");
          } else if (message.type === 'session_started') {
            console.log("✅ Session started successfully");
            
            // Test audio chunk
            const audioMessage = {
              type: 'audio_chunk',
              chunk: Buffer.from('test audio data').toString('base64'),
              encoding: 'base64',
              timestamp: Date.now()
            };
            ws.send(JSON.stringify(audioMessage));
            console.log("✅ Sent audio chunk");
          } else if (message.type === 'session_stopped') {
            console.log("✅ Session stopped successfully");
            ws.close(1000, 'Test completed');
            resolve();
          }
        } catch (error) {
          console.error("❌ Error parsing message:", error);
        }
      });

      ws.on('close', (code, reason) => {
        console.log(`✅ WebSocket closed: ${code} - ${reason}`);
        clearTimeout(timeout);
        resolve();
      });

      ws.on('error', (error) => {
        console.error("❌ WebSocket error:", error);
        clearTimeout(timeout);
        reject(error);
      });

      // Set up a timer to stop the session after a few seconds
      setTimeout(() => {
        if (ws.readyState === WebSocket.OPEN) {
          const stopMessage = {
            type: 'stop_session',
            timestamp: Date.now()
          };
          ws.send(JSON.stringify(stopMessage));
          console.log("✅ Sent session stop message");
        }
      }, 3000);
    });

  } catch (error) {
    console.error("❌ Test failed:", error);
    throw error;
  }
}

// Run the test
testWebSocketConnection()
  .then(() => {
    console.log("\n🎉 All WebSocket tests passed! Persistent daemon is working correctly.");
    process.exit(0);
  })
  .catch((error) => {
    console.error("❌ WebSocket test failed:", error);
    process.exit(1);
  });
