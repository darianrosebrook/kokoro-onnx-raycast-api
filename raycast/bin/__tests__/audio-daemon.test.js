/**
 * Tests for raycast/bin/audio-daemon.js
 *
 * First-ever test coverage for the audio daemon — ring buffer, audio format,
 * audio processor lifecycle, chunk handling, and message dispatch.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { AudioRingBuffer, AudioFormat, AudioProcessor, AudioDaemon } from "../audio-daemon.js";

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
      try { processor.audioProcess.kill("SIGTERM"); } catch (_) {}
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
      try { daemon.server.close(); } catch (_) {}
    }
    if (daemon.audioProcessor) {
      if (daemon.audioProcessor._audioLoopInterval)
        clearInterval(daemon.audioProcessor._audioLoopInterval);
      if (daemon.audioProcessor.audioProcess) {
        try { daemon.audioProcessor.audioProcess.kill("SIGTERM"); } catch (_) {}
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
      // Stub start to avoid spawning sox
      const startSpy = vi.fn();
      await daemon.handleControl({ action: "play" });
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

    it("calls stop on non-afplay processor", () => {
      const format = new AudioFormat("pcm", 24000, 1, 16);
      daemon.audioProcessor = new AudioProcessor(format);
      daemon.audioProcessor.afplayMode = false;
      const stopSpy = vi.spyOn(daemon.audioProcessor, "stop");
      daemon.handleEndStream();
      expect(stopSpy).toHaveBeenCalled();
    });
  });
});
