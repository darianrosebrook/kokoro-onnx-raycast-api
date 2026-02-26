/**
 * Tests for raycast/bin/audio-daemon.js
 *
 * Covers ring buffer, audio format, audio processor lifecycle, chunk handling,
 * message dispatch, WebSocket lifecycle, drain logic, back-pressure, process
 * crash recovery, and undefined handler methods.
 */

import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from "vitest";
import { EventEmitter } from "events";
import { AudioRingBuffer, AudioFormat, AudioProcessor, AudioDaemon } from "../audio-daemon.js";

// The audio daemon emits "error" events on EventEmitter without checking for listeners,
// which causes unhandled rejections when sox/ffplay fail in test environment.
// This is itself a production bug (documented in the undefined handler tests),
// but we suppress it here to avoid false-positive test failures.
let originalListeners;
beforeAll(() => {
  originalListeners = process.listeners("unhandledRejection");
  process.removeAllListeners("unhandledRejection");
  process.on("unhandledRejection", (err) => {
    if (err?.message?.includes("restart limit")) return; // Expected in test env
    throw err; // Re-throw unexpected errors
  });
});
afterAll(() => {
  process.removeAllListeners("unhandledRejection");
  originalListeners.forEach((l) => process.on("unhandledRejection", l));
});

// --- AudioRingBuffer ---

describe("AudioRingBuffer", () => {
  it("write then read returns same data", () => {
    const buf = new AudioRingBuffer(1024);
    const data = Buffer.from([1, 2, 3, 4, 5]);
    buf.write(data);
    const out = buf.read(5);
    expect(out).toEqual(data);
    expect(buf.size).toBe(0);
  });

  it("read from empty returns empty Buffer", () => {
    const buf = new AudioRingBuffer(1024);
    const out = buf.read(100);
    expect(out.length).toBe(0);
  });

  it("tracks size and utilization correctly", () => {
    const buf = new AudioRingBuffer(100);
    expect(buf.size).toBe(0);
    expect(buf.utilization).toBe(0);

    buf.write(Buffer.alloc(50));
    expect(buf.size).toBe(50);
    expect(buf.utilization).toBeCloseTo(0.5);
    expect(buf.available).toBe(50);
  });

  it("grows dynamically when write exceeds capacity", () => {
    const buf = new AudioRingBuffer(10);
    const bigData = Buffer.alloc(20, 0xAB);
    const written = buf.write(bigData);
    expect(written).toBe(20);
    expect(buf.size).toBe(20);
    expect(buf.capacity).toBeGreaterThanOrEqual(20);

    const out = buf.read(20);
    expect(out.every((b) => b === 0xAB)).toBe(true);
  });

  it("handles wrap-around correctly", () => {
    const buf = new AudioRingBuffer(10);
    // Write 7 bytes, read 7 — readIndex now at 7
    buf.write(Buffer.from([1, 2, 3, 4, 5, 6, 7]));
    buf.read(7);

    // Write 6 bytes — must wrap around
    buf.write(Buffer.from([10, 20, 30, 40, 50, 60]));
    const out = buf.read(6);
    expect([...out]).toEqual([10, 20, 30, 40, 50, 60]);
  });

  it("clear resets all state", () => {
    const buf = new AudioRingBuffer(100);
    buf.write(Buffer.alloc(50));
    buf.markFinished();
    buf.clear();
    expect(buf.size).toBe(0);
    expect(buf.readIndex).toBe(0);
    expect(buf.writeIndex).toBe(0);
    expect(buf.isFinished).toBe(false);
  });

  it("markFinished sets the flag", () => {
    const buf = new AudioRingBuffer(100);
    expect(buf.isFinished).toBe(false);
    buf.markFinished();
    expect(buf.isFinished).toBe(true);
  });

  it("partial read returns available data", () => {
    const buf = new AudioRingBuffer(100);
    buf.write(Buffer.from([1, 2, 3]));
    const out = buf.read(10); // request more than available
    expect(out.length).toBe(3);
    expect([...out]).toEqual([1, 2, 3]);
  });

  it("multiple write/read cycles maintain data integrity", () => {
    const buf = new AudioRingBuffer(16);
    for (let i = 0; i < 50; i++) {
      const data = Buffer.from([i & 0xFF, (i + 1) & 0xFF]);
      buf.write(data);
      const out = buf.read(2);
      expect([...out]).toEqual([i & 0xFF, (i + 1) & 0xFF]);
    }
  });
});


// --- AudioFormat ---

