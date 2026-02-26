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

import { describe, it, expect, afterEach } from "vitest";
import WebSocket from "ws";

const DAEMON_PORT = 8081;
const DAEMON_URL = `ws://localhost:${DAEMON_PORT}`;
const DAEMON_HEALTH_URL = `http://localhost:${DAEMON_PORT}/health`;

// Top-level await so the check runs BEFORE test collection.
// it.skipIf() evaluates its argument at definition time (before beforeAll),
// so a beforeAll + skipIfNoDaemon() pattern always skips.
let daemonAvailable = false;
try {
  const res = await fetch(DAEMON_HEALTH_URL, { signal: AbortSignal.timeout(2000) });
  daemonAvailable = res.ok;
} catch {
  daemonAvailable = false;
}

/**
 * Connect to the daemon and immediately start buffering messages.
 * Returns { ws, messages } where messages is a live array of parsed messages
 * received so far. This avoids the race where the daemon sends the welcome
 * status before waitForMessage is attached.
 */
function connectWs() {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(DAEMON_URL);
    const messages = [];
    ws.on("message", (data) => {
      messages.push(JSON.parse(data.toString()));
    });
    ws.on("open", () => resolve({ ws, messages }));
    ws.on("error", reject);
    setTimeout(() => reject(new Error("WebSocket connection timeout")), 5000);
  });
}

/**
 * Wait for a message of the given type. Checks the already-buffered messages
 * first, then listens for new ones.
 */
function waitForMessage(ws, messages, type, timeoutMs = 10000) {
  return new Promise((resolve, reject) => {
    // Check buffered messages first
    const existing = messages.find((m) => m.type === type);
    if (existing) {
      // Remove it so subsequent waits for the same type get the next one
      messages.splice(messages.indexOf(existing), 1);
      return resolve(existing);
    }

    const timer = setTimeout(() => reject(new Error(`Timeout waiting for ${type}`)), timeoutMs);
    // Poll the buffer — new messages are pushed by the persistent listener
    const interval = setInterval(() => {
      const idx = messages.findIndex((m) => m.type === type);
      if (idx !== -1) {
        clearTimeout(timer);
        clearInterval(interval);
        const msg = messages[idx];
        messages.splice(idx, 1);
        resolve(msg);
      }
    }, 20);

    // Clean up on timeout
    const origReject = reject;
    reject = (err) => {
      clearInterval(interval);
      origReject(err);
    };
  });
}


// --- Health endpoint ---

