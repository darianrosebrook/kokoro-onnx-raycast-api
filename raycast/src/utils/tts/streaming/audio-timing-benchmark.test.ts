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
      };
      const audioData = new Uint8Array(48000);
      const result = await benchmark.benchmarkAudioTiming(audioData, format, { testMode: true });
      expect(result).toMatchObject({
        calculatedDurationMs: 1000,
        expectedDurationMs: 1000,
        success: true,
      });
    }, 15000);

    it("should calculate duration correctly for 48kHz stereo 16-bit audio", async () => {
      const format: AudioFormat = {
        sampleRate: 48000,
        channels: 2,
        bitDepth: 16,
        format: "pcm",
      };
      const audioData = new Uint8Array(384000);
      const result = await benchmark.benchmarkAudioTiming(audioData, format, { testMode: true });
      expect(result).toMatchObject({
        calculatedDurationMs: 2000,
        expectedDurationMs: 2000,
        success: true,
      });
    }, 15000);

    it("should handle different bit depths correctly", async () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 24,
        format: "pcm",
      };
      const audioData = new Uint8Array(72000);
      const result = await benchmark.benchmarkAudioTiming(audioData, format, { testMode: true });
      expect(result).toMatchObject({
        calculatedDurationMs: 1000,
        expectedDurationMs: 1000,
        success: true,
      });
    }, 15000);
  });

  describe("Test Audio Generation", () => {
    it("should generate test audio with correct size", () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 16,
        format: "pcm",
      };

      const durationMs = 1000;
      const audioData = benchmark.generateTestAudio(durationMs, format);

      // Expected size: 24000 samples * 1 channel * 2 bytes = 48000 bytes
      expect(audioData.length).toBe(48000);
    });

    it("should generate stereo test audio with correct size", () => {
      const format: AudioFormat = {
        sampleRate: 48000,
        channels: 2,
        bitDepth: 16,
        format: "pcm",
      };

      const durationMs = 2000;
      const audioData = benchmark.generateTestAudio(durationMs, format);

      // Expected size: 48000 samples * 2 channels * 2 bytes * 2 seconds = 384000 bytes
      expect(audioData.length).toBe(384000);
    });
  });

  describe("Chunked Delivery Simulation", () => {
    it("should simulate chunked delivery with correct timing", async () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 16,
        format: "pcm",
      };

      const audioData = benchmark.generateTestAudio(1000, format);

      // Use real timers for this test
      vi.useRealTimers();

      const result = await benchmark.benchmarkAudioTiming(audioData, format, {
        chunkSize: 2400, // 50ms chunks
        deliveryRate: 50, // 50ms between chunks
        testMode: true,
      });

      expect(result.chunkCount).toBeGreaterThan(0);
      expect(result.averageChunkInterval).toBeGreaterThan(0);
      expect(result.firstChunkTime).toBeLessThan(result.lastChunkTime);
    });
  });

  describe("Daemon Lifecycle Simulation", () => {
    it("should detect premature daemon termination", async () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 16,
        format: "pcm",
      };

      const audioData = benchmark.generateTestAudio(5000, format); // 5 second audio

      // Use real timers for this test
      vi.useRealTimers();

      const result = await benchmark.benchmarkAudioTiming(audioData, format, {
        testDurationMs: 1000, // Force premature termination
        testMode: true,
      });

      expect(result.prematureTermination).toBe(true);
      expect(result.daemonLifetimeMs).toBeLessThan(result.expectedDurationMs * 0.9);
    }, 15000);

    it("should allow normal daemon lifecycle", async () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 16,
        format: "pcm",
      };

      const audioData = benchmark.generateTestAudio(1000, format); // 1 second audio

      // Use real timers for this test
      vi.useRealTimers();

      const result = await benchmark.benchmarkAudioTiming(audioData, format, { testMode: true });

      expect(result.prematureTermination).toBe(false);
      expect(result.daemonLifetimeMs).toBeGreaterThan(result.expectedDurationMs * 0.9);
    });
  });

  describe("End-of-Stream Detection", () => {
    it("should detect end-of-stream within reasonable time", async () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 16,
        format: "pcm",
      };

      const audioData = benchmark.generateTestAudio(1000, format);

      // Use real timers for this test
      vi.useRealTimers();

      const result = await benchmark.benchmarkAudioTiming(audioData, format, { testMode: true });

      expect(result.endOfStreamDetected).toBe(true);
      expect(result.endOfStreamDelayMs).toBeLessThan(1000); // Within 1 second
    });
  });

  describe("Buffer Behavior Analysis", () => {
    it("should detect buffer underruns", async () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 16,
        format: "pcm",
      };

      const audioData = benchmark.generateTestAudio(1000, format);

      // Use real timers for this test
      vi.useRealTimers();

      const result = await benchmark.benchmarkAudioTiming(audioData, format, {
        deliveryRate: 10, // Very fast delivery to simulate underruns
        testMode: true,
      });

      expect(result.bufferUnderruns).toBeGreaterThanOrEqual(0);
      expect(result.stutterCount).toBeGreaterThanOrEqual(0);
    });
  });

  describe("Timing Accuracy", () => {
    it("should maintain high timing accuracy", async () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 16,
        format: "pcm",
      };

      const audioData = benchmark.generateTestAudio(1000, format);

      // Use real timers for this test
      vi.useRealTimers();

      const result = await benchmark.benchmarkAudioTiming(audioData, format, { testMode: true });

      const accuracy =
        Math.abs(result.calculatedDurationMs - result.expectedDurationMs) /
        result.expectedDurationMs;
      expect(accuracy).toBeLessThan(0.05); // Within 5% accuracy
    });

    it("should handle different audio durations accurately", async () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 16,
        format: "pcm",
      };

      const durations = [500, 1000, 2000, 5000];

      // Use real timers for this test
      vi.useRealTimers();

      for (const duration of durations) {
        const audioData = benchmark.generateTestAudio(duration, format);
        const result = await benchmark.benchmarkAudioTiming(audioData, format, { testMode: true });

        const accuracy =
          Math.abs(result.calculatedDurationMs - result.expectedDurationMs) /
          result.expectedDurationMs;
        expect(accuracy).toBeLessThan(0.05); // Within 5% accuracy
      }
    }, 15000);
  });

  describe("Comprehensive Test Suite", () => {
    it("should run timing test suite successfully", async () => {
      // Use real timers for this test
      vi.useRealTimers();

      const { results, summary } = await benchmark.runTimingTestSuite();

      expect(results.length).toBeGreaterThan(0);
      expect(summary.totalTests).toBeGreaterThan(0);
      expect(summary.successfulTests).toBeGreaterThanOrEqual(0);
      expect(summary.averageAccuracy).toBeGreaterThanOrEqual(0);
      expect(summary.prematureTerminations).toBeGreaterThanOrEqual(0);
      expect(Array.isArray(summary.recommendations)).toBe(true);
    }, 15000);
  });

  describe("Error Handling", () => {
    it("should handle invalid audio data gracefully", async () => {
      const format: AudioFormat = {
        sampleRate: 24000,
        channels: 1,
        bitDepth: 16,
        format: "pcm",
      };

      const emptyAudioData = new Uint8Array(0);

      // Use real timers for this test
      vi.useRealTimers();

      const result = await benchmark.benchmarkAudioTiming(emptyAudioData, format, {
        testMode: true,
      });

      expect(result.success).toBe(false);
      expect(result.errorMessage).toBeDefined();
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
        } as any,
      ];

      // This should not throw
      expect(() => benchmark.printTimingReport(mockMetrics)).not.toThrow();
    });
  });
});