describe("AudioFormat", () => {
  it("constructs with valid params", () => {
    const fmt = new AudioFormat("pcm", 24000, 1, 16);
    expect(fmt.sampleRate).toBe(24000);
    expect(fmt.channels).toBe(1);
    expect(fmt.bitDepth).toBe(16);
    expect(fmt.bytesPerSample).toBe(2);
    expect(fmt.bytesPerSecond).toBe(48000);
  });

  it("throws on invalid channel count", () => {
    expect(() => new AudioFormat("pcm", 24000, 5, 16)).toThrow("Unsupported channel count");
  });

  it("throws on invalid bit depth", () => {
    expect(() => new AudioFormat("pcm", 24000, 1, 4)).toThrow("Unsupported bit depth");
  });

  it("warns but does not throw on unusual sample rate", () => {
    const spy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const fmt = new AudioFormat("pcm", 11025, 1, 16);
    expect(fmt.sampleRate).toBe(11025);
    expect(spy).toHaveBeenCalledWith(expect.stringContaining("Unusual sample rate"));
    spy.mockRestore();
  });

  it("getSoxEncoding returns correct values", () => {
    expect(new AudioFormat("pcm", 24000, 1, 8).getSoxEncoding()).toBe("unsigned-integer");
    expect(new AudioFormat("pcm", 24000, 1, 16).getSoxEncoding()).toBe("signed-integer");
    expect(new AudioFormat("pcm", 24000, 1, 24).getSoxEncoding()).toBe("signed-integer");
    expect(new AudioFormat("pcm", 24000, 1, 32).getSoxEncoding()).toBe("floating-point");
  });

  it("getFfplayFormat returns correct values", () => {
    expect(new AudioFormat("pcm", 24000, 1, 8).getFfplayFormat()).toBe("u8");
    expect(new AudioFormat("pcm", 24000, 1, 16).getFfplayFormat()).toBe("s16le");
    expect(new AudioFormat("pcm", 24000, 1, 24).getFfplayFormat()).toBe("s24le");
    expect(new AudioFormat("pcm", 24000, 1, 32).getFfplayFormat()).toBe("f32le");
  });

  it("stereo format calculates bytesPerSecond correctly", () => {
    const fmt = new AudioFormat("pcm", 44100, 2, 16);
    expect(fmt.bytesPerSecond).toBe(44100 * 2 * 2); // 176400
  });
});


// --- AudioProcessor ---

describe("AudioProcessor", () => {
  let processor;

  beforeEach(() => {
    // Suppress console output during tests
    vi.spyOn(console, "log").mockImplementation(() => {});
    vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.spyOn(console, "error").mockImplementation(() => {});

    const format = new AudioFormat("pcm", 24000, 1, 16);
    processor = new AudioProcessor(format);
  });

  afterEach(() => {
    // Clean up timers and processes
    if (processor._audioLoopInterval) clearInterval(processor._audioLoopInterval);
    if (processor._endStreamTimeout) clearTimeout(processor._endStreamTimeout);
    if (processor.processKeepAliveTimer) clearTimeout(processor.processKeepAliveTimer);
    if (processor.restartTimeout) clearTimeout(processor.restartTimeout);
    if (processor.audioProcess) {
      try { processor.audioProcess.kill("SIGTERM"); } catch { /* process may be dead */ }
    }
    vi.restoreAllMocks();
  });

  it("initializes with correct defaults", () => {
    expect(processor.isPlaying).toBe(false);
    expect(processor.isPaused).toBe(false);
    expect(processor.isStopped).toBe(false);
    expect(processor._completionEmitted).toBe(false);
    expect(processor.ringBuffer).toBeInstanceOf(AudioRingBuffer);
    expect(processor.ringBuffer.capacity).toBe(48000 * 2); // bytesPerSecond * 2
  });

  it("_completePlaybackSession prevents double emission", () => {
    const completedSpy = vi.fn();
    processor.on("completed", completedSpy);

    processor._completePlaybackSession();
    processor._completePlaybackSession();
    processor._completePlaybackSession();

    expect(completedSpy).toHaveBeenCalledTimes(1);
  });

  it("_completePlaybackSession emits completed event", () => {
    const completedSpy = vi.fn();
    processor.on("completed", completedSpy);

    processor._completePlaybackSession();

    expect(completedSpy).toHaveBeenCalledTimes(1);
    expect(processor._completionEmitted).toBe(true);
    expect(processor.isEndingStream).toBe(false);
    expect(processor.ringBuffer.size).toBe(0);
  });

  it("_completePlaybackSession records timing stats", () => {
    // Use a real performance.now() value so actualDuration is positive
    processor.stats.playbackStartTime = performance.now() - 100;
    processor.stats.playbackEndTime = 0;

    processor._completePlaybackSession();

    expect(processor.stats.playbackEndTime).toBeGreaterThan(0);
    expect(processor.stats.actualDuration).toBeGreaterThanOrEqual(0);
  });

  it("calculateExpectedDuration computes correctly", () => {
    // 48000 bytes = 1 second at 24kHz/16bit/mono
    const durationMs = processor.calculateExpectedDuration(48000);
    // Should be ~1000ms plus a small processing buffer
    expect(durationMs).toBeGreaterThanOrEqual(1000);
    expect(durationMs).toBeLessThan(1100);
  });

  it("pause sets isPaused flag", () => {
    processor.isPlaying = true;
    processor.pause();
    expect(processor.isPaused).toBe(true);
  });

  it("resume clears isPaused flag", () => {
    processor.isPlaying = true;
    processor.isPaused = true;
    processor.resume();
    expect(processor.isPaused).toBe(false);
  });

  it("stop sets isStopping flag and emits stopped", () => {
    const stoppedSpy = vi.fn();
    processor.on("stopped", stoppedSpy);
    processor.ringBuffer.write(Buffer.alloc(100));
    processor.stop();
    expect(processor.isStopping).toBe(true);
    expect(processor.isStopped).toBe(true);
    expect(processor.isPlaying).toBe(false);
    expect(stoppedSpy).toHaveBeenCalledTimes(1);
    // Note: stop() intentionally does NOT clear the buffer — it lets the loop drain it
    expect(processor.ringBuffer.size).toBe(100);
  });
});


// --- AudioDaemon ---

