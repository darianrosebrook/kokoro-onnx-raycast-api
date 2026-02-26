/**
 * Integration tests for the audio daemon WebSocket protocol.
 *
 * Tests the full message flow that the Raycast extension uses:
 * connect → control(play) → audio_chunk × N → end_stream → completed
 *
 * Requires: audio daemon running on localhost:8081
 * Skip: tests auto-skip if daemon is not running
 *
 * Run: cd raycast && npx vitest run bin/__tests__/audio-daemon-integration.test.js
 */

import { describe, it, expect, beforeAll, afterAll, afterEach } from "vitest";
import WebSocket from "ws";

const DAEMON_PORT = 8081;
const DAEMON_URL = `ws://localhost:${DAEMON_PORT}`;
const DAEMON_HEALTH_URL = `http://localhost:${DAEMON_PORT}/health`;

let daemonAvailable = false;

beforeAll(async () => {
  try {
    const res = await fetch(DAEMON_HEALTH_URL, { signal: AbortSignal.timeout(2000) });
    daemonAvailable = res.ok;
  } catch {
    daemonAvailable = false;
  }
});

function skipIfNoDaemon() {
  if (!daemonAvailable) {
    return true;
  }
  return false;
}

function connectWs() {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(DAEMON_URL);
    ws.on("open", () => resolve(ws));
    ws.on("error", reject);
    setTimeout(() => reject(new Error("WebSocket connection timeout")), 5000);
  });
}

function waitForMessage(ws, type, timeoutMs = 10000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`Timeout waiting for ${type}`)), timeoutMs);
    const handler = (data) => {
      const msg = JSON.parse(data.toString());
      if (msg.type === type) {
        clearTimeout(timer);
        ws.removeListener("message", handler);
        resolve(msg);
      }
    };
    ws.on("message", handler);
  });
}

function collectMessages(ws, durationMs) {
  return new Promise((resolve) => {
    const messages = [];
    const handler = (data) => messages.push(JSON.parse(data.toString()));
    ws.on("message", handler);
    setTimeout(() => {
      ws.removeListener("message", handler);
      resolve(messages);
    }, durationMs);
  });
}


// --- Health endpoint ---

describe("Daemon health endpoint", () => {
  it.skipIf(skipIfNoDaemon())("returns healthy status", async () => {
    const res = await fetch(DAEMON_HEALTH_URL);
    const data = await res.json();
    expect(data.status).toBe("healthy");
    expect(data.version).toBe("2.0.0");
    expect(data).toHaveProperty("uptime");
    expect(data).toHaveProperty("clients");
  });
});


// --- WebSocket connection lifecycle ---

describe("WebSocket connection lifecycle", () => {
  let ws;

  afterEach(() => {
    if (ws && ws.readyState <= WebSocket.OPEN) ws.close();
  });

  it.skipIf(skipIfNoDaemon())("connects and receives welcome status", async () => {
    ws = await connectWs();
    const msg = await waitForMessage(ws, "status", 3000);
    expect(msg.type).toBe("status");
    expect(msg.data).toHaveProperty("state");
  });

  it.skipIf(skipIfNoDaemon())("heartbeat responds with ack", async () => {
    ws = await connectWs();
    // Drain welcome message
    await waitForMessage(ws, "status", 3000);

    ws.send(JSON.stringify({ type: "heartbeat", timestamp: Date.now() }));
    const ack = await waitForMessage(ws, "heartbeat", 3000);
    expect(ack.data.status).toBe("ok");
  });

  it.skipIf(skipIfNoDaemon())("multiple clients can connect", async () => {
    const ws1 = await connectWs();
    const ws2 = await connectWs();

    // Both should receive welcome
    await waitForMessage(ws1, "status", 3000);
    await waitForMessage(ws2, "status", 3000);

    ws1.close();
    ws2.close();
  });

  it.skipIf(skipIfNoDaemon())("survives malformed JSON", async () => {
    ws = await connectWs();
    await waitForMessage(ws, "status", 3000);

    // Send garbage — daemon should not crash
    ws.send("{ not valid json !!!");
    ws.send("<<< xml maybe? >>>");
    ws.send("");

    // Should still be able to send valid message after
    ws.send(JSON.stringify({ type: "heartbeat", timestamp: Date.now() }));
    const ack = await waitForMessage(ws, "heartbeat", 3000);
    expect(ack.data.status).toBe("ok");
  });
});


