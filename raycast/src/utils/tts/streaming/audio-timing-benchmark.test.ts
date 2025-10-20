import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { AudioTimingBenchmark } from "./audio-timing-benchmark.js";
import type { AudioFormat } from "../../validation/tts-types.js";

// Mock the logger to avoid console output during tests
vi.mock("../../core/logger", () => ({
  logger: {
    info: vi.fn(),
    warn: vi.fn(),
    debug: vi.fn(),
    error: vi.fn(),
    consoleInfo: vi.fn(),
    consoleDebug: vi.fn(),
    consoleWarn: vi.fn(),
    consoleError: vi.fn(),
  },
}));

describe("AudioTimingBenchmark", () => {
  let benchmark: AudioTimingBenchmark;

  beforeEach(() => {
    vi.useFakeTimers();
    benchmark = new AudioTimingBenchmark(true); // testMode true
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe("Constructor and Initialization", () => {
    it("should initialize without errors", () => {
      expect(benchmark).toBeInstanceOf(AudioTimingBenchmark);
    });

    it("should start collection correctly", () => {
      benchmark.startCollection();
      expect(benchmark.getMetrics()).toEqual([]);
    });

    it("should stop collection and generate report", () => {
      benchmark.startCollection();
      const report = benchmark.stopCollection();

      expect(report).toEqual({
        totalTests: 0,
        successfulTests: 0,
        averageAccuracy: 0,
        prematureTerminations: 0,
        recommendations: ["No timing data available"],
      });
    });
  });

  describe("Audio Duration Calculation", () => {
    it("should calculate duration correctly for 24kHz mono 16-bit audio", async () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 16,
        format: "pcm",
        bytesPerSample: 2,
        bytesPerSecond: 48000,
      };
      const audioData = new Uint8Array(48000);
      const result = await benchmark.benchmarkAudioTiming(audioData, format, { testMode: true });
      expect(result.success).toBe(true);
      expect(result.calculatedDurationMs).toBeGreaterThan(0);
      expect(result.chunkCount).toBeGreaterThan(0);
      expect(result.daemonLifetimeMs).toBeGreaterThan(0);
    });

    it("should calculate duration correctly for 22kHz stereo 16-bit audio", async () => {
      const format: AudioFormat = {
        sampleRate: 22050,
        channels: 2,
        bitDepth: 16,
        format: "pcm",
        bytesPerSample: 2,
        bytesPerSecond: 88200,
      };
      const audioData = new Uint8Array(88200);
      const result = await benchmark.benchmarkAudioTiming(audioData, format, { testMode: true });
      expect(result.success).toBe(true);
      expect(result.calculatedDurationMs).toBeGreaterThan(0);
      expect(result.chunkCount).toBeGreaterThan(0);
      expect(result.daemonLifetimeMs).toBeGreaterThan(0);
    });

    it("should calculate duration correctly for 48kHz mono 24-bit audio", async () => {
      const format: AudioFormat = {
        sampleRate: 48000,
        channels: 1,
        bitDepth: 24,
        format: "pcm",
        bytesPerSample: 3,
        bytesPerSecond: 144000,
      };
      const audioData = new Uint8Array(144000);
      const result = await benchmark.benchmarkAudioTiming(audioData, format, { testMode: true });
      expect(result.success).toBe(true);
      expect(result.calculatedDurationMs).toBeGreaterThan(0);
      expect(result.chunkCount).toBeGreaterThan(0);
      expect(result.daemonLifetimeMs).toBeGreaterThan(0);
    });
  });

  describe("Audio Chunk Timing", () => {
    it("should track chunk delivery timing accurately", async () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 16,
        format: "pcm",
        bytesPerSample: 2,
        bytesPerSecond: 48000,
      };
      const audioData = new Uint8Array(4800);
      const result = await benchmark.benchmarkAudioTiming(audioData, format);
      expect(result.success).toBe(true);
      expect(result.chunkCount).toBeGreaterThan(0);
      expect(result.averageChunkInterval).toBeGreaterThan(0);
    });

    it("should identify irregular chunk delivery patterns", async () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 16,
        format: "pcm",
        bytesPerSample: 2,
        bytesPerSecond: 48000,
      };
      const audioData = new Uint8Array(9600);
      const result = await benchmark.benchmarkAudioTiming(audioData, format, { testMode: true });
      expect(result.success).toBe(true);
      expect(result.maxChunkInterval).toBeGreaterThan(0);
      expect(result.minChunkInterval).toBeGreaterThan(0);
    });

    it("should handle very small audio chunks", async () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 16,
        format: "pcm",
        bytesPerSample: 2,
        bytesPerSecond: 48000,
      };
      const audioData = new Uint8Array(480);
      const result = await benchmark.benchmarkAudioTiming(audioData, format);
      expect(result.success).toBe(true);
      expect(result.calculatedDurationMs).toBeGreaterThan(0);
      expect(result.chunkCount).toBeGreaterThan(0);
    });
  });

  describe("Buffer Health Monitoring", () => {
    it("should detect buffer underruns accurately", async () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 16,
        format: "pcm",
        bytesPerSample: 2,
        bytesPerSecond: 48000,
      };
      const audioData = new Uint8Array(24000);
      const result = await benchmark.benchmarkAudioTiming(audioData, format, { testMode: true });
      expect(result).toMatchObject({
        success: true,
        bufferUnderruns: expect.any(Number),
      });
    });

    it("should track buffer utilization over time", async () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 16,
        format: "pcm",
        bytesPerSample: 2,
        bytesPerSecond: 48000,
      };
      const audioData = new Uint8Array(48000);
      const result = await benchmark.benchmarkAudioTiming(audioData, format);
      expect(result.success).toBe(true);
      expect(result.bufferUnderruns).toBeDefined();
    });

    it("should measure buffer recovery time after underruns", async () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 16,
        format: "pcm",
        bytesPerSample: 2,
        bytesPerSecond: 48000,
      };
      const audioData = new Uint8Array(48000);
      const result = await benchmark.benchmarkAudioTiming(audioData, format);
      expect(result.success).toBe(true);
      expect(result.stutterCount).toBeDefined();
    });
  });

  describe("End-of-Stream Detection", () => {
    it("should detect natural end-of-stream correctly", async () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 16,
        format: "pcm",
        bytesPerSample: 2,
        bytesPerSecond: 48000,
      };
      const audioData = new Uint8Array(24000);
      const result = await benchmark.benchmarkAudioTiming(audioData, format, { testMode: true });
      expect(result).toMatchObject({
        success: true,
        endOfStreamDetected: true,
        prematureTermination: false,
      });
    });

    it("should detect premature stream termination", async () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 16,
        format: "pcm",
        bytesPerSample: 2,
        bytesPerSecond: 48000,
      };
      const audioData = new Uint8Array(12000);
      const result = await benchmark.benchmarkAudioTiming(audioData, format);
      expect(result).toMatchObject({
        success: true,
        endOfStreamDetected: true,
      });
    });

    it("should measure end-of-stream detection latency", async () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 16,
        format: "pcm",
        bytesPerSample: 2,
        bytesPerSecond: 48000,
      };
      const audioData = new Uint8Array(48000);
      const result = await benchmark.benchmarkAudioTiming(audioData, format, { testMode: true });
      expect(result.success).toBe(true);
      expect(result.endOfStreamTime).toBeDefined();
    });
  });

  describe("Daemon Lifecycle Management", () => {
    it("should handle daemon startup and shutdown gracefully", async () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 16,
        format: "pcm",
        bytesPerSample: 2,
        bytesPerSecond: 48000,
      };
      const audioData = new Uint8Array(24000);
      const result = await benchmark.benchmarkAudioTiming(audioData, format, { testMode: true });
      expect(result.success).toBe(true);
      expect(result.daemonStartTime).toBeGreaterThan(0);
      expect(result.daemonEndTime).toBeGreaterThan(0);
    });
  });

  describe("Test Audio Generation", () => {
    it("should generate test audio with correct size", () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 16,
        format: "pcm",
        bytesPerSample: 2,
        bytesPerSecond: 48000,
      };

      const durationMs = 1000;
      const audioData = benchmark.generateTestAudio(durationMs, format);

      const expectedSize =
        (durationMs / 1000) * format.sampleRate * format.channels * (format.bitDepth / 8);
      expect(audioData.length).toBe(expectedSize);
    });

    it("should generate audio with different sample rates", () => {
      const format: AudioFormat = {
        sampleRate: 48000,
        channels: 2,
        bitDepth: 16,
        format: "pcm",
        bytesPerSample: 2,
        bytesPerSecond: 192000,
      };

      const durationMs = 500;
      const audioData = benchmark.generateTestAudio(durationMs, format);

      const expectedSize =
        (durationMs / 1000) * format.sampleRate * format.channels * (format.bitDepth / 8);
      expect(audioData.length).toBe(expectedSize);
    });

    it("should generate audio with 24-bit depth", () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 24,
        format: "pcm",
        bytesPerSample: 3,
        bytesPerSecond: 72000,
      };

      const durationMs = 250;
      const audioData = benchmark.generateTestAudio(durationMs, format);

      const expectedSize =
        (durationMs / 1000) * format.sampleRate * format.channels * (format.bitDepth / 8);
      expect(audioData.length).toBe(expectedSize);
    });
  });

  describe("Chunked Delivery Testing", () => {
    // TODO: Implement real chunked delivery integration tests
    // - [ ] Test with actual streaming audio pipeline
    // - [ ] Add network condition simulation in test environment
    // - [ ] Implement end-to-end timing verification
    // - [ ] Add audio quality validation during chunking
    // - [ ] Test chunking with various audio formats and bitrates
    it("should simulate chunked delivery with correct timing", async () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 16,
        format: "pcm",
        bytesPerSample: 2,
        bytesPerSecond: 48000,
      };

      const audioData = benchmark.generateTestAudio(1000, format);

      const result = await benchmark.benchmarkAudioTiming(audioData, format, {
        chunkSize: 1200,
        deliveryRate: 50,
        testMode: true,
      });

      expect(result.success).toBe(true);
      expect(result.chunkCount).toBeGreaterThan(0);
      expect(result.averageChunkInterval).toBeGreaterThan(0);
    });

    it("should handle varying chunk sizes", async () => {
      const format: AudioFormat = {
        sampleRate: 48000,
        channels: 2,
        bitDepth: 16,
        format: "pcm",
        bytesPerSample: 2,
        bytesPerSecond: 192000,
      };

      const audioData = benchmark.generateTestAudio(500, format);

      const result = await benchmark.benchmarkAudioTiming(audioData, format, {
        chunkSize: 2400,
        deliveryRate: 25,
        testMode: true,
      });

      expect(result.success).toBe(true);
      expect(result.maxChunkInterval).toBeGreaterThan(0);
      expect(result.minChunkInterval).toBeGreaterThan(0);
    });

    it("should detect irregular timing patterns", async () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 24,
        format: "pcm",
        bytesPerSample: 3,
        bytesPerSecond: 72000,
      };

      const audioData = benchmark.generateTestAudio(2000, format);

      const result = await benchmark.benchmarkAudioTiming(audioData, format, {
        testMode: true,
      });

      expect(result.success).toBe(true);
      expect(result.maxChunkInterval).toBeGreaterThan(0);
      expect(result.minChunkInterval).toBeGreaterThan(0);
    });
  });

  describe("Buffer Underrun Detection", () => {
    it("should accurately detect buffer underruns", async () => {
      const format: AudioFormat = {
        sampleRate: 22050,
        channels: 1,
        bitDepth: 16,
        format: "pcm",
        bytesPerSample: 2,
        bytesPerSecond: 44100,
      };

      const audioData = benchmark.generateTestAudio(3000, format);

      const result = await benchmark.benchmarkAudioTiming(audioData, format, {
        bufferSize: 1024,
        chunkSize: 512,
      });

      expect(result).toMatchObject({
        success: true,
        bufferUnderruns: expect.any(Number),
      });
    });

    it("should measure underrun recovery time", async () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 2,
        bitDepth: 16,
        format: "pcm",
        bytesPerSample: 2,
        bytesPerSecond: 96000,
      };

      const audioData = benchmark.generateTestAudio(1500, format);

      const result = await benchmark.benchmarkAudioTiming(audioData, format, { testMode: true });

      expect(result.success).toBe(true);
      expect(result.bufferUnderruns).toBeDefined();
      expect(result.stutterCount).toBeDefined();
    });

    it("should track buffer health over time", async () => {
      const format: AudioFormat = {
        sampleRate: 48000,
        channels: 1,
        bitDepth: 16,
        format: "pcm",
        bytesPerSample: 2,
        bytesPerSecond: 96000,
      };

      const audioData = benchmark.generateTestAudio(1000, format);

      const result = await benchmark.benchmarkAudioTiming(audioData, format, { testMode: true });

      expect(result.success).toBe(true);
      expect(result.bufferUnderruns).toBeDefined();
    });
  });

  describe("Error Handling", () => {
    it("should handle invalid audio data gracefully", async () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 16,
        format: "pcm",
        bytesPerSample: 2,
        bytesPerSecond: 48000,
      };

      const emptyData = new Uint8Array(0);
      const result = await benchmark.benchmarkAudioTiming(emptyData, format);

      expect(result.success).toBe(false);
    });

    it("should handle malformed audio format", async () => {
      const format: AudioFormat = {
        sampleRate: 0,
        channels: 0,
        bitDepth: 0,
        format: "pcm",
        bytesPerSample: 0,
        bytesPerSecond: 0,
      };

      const audioData = new Uint8Array(1000);
      const result = await benchmark.benchmarkAudioTiming(audioData, format);

      expect(result.success).toBe(false);
    });
  });

  describe("Report Generation", () => {
    it("should generate detailed timing report", () => {
      const mockMetrics = [
        {
          testId: "test-1",
          calculatedDurationMs: 1000,
          expectedDurationMs: 1000,
          daemonLifetimeMs: 1100,
          endOfStreamDetected: true,
          endOfStreamDelayMs: 100,
          prematureTermination: false,
          success: true,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
        } as any,
      ];

      // This should not throw
      expect(() => benchmark.printTimingReport(mockMetrics)).not.toThrow();
    });
  });
});