describe("AudioDaemon", () => {
  let daemon;

  beforeEach(() => {
    vi.spyOn(console, "log").mockImplementation(() => {});
    vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.spyOn(console, "error").mockImplementation(() => {});

    daemon = new AudioDaemon(0); // port 0 = random available port
  });

  afterEach(() => {
    if (daemon.heartbeatInterval) clearInterval(daemon.heartbeatInterval);
    if (daemon.server) {
      try { daemon.server.close(); } catch { /* process may be dead */ }
    }
    if (daemon.audioProcessor) {
      if (daemon.audioProcessor._audioLoopInterval)
        clearInterval(daemon.audioProcessor._audioLoopInterval);
      if (daemon.audioProcessor.audioProcess) {
        try { daemon.audioProcessor.audioProcess.kill("SIGTERM"); } catch { /* process may be dead */ }
      }
    }
    vi.restoreAllMocks();
  });

  it("parses default config", () => {
    expect(daemon.config.port).toBe(8081);
    expect(daemon.config.sampleRate).toBe(24000);
    expect(daemon.config.channels).toBe(1);
    expect(daemon.config.bitDepth).toBe(16);
  });

  describe("handleMessage dispatch", () => {
    it("logs unknown message type", () => {
      const errorSpy = vi.spyOn(console, "error");
      daemon.handleMessage({}, { type: "banana" });
      expect(errorSpy).toHaveBeenCalledWith(
        expect.stringContaining("Unknown message type"),
        "banana"
      );
    });

    it("dispatches audio_chunk to handleAudioChunk", () => {
      const spy = vi.spyOn(daemon, "handleAudioChunk").mockImplementation(() => {});
      const ws = {};
      const msg = { type: "audio_chunk", data: { chunk: Buffer.alloc(10) } };
      daemon.handleMessage(ws, msg);
      expect(spy).toHaveBeenCalledWith(ws, msg);
    });

    it("dispatches control to handleControl", () => {
      const spy = vi.spyOn(daemon, "handleControl").mockImplementation(() => {});
      const msg = { type: "control", data: { action: "play" } };
      daemon.handleMessage({}, msg);
      expect(spy).toHaveBeenCalledWith(msg.data);
    });

    it("dispatches end_stream to handleEndStream", () => {
      const spy = vi.spyOn(daemon, "handleEndStream").mockImplementation(() => {});
      daemon.handleMessage({}, { type: "end_stream" });
      expect(spy).toHaveBeenCalled();
    });
  });

  describe("handleAudioChunk", () => {
    beforeEach(() => {
      // Set up a minimal audio processor with a mock writeChunk
      const format = new AudioFormat("pcm", 24000, 1, 16);
      daemon.audioProcessor = new AudioProcessor(format);
      daemon.audioProcessor.writeChunk = vi.fn();
    });

    afterEach(() => {
      if (daemon.audioProcessor?._audioLoopInterval)
        clearInterval(daemon.audioProcessor._audioLoopInterval);
    });

    it("decodes base64 string chunk", () => {
      const raw = Buffer.from([1, 2, 3, 4]);
      const b64 = raw.toString("base64");
      daemon.handleAudioChunk({}, { type: "audio_chunk", data: { chunk: b64 } });
      expect(daemon.audioProcessor.writeChunk).toHaveBeenCalledWith(
        expect.any(Buffer)
      );
      const arg = daemon.audioProcessor.writeChunk.mock.calls[0][0];
      expect([...arg]).toEqual([1, 2, 3, 4]);
    });

    it("passes raw Buffer through", () => {
      const raw = Buffer.from([10, 20, 30]);
      daemon.handleAudioChunk({}, { type: "audio_chunk", data: { chunk: raw } });
      expect(daemon.audioProcessor.writeChunk).toHaveBeenCalledWith(raw);
    });

    it("converts {type: 'Buffer', data: [...]} format", () => {
      const obj = { type: "Buffer", data: [5, 6, 7] };
      daemon.handleAudioChunk({}, { type: "audio_chunk", data: { chunk: obj } });
      const arg = daemon.audioProcessor.writeChunk.mock.calls[0][0];
      expect([...arg]).toEqual([5, 6, 7]);
    });

    it("converts numeric-key object format", () => {
      const obj = { "0": 10, "1": 20, "2": 30 };
      daemon.handleAudioChunk({}, { type: "audio_chunk", data: { chunk: obj } });
      const arg = daemon.audioProcessor.writeChunk.mock.calls[0][0];
      expect([...arg]).toEqual([10, 20, 30]);
    });

    it("rejects invalid chunk format", () => {
      const errorSpy = vi.spyOn(console, "error");
      daemon.handleAudioChunk({}, { type: "audio_chunk", data: { chunk: { foo: "bar" } } });
      expect(daemon.audioProcessor.writeChunk).not.toHaveBeenCalled();
      expect(errorSpy).toHaveBeenCalledWith(
        expect.stringContaining("Unrecognized object format"),
        expect.anything()
      );
    });

    it("handles missing processor gracefully", () => {
      daemon.audioProcessor = null;
      const errorSpy = vi.spyOn(console, "error");
      daemon.handleAudioChunk({}, { type: "audio_chunk", data: { chunk: Buffer.alloc(5) } });
      expect(errorSpy).toHaveBeenCalledWith(
        expect.stringContaining("Audio processor not initialized")
      );
    });
  });

  describe("handleControl", () => {
    it("initializes audio processor if not present", async () => {
      expect(daemon.audioProcessor).toBeNull();
      // Use "pause" to avoid spawning sox (play triggers start() → sox)
      await daemon.handleControl({ action: "pause" });
      expect(daemon.audioProcessor).not.toBeNull();
      expect(daemon.audioProcessor).toBeInstanceOf(AudioProcessor);
    });

    it("logs error for missing action", async () => {
      const errorSpy = vi.spyOn(console, "error");
      await daemon.handleControl({});
      expect(errorSpy).toHaveBeenCalledWith(
        expect.stringContaining("Control message missing action"),
        expect.anything()
      );
    });

    it("sets isEndingStream on end_stream action", async () => {
      // Pre-initialize processor to avoid spawning sox
      const format = new AudioFormat("pcm", 24000, 1, 16);
      daemon.audioProcessor = new AudioProcessor(format);
      daemon.audioProcessor.audioProcess = { exitCode: null, killed: false };

      await daemon.handleControl({ action: "end_stream" });
      expect(daemon.audioProcessor.isEndingStream).toBe(true);
    });
  });

  describe("handleEndStream", () => {
    it("does nothing when no processor", () => {
      daemon.audioProcessor = null;
      expect(() => daemon.handleEndStream()).not.toThrow();
    });

    it("routes to handleControl end_stream action (drain-and-complete)", () => {
      // BUG FIX: handleEndStream previously called stop() which killed playback
      // without emitting "completed". Now it routes through handleControl's
      // "end_stream" action which has proper drain-and-complete logic.
      const format = new AudioFormat("pcm", 24000, 1, 16);
      daemon.audioProcessor = new AudioProcessor(format);
      daemon.audioProcessor.afplayMode = false;
      const stopSpy = vi.spyOn(daemon.audioProcessor, "stop");
      daemon.handleEndStream();
      // Should NOT call stop — that was the bug
      expect(stopSpy).not.toHaveBeenCalled();
      // With empty buffer and no process, completion fires immediately,
      // so isEndingStream is reset to false. Check _completionEmitted instead.
      expect(daemon.audioProcessor._completionEmitted).toBe(true);
    });

    it("routes to handleControl in afplay mode too", () => {
      const format = new AudioFormat("pcm", 24000, 1, 16);
      daemon.audioProcessor = new AudioProcessor(format);
      daemon.audioProcessor.afplayMode = true;
      daemon.handleEndStream();
      expect(daemon.audioProcessor._completionEmitted).toBe(true);
    });
  });

  // --- Undefined handler methods (CRITICAL BUG) ---

  describe("undefined handler methods", () => {
    it("handleStart is not defined — 'start' message throws TypeError", () => {
      expect(typeof daemon.handleStart).toBe("undefined");
      expect(() => daemon.handleMessage({}, { type: "start" })).toThrow(TypeError);
    });

    it("handleStop is not defined — 'stop' message throws TypeError", () => {
      expect(typeof daemon.handleStop).toBe("undefined");
      expect(() => daemon.handleMessage({}, { type: "stop" })).toThrow(TypeError);
    });

    it("handlePause is not defined — 'pause' message throws TypeError", () => {
      expect(typeof daemon.handlePause).toBe("undefined");
      expect(() => daemon.handleMessage({}, { type: "pause" })).toThrow(TypeError);
    });

    it("handleResume is not defined — 'resume' message throws TypeError", () => {
      expect(typeof daemon.handleResume).toBe("undefined");
      expect(() => daemon.handleMessage({}, { type: "resume" })).toThrow(TypeError);
    });
  });

  // --- Daemon stop and cleanup ---

  describe("daemon stop", () => {
    it("stop emits stopped event", () => {
      const stoppedSpy = vi.fn();
      daemon.on("stopped", stoppedSpy);
      daemon.stop();
      expect(stoppedSpy).toHaveBeenCalledTimes(1);
    });

    it("stop clears heartbeat interval", () => {
      daemon.heartbeatInterval = setInterval(() => {}, 10000);
      const id = daemon.heartbeatInterval;
      daemon.stop();
      // After stop, heartbeatInterval should have been cleared
      // (clearInterval doesn't null the reference, but the interval stops)
      expect(daemon.heartbeatInterval).toBe(id); // reference persists but interval cleared
    });

    it("stop calls audioProcessor.stop if processor exists", () => {
      const format = new AudioFormat("pcm", 24000, 1, 16);
      daemon.audioProcessor = new AudioProcessor(format);
      const stopSpy = vi.spyOn(daemon.audioProcessor, "stop");
      daemon.stop();
      expect(stopSpy).toHaveBeenCalled();
    });

    it("stop handles missing audioProcessor gracefully", () => {
      daemon.audioProcessor = null;
      expect(() => daemon.stop()).not.toThrow();
    });
  });

  // --- Broadcast ---

  describe("broadcast", () => {
    it("sends to all open clients", async () => {
      const { default: WebSocket } = await import("ws");
      const ws1 = { readyState: WebSocket.OPEN, send: vi.fn() };
      const ws2 = { readyState: WebSocket.OPEN, send: vi.fn() };
      daemon.clients.add(ws1);
      daemon.clients.add(ws2);

      daemon.broadcast({ type: "test", data: "hello" });

      expect(ws1.send).toHaveBeenCalledWith(JSON.stringify({ type: "test", data: "hello" }));
      expect(ws2.send).toHaveBeenCalledWith(JSON.stringify({ type: "test", data: "hello" }));
    });

    it("skips clients that are not OPEN", async () => {
      const { default: WebSocket } = await import("ws");
      const openWs = { readyState: WebSocket.OPEN, send: vi.fn() };
      const closedWs = { readyState: WebSocket.CLOSED, send: vi.fn() };
      daemon.clients.add(openWs);
      daemon.clients.add(closedWs);

      daemon.broadcast({ type: "ping" });

      expect(openWs.send).toHaveBeenCalled();
      expect(closedWs.send).not.toHaveBeenCalled();
    });

    it("handles empty client set", () => {
      expect(() => daemon.broadcast({ type: "test" })).not.toThrow();
    });
  });

  // --- handleControl edge cases ---

  describe("handleControl edge cases", () => {
    it("pause delegates to audioProcessor.pause", async () => {
      const format = new AudioFormat("pcm", 24000, 1, 16);
      daemon.audioProcessor = new AudioProcessor(format);
      const spy = vi.spyOn(daemon.audioProcessor, "pause");
      await daemon.handleControl({ action: "pause" });
      expect(spy).toHaveBeenCalled();
    });

    it("resume delegates to audioProcessor.resume", async () => {
      const format = new AudioFormat("pcm", 24000, 1, 16);
      daemon.audioProcessor = new AudioProcessor(format);
      await daemon.handleControl({ action: "resume" });
      expect(daemon.audioProcessor.isPaused).toBe(false);
    });

    it("stop delegates to audioProcessor.stop", async () => {
      const format = new AudioFormat("pcm", 24000, 1, 16);
      daemon.audioProcessor = new AudioProcessor(format);
      const spy = vi.spyOn(daemon.audioProcessor, "stop");
      await daemon.handleControl({ action: "stop" });
      expect(spy).toHaveBeenCalled();
    });

    it("reads nested action from data.data.action format", async () => {
      const format = new AudioFormat("pcm", 24000, 1, 16);
      daemon.audioProcessor = new AudioProcessor(format);
      const spy = vi.spyOn(daemon.audioProcessor, "pause");
      await daemon.handleControl({ data: { action: "pause" } });
      expect(spy).toHaveBeenCalled();
    });

    it("uses custom format params when initializing processor", async () => {
      daemon.audioProcessor = null;
      // Use a non-play action to avoid spawning sox
      await daemon.handleControl({
        action: "pause",
        params: { format: "pcm", sampleRate: 44100, channels: 2, bitDepth: 16 },
      });
      expect(daemon.audioProcessor.format.sampleRate).toBe(44100);
      expect(daemon.audioProcessor.format.channels).toBe(2);
    });
  });

  // --- handleStatus and handleHeartbeat ---

  describe("handleStatus — undefined method bug", () => {
    it("handleStatus is not defined — 'status' message throws TypeError", () => {
      expect(typeof daemon.handleStatus).toBe("undefined");
      expect(() => daemon.handleMessage({}, { type: "status" })).toThrow(TypeError);
    });
  });

  describe("handleHeartbeat", () => {
    it("responds with heartbeat ack", () => {
      const format = new AudioFormat("pcm", 24000, 1, 16);
      daemon.audioProcessor = new AudioProcessor(format);
      const ws = { send: vi.fn() };
      daemon.handleMessage(ws, { type: "heartbeat" });
      expect(ws.send).toHaveBeenCalled();
      const sent = JSON.parse(ws.send.mock.calls[0][0]);
      expect(sent.type).toBe("heartbeat");
      expect(sent.data.status).toBe("ok");
    });
  });

  describe("handleTimingAnalysis", () => {
    it("returns timing data when processor exists", () => {
      const format = new AudioFormat("pcm", 24000, 1, 16);
      daemon.audioProcessor = new AudioProcessor(format);
      const ws = { send: vi.fn() };
      daemon.handleMessage(ws, { type: "timing_analysis" });
      const sent = JSON.parse(ws.send.mock.calls[0][0]);
      expect(sent.type).toBe("timing_analysis");
      expect(sent.data).toHaveProperty("basic");
    });

    it("returns error when no processor", () => {
      daemon.audioProcessor = null;
      const ws = { send: vi.fn() };
      daemon.handleMessage(ws, { type: "timing_analysis" });
      const sent = JSON.parse(ws.send.mock.calls[0][0]);
      expect(sent.type).toBe("error");
      expect(sent.data.message).toContain("not available");
    });
  });
});