// --- Audio chunk protocol ---

describe("Audio chunk protocol", () => {
  let ws;

  afterEach(() => {
    if (ws && ws.readyState <= WebSocket.OPEN) ws.close();
  });

  it.skipIf(skipIfNoDaemon())("accepts base64-encoded chunks", async () => {
    ws = await connectWs();
    await waitForMessage(ws, "status", 3000);

    // Send a control play first
    ws.send(JSON.stringify({
      type: "control",
      timestamp: Date.now(),
      data: { action: "play" },
    }));

    // Send a small base64-encoded PCM chunk (silence)
    const silence = Buffer.alloc(4800, 0); // 100ms of 16-bit mono 24kHz
    ws.send(JSON.stringify({
      type: "audio_chunk",
      timestamp: Date.now(),
      data: { chunk: silence.toString("base64") },
    }));

    // Send end_stream
    ws.send(JSON.stringify({ type: "end_stream", timestamp: Date.now() }));

    // Should eventually get completed
    const completed = await waitForMessage(ws, "completed", 15000);
    expect(completed.data.state).toBe("completed");
  });

  it.skipIf(skipIfNoDaemon())("handles rapid sequential sessions", async () => {
    ws = await connectWs();
    await waitForMessage(ws, "status", 3000);

    for (let session = 0; session < 3; session++) {
      ws.send(JSON.stringify({
        type: "control",
        timestamp: Date.now(),
        data: { action: "play" },
      }));

      // 200ms of silence
      const chunk = Buffer.alloc(9600, 0);
      ws.send(JSON.stringify({
        type: "audio_chunk",
        timestamp: Date.now(),
        data: { chunk: chunk.toString("base64") },
      }));

      ws.send(JSON.stringify({ type: "end_stream", timestamp: Date.now() }));

      const completed = await waitForMessage(ws, "completed", 15000);
      expect(completed.data.state).toBe("completed");
    }
  });

  it.skipIf(skipIfNoDaemon())("stop interrupts playback", async () => {
    ws = await connectWs();
    await waitForMessage(ws, "status", 3000);

    ws.send(JSON.stringify({
      type: "control",
      timestamp: Date.now(),
      data: { action: "play" },
    }));

    // Send a large chunk (2 seconds of audio)
    const bigChunk = Buffer.alloc(96000, 0x40);
    ws.send(JSON.stringify({
      type: "audio_chunk",
      timestamp: Date.now(),
      data: { chunk: bigChunk.toString("base64") },
    }));

    // Immediately stop
    ws.send(JSON.stringify({
      type: "control",
      timestamp: Date.now(),
      data: { action: "stop" },
    }));

    // Should not hang — give it a moment
    await new Promise((resolve) => setTimeout(resolve, 500));
    // Connection should still be alive
    expect(ws.readyState).toBe(WebSocket.OPEN);
  });

  it.skipIf(skipIfNoDaemon())("timing_analysis returns data after playback", async () => {
    ws = await connectWs();
    await waitForMessage(ws, "status", 3000);

    ws.send(JSON.stringify({ type: "timing_analysis", timestamp: Date.now() }));
    const analysis = await waitForMessage(ws, "timing_analysis", 3000);
    expect(analysis.data).toHaveProperty("basic");
    expect(analysis.data).toHaveProperty("chunkAnalysis");
    expect(analysis.data).toHaveProperty("playbackAnalysis");
  });
});