describe("Daemon health endpoint", () => {
  it.skipIf(!daemonAvailable)("returns healthy status", async () => {
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
  let conn;

  afterEach(() => {
    if (conn?.ws?.readyState <= WebSocket.OPEN) conn.ws.close();
  });

  it.skipIf(!daemonAvailable)("connects and receives welcome status", async () => {
    conn = await connectWs();
    const msg = await waitForMessage(conn.ws, conn.messages, "status", 3000);
    expect(msg.type).toBe("status");
    expect(msg.data).toHaveProperty("state");
  });

  it.skipIf(!daemonAvailable)("heartbeat responds with ack", async () => {
    conn = await connectWs();
    await waitForMessage(conn.ws, conn.messages, "status", 3000);

    conn.ws.send(JSON.stringify({ type: "heartbeat", timestamp: Date.now() }));
    const ack = await waitForMessage(conn.ws, conn.messages, "heartbeat", 3000);
    expect(ack.data.status).toBe("ok");
  });

  it.skipIf(!daemonAvailable)("multiple clients can connect", async () => {
    const conn1 = await connectWs();
    const conn2 = await connectWs();

    // Both should receive welcome — messages are buffered from connection time
    await waitForMessage(conn1.ws, conn1.messages, "status", 3000);
    await waitForMessage(conn2.ws, conn2.messages, "status", 3000);

    conn1.ws.close();
    conn2.ws.close();
  });

  it.skipIf(!daemonAvailable)("survives malformed JSON", async () => {
    conn = await connectWs();
    await waitForMessage(conn.ws, conn.messages, "status", 3000);

    // Send garbage — daemon should not crash
    conn.ws.send("{ not valid json !!!");
    conn.ws.send("<<< xml maybe? >>>");
    conn.ws.send("");

    // Should still be able to send valid message after
    conn.ws.send(JSON.stringify({ type: "heartbeat", timestamp: Date.now() }));
    const ack = await waitForMessage(conn.ws, conn.messages, "heartbeat", 3000);
    expect(ack.data.status).toBe("ok");
  });
});


// --- Audio chunk protocol ---

describe("Audio chunk protocol", () => {
  let conn;

  afterEach(() => {
    if (conn?.ws?.readyState <= WebSocket.OPEN) conn.ws.close();
  });

  it.skipIf(!daemonAvailable)(
    "accepts base64-encoded chunks",
    async () => {
      conn = await connectWs();
      await waitForMessage(conn.ws, conn.messages, "status", 3000);

      // Send a control play first
      conn.ws.send(JSON.stringify({
        type: "control",
        timestamp: Date.now(),
        data: { action: "play" },
      }));

      // Send a small base64-encoded PCM chunk (silence)
      const silence = Buffer.alloc(4800, 0); // 100ms of 16-bit mono 24kHz
      conn.ws.send(JSON.stringify({
        type: "audio_chunk",
        timestamp: Date.now(),
        data: { chunk: silence.toString("base64") },
      }));

      // Send end_stream
      conn.ws.send(JSON.stringify({ type: "end_stream", timestamp: Date.now() }));

      // Should eventually get completed — sox/afplay needs time to process
      const completed = await waitForMessage(conn.ws, conn.messages, "completed", 15000);
      expect(completed.data.state).toBe("completed");
    },
    20000, // vitest timeout — must exceed the waitForMessage timeout
  );

  it.skipIf(!daemonAvailable)(
    "handles rapid sequential sessions",
    async () => {
      conn = await connectWs();
      await waitForMessage(conn.ws, conn.messages, "status", 3000);

      // Ensure clean state — stop any lingering session from prior tests
      conn.ws.send(JSON.stringify({
        type: "control",
        timestamp: Date.now(),
        data: { action: "stop" },
      }));
      await new Promise((r) => setTimeout(r, 500));

      for (let session = 0; session < 3; session++) {
        conn.ws.send(JSON.stringify({
          type: "control",
          timestamp: Date.now(),
          data: { action: "play" },
        }));

        // Wait for sox to spawn before sending audio data
        await new Promise((r) => setTimeout(r, 500));

        // 200ms of silence
        const chunk = Buffer.alloc(9600, 0);
        conn.ws.send(JSON.stringify({
          type: "audio_chunk",
          timestamp: Date.now(),
          data: { chunk: chunk.toString("base64") },
        }));

        conn.ws.send(JSON.stringify({ type: "end_stream", timestamp: Date.now() }));

        const completed = await waitForMessage(conn.ws, conn.messages, "completed", 15000);
        expect(completed.data.state).toBe("completed");

        // Wait for state reset between sessions
        await new Promise((r) => setTimeout(r, 500));
      }
    },
    60000, // 3 sequential sessions × up to 15s each
  );

  it.skipIf(!daemonAvailable)("stop interrupts playback", async () => {
    conn = await connectWs();
    await waitForMessage(conn.ws, conn.messages, "status", 3000);

    conn.ws.send(JSON.stringify({
      type: "control",
      timestamp: Date.now(),
      data: { action: "play" },
    }));

    // Send a large chunk (2 seconds of audio)
    const bigChunk = Buffer.alloc(96000, 0x40);
    conn.ws.send(JSON.stringify({
      type: "audio_chunk",
      timestamp: Date.now(),
      data: { chunk: bigChunk.toString("base64") },
    }));

    // Immediately stop
    conn.ws.send(JSON.stringify({
      type: "control",
      timestamp: Date.now(),
      data: { action: "stop" },
    }));

    // Should not hang — give it a moment
    await new Promise((resolve) => setTimeout(resolve, 500));
    // Connection should still be alive
    expect(conn.ws.readyState).toBe(WebSocket.OPEN);
  });

  it.skipIf(!daemonAvailable)("timing_analysis returns data after playback", async () => {
    conn = await connectWs();
    await waitForMessage(conn.ws, conn.messages, "status", 3000);

    conn.ws.send(JSON.stringify({ type: "timing_analysis", timestamp: Date.now() }));
    const analysis = await waitForMessage(conn.ws, conn.messages, "timing_analysis", 3000);
    expect(analysis.data).toHaveProperty("basic");
    expect(analysis.data).toHaveProperty("chunkAnalysis");
    expect(analysis.data).toHaveProperty("playbackAnalysis");
  });
});