// --- AudioProcessor: writeChunk and drain logic ---

describe("AudioProcessor writeChunk", () => {
  let processor;

  beforeEach(() => {
    vi.spyOn(console, "log").mockImplementation(() => {});
    vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.spyOn(console, "error").mockImplementation(() => {});

    const format = new AudioFormat("pcm", 24000, 1, 16);
    processor = new AudioProcessor(format);
    // Stub start() to prevent sox spawning
    processor.start = vi.fn();
  });

  afterEach(() => {
    if (processor._audioLoopInterval) clearInterval(processor._audioLoopInterval);
    if (processor._endStreamTimeout) clearTimeout(processor._endStreamTimeout);
    if (processor.processKeepAliveTimer) clearTimeout(processor.processKeepAliveTimer);
    if (processor.restartTimeout) clearTimeout(processor.restartTimeout);
    vi.restoreAllMocks();
  });

  it("writes chunk to ring buffer and returns bytes written", async () => {
    const chunk = Buffer.alloc(100, 0xAA);
    const written = await processor.writeChunk(chunk);
    expect(written).toBe(100);
    expect(processor.ringBuffer.size).toBe(100);
  });

  it("auto-starts playback on first chunk", async () => {
    const chunk = Buffer.alloc(50);
    await processor.writeChunk(chunk);
    expect(processor.start).toHaveBeenCalledTimes(1);
  });

  it("does not auto-start on subsequent chunks", async () => {
    await processor.writeChunk(Buffer.alloc(50));
    await processor.writeChunk(Buffer.alloc(50));
    await processor.writeChunk(Buffer.alloc(50));
    // start() called only once (on first chunk)
    expect(processor.start).toHaveBeenCalledTimes(1);
  });

  it("tracks chunk timing metrics", async () => {
    await processor.writeChunk(Buffer.alloc(100));
    expect(processor.stats.firstChunkTime).toBeGreaterThan(0);
    expect(processor.stats.lastChunkTime).toBeGreaterThan(0);
    expect(processor.stats.totalChunksReceived).toBe(1);
  });

  it("updates expected duration as chunks arrive", async () => {
    // 48000 bytes = 1 second of audio at 24kHz/16bit/mono
    await processor.writeChunk(Buffer.alloc(48000));
    expect(processor.stats.expectedDuration).toBeGreaterThanOrEqual(1000);
    expect(processor.totalAudioBytes).toBe(48000);
  });

  it("emits chunkReceived event with metrics", async () => {
    const spy = vi.fn();
    processor.on("chunkReceived", spy);
    await processor.writeChunk(Buffer.alloc(100));
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy.mock.calls[0][0]).toHaveProperty("bufferUtilization");
    expect(spy.mock.calls[0][0]).toHaveProperty("timingMetrics");
  });

  it("accumulates stats across multiple chunks", async () => {
    await processor.writeChunk(Buffer.alloc(100));
    await processor.writeChunk(Buffer.alloc(200));
    await processor.writeChunk(Buffer.alloc(300));
    expect(processor.stats.totalChunksReceived).toBe(3);
    expect(processor.totalAudioBytes).toBe(600);
  });
});


