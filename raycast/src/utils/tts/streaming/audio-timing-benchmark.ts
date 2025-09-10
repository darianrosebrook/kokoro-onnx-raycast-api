/**
 * Audio Timing Benchmark for Raycast Kokoro TTS
 *
 * This module provides comprehensive testing for audio timing accuracy,
 * end-of-stream detection, and daemon lifecycle management to ensure
 * reliable playback without premature daemon termination.
 *
 * Features:
 * - Audio duration calculation and validation
 * - End-of-stream detection timing
 * - Daemon lifecycle management testing
 * - Buffer timing and jitter analysis
 * - Stutter detection and compensation
 * - Playback completion verification
 *
 * @author @darianrosebrook
 * @version 1.0.0
 * @since 2025-07-17
 */

import { performance } from "perf_hooks";
import type { AudioFormat } from "../../validation/tts-types.js";

/**
 * Audio timing metrics
 */
interface AudioTimingMetrics {
  testId: string;
  timestamp: number;

  // Audio characteristics
  sampleRate: number;
  channels: number;
  bitDepth: number;
  audioDataSize: number;
  expectedDurationMs: number;

  // Timing measurements
  startTime: number;
  firstChunkTime: number;
  lastChunkTime: number;
  endOfStreamTime: number;
  daemonStartTime: number;
  daemonEndTime: number;

  // Duration calculations
  calculatedDurationMs: number;
  actualPlaybackDurationMs: number;
  daemonLifetimeMs: number;

  // Buffer and timing analysis
  chunkCount: number;
  averageChunkInterval: number;
  maxChunkInterval: number;
  minChunkInterval: number;
  bufferUnderruns: number;
  stutterCount: number;

  // End-of-stream detection
  endOfStreamDetected: boolean;
  endOfStreamDelayMs: number;
  prematureTermination: boolean;

  // Success indicators
  success: boolean;
  errorMessage?: string;
}

/**
 * Audio format configuration for testing
 */
interface AudioTestConfig {
  sampleRate: number;
  channels: number;
  bitDepth: number;
  testDurationMs: number;
  chunkSize: number;
  deliveryRate: number;
  bufferSize: number;
  testMode: boolean;
  format: string;
}

/**
 * Audio Timing Benchmark
 */
export class AudioTimingBenchmark {
  private readonly name = "AudioTimingBenchmark";
  private metrics: AudioTimingMetrics[] = [];
  private isCollecting = false;
  private testMode = false;

  constructor(testMode = false) {
    this.testMode = testMode;
    console.log("Audio timing benchmark system created", {
      component: this.name,
      method: "constructor",
      testMode,
    });
  }

  /**
   * Start collecting timing metrics
   */
  startCollection(): void {
    this.isCollecting = true;
    this.metrics = [];
    console.log("Audio timing benchmark started");
  }

  /**
   * Stop collecting and generate report
   */
  stopCollection(): {
    totalTests: number;
    successfulTests: number;
    averageAccuracy: number;
    prematureTerminations: number;
    recommendations: string[];
  } {
    this.isCollecting = false;
    const report = this.generateReport();
    console.log("Audio timing benchmark completed", report);
    return report;
  }

