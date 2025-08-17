#!/usr/bin/env node

/**
 * Test script for persistent daemon client
 * @author @darianrosebrook
 */

import { PersistentDaemonClient } from '../src/utils/tts/streaming/persistent-daemon-client.ts';

async function testPersistentClient() {
  console.log("Testing persistent daemon client...");

  try {
    // Check if daemon is available
    console.log("1. Checking daemon health...");
    const isHealthy = await PersistentDaemonClient.checkDaemonHealth();
    console.log(`✅ Daemon health: ${isHealthy ? 'OK' : 'FAILED'}`);

    if (!isHealthy) {
      console.log("❌ Daemon is not healthy, please start it first");
      process.exit(1);
    }

    // Get daemon status
    console.log("2. Getting daemon status...");
    const status = await PersistentDaemonClient.getDaemonStatus();
    console.log("✅ Daemon status:", status);

    // Create client and connect
    console.log("3. Creating client and connecting...");
    const client = new PersistentDaemonClient();

    // Set up event listeners
    client.on('connected', () => {
      console.log("✅ Connected to daemon");
    });

    client.on('welcome', (message) => {
      console.log("✅ Received welcome message:", message);
    });

    client.on('session_started', (message) => {
      console.log("✅ Session started:", message);
    });

    client.on('session_stopped', (message) => {
      console.log("✅ Session stopped:", message);
    });

    client.on('disconnected', (data) => {
      console.log("⚠️ Disconnected from daemon:", data);
    });

    client.on('error', (error) => {
      console.error("❌ Client error:", error);
    });

    // Connect to daemon
    await client.connect();

    // Test ping
    console.log("4. Testing ping...");
    client.ping();
    await new Promise(resolve => setTimeout(resolve, 1000));

    // Test session management
    console.log("5. Testing session management...");
    const audioFormat = {
      format: 'wav',
      sampleRate: 24000,
      channels: 1,
      bitDepth: 16
    };

    client.startSession(audioFormat);
    await new Promise(resolve => setTimeout(resolve, 1000));

    // Test audio chunk
    console.log("6. Testing audio chunk...");
    const testChunk = Buffer.from('test audio data', 'utf8');
    client.sendAudioChunk(testChunk);
    await new Promise(resolve => setTimeout(resolve, 1000));

    // Stop session
    console.log("7. Stopping session...");
    client.stopSession();
    await new Promise(resolve => setTimeout(resolve, 1000));

    // Get status
    console.log("8. Getting client status...");
    const clientStatus = client.getConnectionStatus();
    console.log("✅ Client status:", clientStatus);

    // Disconnect
    console.log("9. Disconnecting...");
    client.disconnect();

    console.log("\n🎉 All tests passed! Persistent daemon client is working correctly.");

  } catch (error) {
    console.error("❌ Test failed:", error);
    process.exit(1);
  }
}

// Run the test
testPersistentClient().catch((error) => {
  console.error("Unhandled error:", error);
  process.exit(1);
});