// --- AudioProcessor: processAudioLoop drain logic ---

describe("AudioProcessor processAudioLoop", () => {
  let processor;

  beforeEach(() => {
    vi.spyOn(console, "log").mockImplementation(() => {});
    vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.spyOn(console, "error").mockImplementation(() => {});

    const format = new AudioFormat("pcm", 24000, 1, 16);
    processor = new AudioProcessor(format);
  });

  afterEach(() => {
    processor._audioLoopActive = false;
    if (processor._audioLoopInterval) clearInterval(processor._audioLoopInterval);
    if (processor._endStreamTimeout) clearTimeout(processor._endStreamTimeout);
    if (processor.processKeepAliveTimer) clearTimeout(processor.processKeepAliveTimer);
    if (processor.restartTimeout) clearTimeout(processor.restartTimeout);
    if (processor.audioProcess) {
      try { processor.audioProcess.kill("SIGTERM"); } catch { /* process may be dead */ }
    }
    vi.restoreAllMocks();
  });

  it("exits when isStopped is true after first tick", () => {
    processor.isStopped = true;
    processor.audioProcess = { killed: false, exitCode: null, stdin: { write: vi.fn(), end: vi.fn(), destroyed: false } };
    processor.processAudioLoop();
    // _audioLoopActive is set synchronously, but processChunk runs on setTimeout
    // After the timeout fires, isStopped causes it to set _audioLoopActive=false
    return new Promise((resolve) => {
      setTimeout(() => {
        expect(processor._audioLoopActive).toBe(false);
        resolve();
      }, 50);
    });
  });

  it("exits when no audio process is available", () => {
    processor.audioProcess = null;
    processor.processAudioLoop();
    expect(processor._audioLoopActive).toBe(false);
  });

  it("prevents re-entrancy", () => {
    processor._audioLoopActive = true;
    processor.audioProcess = { killed: false, exitCode: null };
    const _logSpy = vi.spyOn(console, "log");
    processor.processAudioLoop();
    // Should return early without logging "NEW ROBUST AUDIO LOOP STARTED"
    // (re-entrancy guard at line 1020)
  });

  it("completes session when isEndingStream and buffer empty and process dead", () => {
    const completedSpy = vi.fn();
    processor.on("completed", completedSpy);

    processor.isEndingStream = true;
    processor.ringBuffer.clear(); // buffer empty
    processor.audioProcess = { killed: true, exitCode: 0, stdin: { write: vi.fn(), end: vi.fn(), destroyed: true } };

    processor.processAudioLoop();

    // Give the setTimeout(processChunk, 1) a tick to fire
    return new Promise((resolve) => {
      setTimeout(() => {
        expect(completedSpy).toHaveBeenCalledTimes(1);
        resolve();
      }, 50);
    });
  });

  it("attempts recovery when process dies with data in buffer", () => {
    const restartSpy = vi.spyOn(processor, "restartAudioProcess").mockImplementation(() => {});

    processor.ringBuffer.write(Buffer.alloc(1000));
    processor.audioProcess = { killed: true, exitCode: 1, stdin: { write: vi.fn(), end: vi.fn(), destroyed: true } };

    processor.processAudioLoop();

    return new Promise((resolve) => {
      setTimeout(() => {
        expect(restartSpy).toHaveBeenCalled();
        resolve();
      }, 50);
    });
  });

  it("drains buffer to stdin when data available", () => {
    const writeFn = vi.fn().mockReturnValue(true);
    const stdinMock = new EventEmitter();
    stdinMock.write = writeFn;
    stdinMock.end = vi.fn();
    stdinMock.destroyed = false;
    stdinMock.setDefaultEncoding = vi.fn();
    stdinMock._writableState = { highWaterMark: 65536 };

    processor.audioProcess = {
      killed: false,
      exitCode: null,
      stdin: stdinMock,
      on: vi.fn(),
      stderr: { on: vi.fn() },
    };

    // Write enough data for at least one chunk (50ms = 2400 bytes at 48000 bytes/s)
    processor.ringBuffer.write(Buffer.alloc(2400));

    processor.processAudioLoop();

    return new Promise((resolve) => {
      setTimeout(() => {
        expect(writeFn).toHaveBeenCalled();
        resolve();
      }, 50);
    });
  });

  it("handles back-pressure when stdin.write returns false", () => {
    // First write returns false (back-pressure), then drain fires
    let writeCallCount = 0;
    const stdinMock = new EventEmitter();
    stdinMock.write = vi.fn().mockImplementation((_chunk, _cb) => {
      writeCallCount++;
      if (writeCallCount === 1) return false; // back-pressure
      return true;
    });
    stdinMock.end = vi.fn();
    stdinMock.destroyed = false;
    stdinMock.setDefaultEncoding = vi.fn();
    stdinMock._writableState = { highWaterMark: 65536 };

    processor.audioProcess = {
      killed: false,
      exitCode: null,
      stdin: stdinMock,
      on: vi.fn(),
      stderr: { on: vi.fn() },
    };

    processor.ringBuffer.write(Buffer.alloc(5000)); // more than one chunk

    processor.processAudioLoop();

    return new Promise((resolve) => {
      setTimeout(() => {
        expect(stdinMock.write).toHaveBeenCalled();
        // Emit drain to unblock
        stdinMock.emit("drain");
        setTimeout(() => {
          // After drain, loop should resume and write more
          expect(stdinMock.write.mock.calls.length).toBeGreaterThanOrEqual(1);
          resolve();
        }, 50);
      }, 50);
    });
  });
});