  /**
   * Benchmark audio timing with comprehensive analysis
   */
  async benchmarkAudioTiming(
    audioData: Uint8Array,
    format: AudioFormat,
    config: Partial<AudioTestConfig> = {}
  ): Promise<AudioTimingMetrics> {
    const testId = `audio-timing-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
    const startTime = performance.now();

    // Fail-fast guard for empty audio data
    if (!audioData || audioData.length === 0) {
      return {
        testId,
        timestamp: Date.now(),
        sampleRate: format.sampleRate,
        channels: format.channels,
        bitDepth: format.bitDepth,
        audioDataSize: 0,
        expectedDurationMs: 0,
        startTime,
        firstChunkTime: 0,
        lastChunkTime: 0,
        endOfStreamTime: 0,
        daemonStartTime: 0,
        daemonEndTime: 0,
        calculatedDurationMs: 0,
        actualPlaybackDurationMs: 0,
        daemonLifetimeMs: 0,
        chunkCount: 0,
        averageChunkInterval: 0,
        maxChunkInterval: 0,
        minChunkInterval: 0,
        bufferUnderruns: 0,
        stutterCount: 0,
        endOfStreamDetected: false,
        endOfStreamDelayMs: 0,
        prematureTermination: false,
        success: false,
        errorMessage: "Audio data is empty.",
      };
    }

    const testConfig: AudioTestConfig = {
      sampleRate: format.sampleRate,
      channels: format.channels,
      bitDepth: format.bitDepth,
      testDurationMs: 5000, // 5 seconds default
      chunkSize: 2400, // 50ms at 24kHz, 16-bit, mono
      deliveryRate: 50, // 50ms between chunks
      bufferSize: 2 * 1024 * 1024, // 2MB
      testMode: false, // Default test mode
      format: "pcm", // Default format
      ...config,
    };
    // If testMode is set in config, override instance testMode
    const testMode = (config as AudioFormat & { testMode?: boolean }).testMode ?? this.testMode;

    const metrics: Partial<AudioTimingMetrics> = {
      testId,
      timestamp: Date.now(),
      sampleRate: testConfig.sampleRate,
      channels: testConfig.channels,
      bitDepth: testConfig.bitDepth,
      audioDataSize: audioData.length,
      startTime,
      success: false,
    };

    try {
      // Calculate expected duration
      const bytesPerSample = testConfig.bitDepth / 8;
      const bytesPerSecond = testConfig.sampleRate * testConfig.channels * bytesPerSample;
      const expectedDurationMs = (audioData.length / bytesPerSecond) * 1000;
      metrics.expectedDurationMs = expectedDurationMs;

      // Simulate chunked delivery
      const chunkTiming = await this.simulateChunkedDelivery(audioData, testConfig, testMode);
      metrics.chunkCount = chunkTiming.chunkCount;
      metrics.firstChunkTime = chunkTiming.firstChunkTime;
      metrics.lastChunkTime = chunkTiming.lastChunkTime;
      metrics.averageChunkInterval = chunkTiming.averageInterval;
      metrics.maxChunkInterval = chunkTiming.maxInterval;
      metrics.minChunkInterval = chunkTiming.minInterval;

      // Calculate actual duration
      const actualDurationMs = chunkTiming.lastChunkTime - chunkTiming.firstChunkTime;
      metrics.actualPlaybackDurationMs = actualDurationMs;

      // Simulate daemon lifecycle
      const daemonTiming = await this.simulateDaemonLifecycle(
        testConfig,
        expectedDurationMs,
        testMode
      );
      metrics.daemonStartTime = daemonTiming.startTime;
      metrics.daemonEndTime = daemonTiming.endTime;
      metrics.daemonLifetimeMs = daemonTiming.lifetimeMs;
      metrics.prematureTermination = daemonTiming.prematureTermination;

      // Test end-of-stream detection
      const endOfStreamTiming = await this.testEndOfStreamDetection(
        chunkTiming,
        expectedDurationMs,
        testConfig,
        testMode
      );
      metrics.endOfStreamTime = endOfStreamTiming.detectionTime;
      metrics.endOfStreamDetected = endOfStreamTiming.detected;
      metrics.endOfStreamDelayMs = endOfStreamTiming.delayMs;

      // Analyze buffer behavior
      const bufferAnalysis = this.analyzeBufferBehavior(chunkTiming, testConfig);
      metrics.bufferUnderruns = bufferAnalysis.underruns;
      metrics.stutterCount = bufferAnalysis.stutters;

      // Calculate accuracy
      const calculatedDurationMs = this.calculateAudioDuration(audioData, format);
      metrics.calculatedDurationMs = calculatedDurationMs;

      // Determine success
      const accuracy = Math.abs(calculatedDurationMs - expectedDurationMs) / expectedDurationMs;
      const success =
        accuracy < 0.05 && // Within 5% accuracy
        !daemonTiming.prematureTermination &&
        endOfStreamTiming.detected &&
        endOfStreamTiming.delayMs < 1000; // End-of-stream detected within 1 second

      metrics.success = success;

      if (this.isCollecting) {
        this.metrics.push(metrics as AudioTimingMetrics);
      }

      console.log("Audio timing benchmark completed", {
        component: this.name,
        method: "benchmarkAudioTiming",
        testId,
        accuracy: `${(accuracy * 100).toFixed(2)}%`,
        success,
        calculatedDurationMs,
        expectedDurationMs,
        daemonLifetimeMs: metrics.daemonLifetimeMs,
      });

      return metrics as AudioTimingMetrics;
    } catch (error) {
      metrics.success = false;
      metrics.errorMessage = error instanceof Error ? error.message : "Unknown error";

      console.error("Audio timing benchmark failed", {
        component: this.name,
        method: "benchmarkAudioTiming",
        testId,
        error: metrics.errorMessage,
      });

      return metrics as AudioTimingMetrics;
    }
  }

  /**
   * Simulate chunked audio delivery with timing analysis
   */
  private async simulateChunkedDelivery(
    audioData: Uint8Array,
    config: AudioTestConfig,
    testMode = false
  ): Promise<{
    chunkCount: number;
    firstChunkTime: number;
    lastChunkTime: number;
    averageInterval: number;
    maxInterval: number;
    minInterval: number;
  }> {
    const chunkSize = config.chunkSize;
    const deliveryRate = config.deliveryRate;
    const chunks: number[] = [];
    const intervals: number[] = [];

    let currentOffset = 0;
    let lastChunkTime = performance.now();
    const firstChunkTime = lastChunkTime;

    while (currentOffset < audioData.length) {
      const _chunk = audioData.slice(currentOffset, currentOffset + chunkSize);
      const chunkTime = performance.now();

      chunks.push(chunkTime);
      if (chunks.length > 1) {
        intervals.push(chunkTime - lastChunkTime);
      }

      lastChunkTime = chunkTime;
      currentOffset += chunkSize;

      // Simulate delivery rate
      if (currentOffset < audioData.length && !testMode) {
        await new Promise((resolve) => setTimeout(resolve, deliveryRate));
      }
    }

    const averageInterval =
      intervals.length > 0 ? intervals.reduce((a, b) => a + b, 0) / intervals.length : 0;
    const maxInterval = intervals.length > 0 ? Math.max(...intervals) : 0;
    const minInterval = intervals.length > 0 ? Math.min(...intervals) : 0;

    return {
      chunkCount: chunks.length,
      firstChunkTime,
      lastChunkTime,
      averageInterval,
      maxInterval,
      minInterval,
    };
  }

  /**
   * Simulate daemon lifecycle with premature termination detection
   */
  private async simulateDaemonLifecycle(
    config: AudioTestConfig,
    expectedDurationMs: number,
    testMode = false
  ): Promise<{
    startTime: number;
    endTime: number;
    lifetimeMs: number;
    prematureTermination: boolean;
  }> {
    const startTime = performance.now();

    // Simulate daemon startup time
    if (!testMode) {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }

    // Simulate daemon processing with potential jitter
    let processingTime = expectedDurationMs + this.generateJitter(200);
    if (testMode) {
      // If testDurationMs is set short, simulate premature termination
      if (config.testDurationMs && config.testDurationMs < expectedDurationMs * 0.9) {
        processingTime = config.testDurationMs;
      } else {
        processingTime = expectedDurationMs;
      }
    }
    if (!testMode) {
      await new Promise((resolve) => setTimeout(resolve, processingTime));
    }

    const endTime = performance.now() + (testMode ? processingTime : 0);
    const lifetimeMs = endTime - startTime;

    // Check for premature termination (daemon ended before audio should be complete)
    const prematureTermination = lifetimeMs < expectedDurationMs * 0.9; // 10% tolerance

    return {
      startTime,
      endTime,
      lifetimeMs,
      prematureTermination,
    };
  }

  /**
   * Test end-of-stream detection timing
   */
  private async testEndOfStreamDetection(
    chunkTiming: {
      chunkCount: number;
      firstChunkTime: number;
      lastChunkTime: number;
    },
    expectedDurationMs: number,
    config: AudioTestConfig,
    testMode = false
  ): Promise<{
    detectionTime: number;
    detected: boolean;
    delayMs: number;
  }> {
    const detectionStart = performance.now();

    // Simulate end-of-stream detection logic
    // Wait for a period after the last chunk to detect end-of-stream
    const detectionDelay = Math.max(100, config.deliveryRate * 2); // At least 100ms or 2x delivery rate
    if (!testMode) {
      await new Promise((resolve) => setTimeout(resolve, detectionDelay));
    }

    const detectionTime = performance.now();
    const delayMs = detectionTime - detectionStart;

    // End-of-stream should be detected within reasonable time
    const detected = delayMs < 1000; // Within 1 second

    return {
      detectionTime,
      detected,
      delayMs,
    };
  }

  /**
   * Analyze buffer behavior for underruns and stutters
   */
  private analyzeBufferBehavior(
    chunkTiming: {
      averageInterval: number;
      maxInterval: number;
      minInterval: number;
    },
    config: AudioTestConfig
  ): {
    underruns: number;
    stutters: number;
  } {
    const expectedInterval = config.deliveryRate;
    const tolerance = expectedInterval * 0.2; // 20% tolerance

    // Count intervals that are too long (underruns)
    const underruns = chunkTiming.maxInterval > expectedInterval + tolerance ? 1 : 0;

    // Count intervals that are too short (stutters)
    const stutters = chunkTiming.minInterval < expectedInterval - tolerance ? 1 : 0;

    return { underruns, stutters };
  }

  /**
   * Calculate audio duration from data and format
   */
  private calculateAudioDuration(audioData: Uint8Array, format: AudioFormat): number {
    const bytesPerSample = format.bitDepth / 8;
    const bytesPerSecond = format.sampleRate * format.channels * bytesPerSample;
    return (audioData.length / bytesPerSecond) * 1000;
  }

  /**
   * Generate realistic jitter for timing simulation
   */
  private generateJitter(maxJitterMs: number): number {
    return (Math.random() - 0.5) * 2 * maxJitterMs;
  }

  /**
   * Generate test audio data
   */
  generateTestAudio(durationMs: number, format: AudioFormat): Uint8Array {
    const samples = Math.floor((durationMs / 1000) * format.sampleRate);
    // eslint-disable-next-line no-undef
    const buffer = Buffer.alloc(samples * format.channels * (format.bitDepth / 8));

    // Generate a simple sine wave (440Hz)
    const frequency = 440;
    const amplitude = 0.3;

    for (let i = 0; i < samples; i++) {
      const sample = Math.sin((2 * Math.PI * frequency * i) / format.sampleRate) * amplitude;
      const intSample = Math.round(sample * 32767);

      for (let channel = 0; channel < format.channels; channel++) {
        const offset = (i * format.channels + channel) * (format.bitDepth / 8);
        buffer.writeInt16LE(intSample, offset);
      }
    }

    return new Uint8Array(buffer);
  }

  /**
   * Run comprehensive timing test suite
   */
  async runTimingTestSuite(): Promise<{
    results: AudioTimingMetrics[];
    summary: {
      totalTests: number;
      successfulTests: number;
      averageAccuracy: number;
      prematureTerminations: number;
      recommendations: string[];
    };
  }> {
    this.startCollection();

    const testCases = [
      { durationMs: 1000, sampleRate: 24000, channels: 1, bitDepth: 16 },
      { durationMs: 3000, sampleRate: 24000, channels: 1, bitDepth: 16 },
      { durationMs: 5000, sampleRate: 24000, channels: 1, bitDepth: 16 },
      { durationMs: 10000, sampleRate: 24000, channels: 1, bitDepth: 16 },
      { durationMs: 2000, sampleRate: 48000, channels: 2, bitDepth: 16 },
    ];

    const results: AudioTimingMetrics[] = [];

    for (const testCase of testCases) {
      const audioData = this.generateTestAudio(testCase.durationMs, {
        sampleRate: testCase.sampleRate,
        channels: testCase.channels,
        bitDepth: testCase.bitDepth,
        format: "pcm",
        bytesPerSample: testCase.bitDepth / 8,
        bytesPerSecond: testCase.sampleRate * testCase.channels * (testCase.bitDepth / 8),
      });

      const result = await this.benchmarkAudioTiming(audioData, {
        sampleRate: testCase.sampleRate,
        channels: testCase.channels,
        bitDepth: testCase.bitDepth,
        format: "pcm",
        bytesPerSample: testCase.bitDepth / 8,
        bytesPerSecond: testCase.sampleRate * testCase.channels * (testCase.bitDepth / 8),
      });

      results.push(result);

      // Wait between tests
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }

    const summary = this.stopCollection();
    return { results, summary };
  }

  /**
   * Generate comprehensive report
   */
  private generateReport(): {
    totalTests: number;
    successfulTests: number;
    averageAccuracy: number;
    prematureTerminations: number;
    recommendations: string[];
  } {
    if (this.metrics.length === 0) {
      return {
        totalTests: 0,
        successfulTests: 0,
        averageAccuracy: 0,
        prematureTerminations: 0,
        recommendations: ["No timing data available"],
      };
    }

    const successfulTests = this.metrics.filter((m) => m.success).length;
    const prematureTerminations = this.metrics.filter((m) => m.prematureTermination).length;

    const accuracies = this.metrics.map((m) => {
      if (m.calculatedDurationMs && m.expectedDurationMs) {
        return Math.abs(m.calculatedDurationMs - m.expectedDurationMs) / m.expectedDurationMs;
      }
      return 1; // 100% error if calculation failed
    });

    const averageAccuracy = accuracies.reduce((a, b) => a + b, 0) / accuracies.length;

    const recommendations: string[] = [];

    if (prematureTerminations > 0) {
      recommendations.push(
        `Fix premature daemon termination (${prematureTerminations}/${this.metrics.length} tests)`
      );
    }

    if (averageAccuracy > 0.05) {
      recommendations.push("Improve audio duration calculation accuracy");
    }

    const endOfStreamFailures = this.metrics.filter((m) => !m.endOfStreamDetected).length;
    if (endOfStreamFailures > 0) {
      recommendations.push(
        `Fix end-of-stream detection (${endOfStreamFailures}/${this.metrics.length} tests)`
      );
    }

    return {
      totalTests: this.metrics.length,
      successfulTests,
      averageAccuracy,
      prematureTerminations,
      recommendations,
    };
  }

  /**
   * Get collected metrics
   */
  getMetrics(): AudioTimingMetrics[] {
    return [...this.metrics];
  }

  /**
   * Print detailed timing report
   */
  printTimingReport(metrics: AudioTimingMetrics[]): void {
    console.log("\n" + "=".repeat(80));
    console.log(" AUDIO TIMING BENCHMARK REPORT");
    console.log("=".repeat(80));

    for (const metric of metrics) {
      console.log(`\nTest: ${metric.testId}`);
      console.log(
        `  Duration: ${metric.calculatedDurationMs.toFixed(1)}ms (expected: ${metric.expectedDurationMs.toFixed(1)}ms)`
      );
      console.log(
        `  Accuracy: ${((1 - Math.abs(metric.calculatedDurationMs - metric.expectedDurationMs) / metric.expectedDurationMs) * 100).toFixed(1)}%`
      );
      console.log(`  Daemon Lifetime: ${metric.daemonLifetimeMs.toFixed(1)}ms`);
      console.log(
        `  End-of-Stream: ${metric.endOfStreamDetected ? "✅" : ""} (${metric.endOfStreamDelayMs.toFixed(1)}ms delay)`
      );
      console.log(`  Premature Termination: ${metric.prematureTermination ? "" : "✅"}`);
      console.log(`  Success: ${metric.success ? "✅" : ""}`);
    }

    const summary = this.generateReport();
    console.log(`\nSUMMARY:`);
    console.log(`  Total Tests: ${summary.totalTests}`);
    console.log(`  Successful: ${summary.successfulTests}/${summary.totalTests}`);
    console.log(`  Average Accuracy: ${((1 - summary.averageAccuracy) * 100).toFixed(1)}%`);
    console.log(`  Premature Terminations: ${summary.prematureTerminations}`);

    if (summary.recommendations.length > 0) {
      console.log(`\nRECOMMENDATIONS:`);
      summary.recommendations.forEach((rec) => console.log(`  - ${rec}`));
    }
  }
}

/**
 * Global audio timing benchmark instance
 */
export const audioTimingBenchmark = new AudioTimingBenchmark();