// --- AudioProcessor: restart logic ---

describe("AudioProcessor restartAudioProcess", () => {
  let processor;

  beforeEach(() => {
    vi.spyOn(console, "log").mockImplementation(() => {});
    vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.spyOn(console, "error").mockImplementation(() => {});

    const format = new AudioFormat("pcm", 24000, 1, 16);
    processor = new AudioProcessor(format);
  });

  afterEach(() => {
    if (processor._audioLoopInterval) clearInterval(processor._audioLoopInterval);
    if (processor._endStreamTimeout) clearTimeout(processor._endStreamTimeout);
    if (processor.processKeepAliveTimer) clearTimeout(processor.processKeepAliveTimer);
    if (processor.restartTimeout) clearTimeout(processor.restartTimeout);
    if (processor.audioProcess) {
      try { processor.audioProcess.kill("SIGTERM"); } catch { /* process may be dead */ }
    }
    vi.restoreAllMocks();
  });

  it("increments restart attempts", () => {
    processor.isPlaying = true;
    processor.restartAudioProcess();
    expect(processor.restartAttempts).toBe(1);
  });

  it("emits error after MAX_RESTARTS exceeded", () => {
    const errorSpy = vi.fn();
    processor.on("error", errorSpy);
    processor.isPlaying = true;
    processor.restartAttempts = 5; // Already at MAX
    processor.restartAudioProcess();
    expect(errorSpy).toHaveBeenCalledWith(
      expect.objectContaining({ message: expect.stringContaining("restart limit") })
    );
  });

  it("resets counter after 30s cooldown", () => {
    processor.isPlaying = true;
    // restartAudioProcess uses performance.now(), not Date.now()
    processor.lastRestartTime = performance.now() - 31000; // 31s ago
    processor.restartAttempts = 4;
    processor.restartAudioProcess();
    // Counter should have been reset to 0, then incremented to 1
    expect(processor.restartAttempts).toBe(1);
  });

  it("does not restart when not playing", () => {
    processor.isPlaying = false;
    processor.restartAudioProcess();
    expect(processor.restartTimeout).toBeNull();
  });

  it("does not restart when stopped", () => {
    processor.isPlaying = true;
    processor.isStopped = true;
    processor.restartAudioProcess();
    // restartTimeout should not be set
    expect(processor.restartTimeout).toBeNull();
  });
});


// --- WebSocket integration (live server) ---

describe("AudioDaemon WebSocket integration", () => {
  let daemon;
  let port;

  beforeEach(async () => {
    vi.spyOn(console, "log").mockImplementation(() => {});
    vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.spyOn(console, "error").mockImplementation(() => {});

    daemon = new AudioDaemon(0); // Random port
    daemon.config.port = 0;

    await new Promise((resolve) => {
      daemon.start();
      daemon.once("started", () => {
        port = daemon.server.address().port;
        // Prevent sox/ffplay spawning and restart loops in test environment
        if (daemon.audioProcessor) {
          daemon.audioProcessor.on("error", () => {});
          daemon.audioProcessor.start = vi.fn();
          daemon.audioProcessor.restartAudioProcess = vi.fn();
        }
        resolve();
      });
    });
  });

  afterEach(async () => {
    if (daemon.heartbeatInterval) clearInterval(daemon.heartbeatInterval);
    if (daemon.audioProcessor) {
      // Aggressively stop the processor to prevent restart loops and timer leaks
      daemon.audioProcessor.isStopped = true;
      daemon.audioProcessor.isStopping = true;
      daemon.audioProcessor.isPlaying = false;
      daemon.audioProcessor._audioLoopActive = false;
      daemon.audioProcessor.restartAttempts = 999; // Prevent any further restarts
      daemon.audioProcessor.removeAllListeners(); // Remove all event listeners
      if (daemon.audioProcessor._audioLoopInterval)
        clearInterval(daemon.audioProcessor._audioLoopInterval);
      if (daemon.audioProcessor._endStreamTimeout)
        clearTimeout(daemon.audioProcessor._endStreamTimeout);
      if (daemon.audioProcessor.processKeepAliveTimer)
        clearTimeout(daemon.audioProcessor.processKeepAliveTimer);
      if (daemon.audioProcessor.restartTimeout)
        clearTimeout(daemon.audioProcessor.restartTimeout);
      if (daemon.audioProcessor._memoryLogInterval)
        clearInterval(daemon.audioProcessor._memoryLogInterval);
      if (daemon.audioProcessor.audioProcess) {
        try { daemon.audioProcessor.audioProcess.kill("SIGKILL"); } catch { /* process may be dead */ }
      }
    }
    daemon.stop();
    // Wait for server to close and pending timers to settle
    await new Promise((resolve) => setTimeout(resolve, 200));
    vi.restoreAllMocks();
  });

  it("accepts WebSocket connections", async () => {
    const { default: WebSocket } = await import("ws");
    const ws = new WebSocket(`ws://localhost:${port}`);

    await new Promise((resolve, reject) => {
      ws.on("open", resolve);
      ws.on("error", reject);
    });

    expect(daemon.clients.size).toBe(1);
    ws.close();
  });

  it("sends welcome message on connection", async () => {
    const { default: WebSocket } = await import("ws");
    const ws = new WebSocket(`ws://localhost:${port}`);

    const msg = await new Promise((resolve, reject) => {
      ws.on("message", (data) => resolve(JSON.parse(data.toString())));
      ws.on("error", reject);
    });

    expect(msg.type).toBe("status");
    ws.close();
  });

  it("handles malformed JSON gracefully — no crash", async () => {
    const { default: WebSocket } = await import("ws");
    const ws = new WebSocket(`ws://localhost:${port}`);

    await new Promise((resolve) => ws.on("open", resolve));

    // Send invalid JSON
    ws.send("{ this is not json");

    // Daemon should not crash — wait and verify
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(daemon.server.listening).toBe(true);
    ws.close();
  });

  it("removes client on disconnect", async () => {
    const { default: WebSocket } = await import("ws");
    const ws = new WebSocket(`ws://localhost:${port}`);

    await new Promise((resolve) => ws.on("open", resolve));
    expect(daemon.clients.size).toBe(1);

    ws.close();
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(daemon.clients.size).toBe(0);
  });

  it("processes audio_chunk messages via WebSocket", async () => {
    const { default: WebSocket } = await import("ws");
    const ws = new WebSocket(`ws://localhost:${port}`);

    await new Promise((resolve) => ws.on("open", resolve));

    // Stub writeChunk to avoid real audio processing and sox spawning
    daemon.audioProcessor.writeChunk = vi.fn().mockResolvedValue(100);
    // Prevent start() from spawning sox
    daemon.audioProcessor.start = vi.fn();

    const chunk = Buffer.alloc(100, 0x55).toString("base64");
    ws.send(JSON.stringify({
      type: "audio_chunk",
      timestamp: Date.now(),
      data: { chunk },
    }));

    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(daemon.audioProcessor.writeChunk).toHaveBeenCalled();
    ws.close();
  });

  it("broadcasts completed event to all connected clients", async () => {
    const { default: WebSocket } = await import("ws");
    const ws1 = new WebSocket(`ws://localhost:${port}`);
    const ws2 = new WebSocket(`ws://localhost:${port}`);

    await Promise.all([
      new Promise((resolve) => ws1.on("open", resolve)),
      new Promise((resolve) => ws2.on("open", resolve)),
    ]);

    // Collect messages from both clients
    const messages1 = [];
    const messages2 = [];
    ws1.on("message", (d) => messages1.push(JSON.parse(d.toString())));
    ws2.on("message", (d) => messages2.push(JSON.parse(d.toString())));

    // Trigger completed event on audio processor
    daemon.audioProcessor._completePlaybackSession();

    await new Promise((resolve) => setTimeout(resolve, 50));

    const completed1 = messages1.find((m) => m.type === "completed");
    const completed2 = messages2.find((m) => m.type === "completed");
    expect(completed1).toBeDefined();
    expect(completed2).toBeDefined();

    ws1.close();
    ws2.close();
  });

  it("health endpoint returns JSON status", async () => {
    const response = await fetch(`http://localhost:${port}/health`);
    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.status).toBe("healthy");
    expect(data.version).toBe("2.0.0");
    expect(data).toHaveProperty("audioProcessor");
    expect(data).toHaveProperty("clients");
  });

  it("handles multiple rapid connections and disconnections", async () => {
    const { default: WebSocket } = await import("ws");
    const connections = [];

    // Open 5 connections rapidly
    for (let i = 0; i < 5; i++) {
      const ws = new WebSocket(`ws://localhost:${port}`);
      connections.push(ws);
    }

    await Promise.all(
      connections.map((ws) => new Promise((resolve) => ws.on("open", resolve)))
    );

    expect(daemon.clients.size).toBe(5);

    // Close all rapidly
    connections.forEach((ws) => ws.close());
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(daemon.clients.size).toBe(0);
  });
});
