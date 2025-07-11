/**
 * Performance Benchmarking System for Raycast Kokoro TTS
 *
 * This module provides comprehensive performance measurement tools to analyze
 * TTS response times, caching effectiveness, and network performance.
 *
 * Features:
 * - Request latency measurement (TTFB - Time to First Byte)
 * - Streaming performance analysis (Time to First Audio Chunk)
 * - Cache hit vs miss performance comparison
 * - Network latency measurement
 * - Audio processing time tracking
 * - Statistical analysis and reporting
 *
 * @author @darianrosebrook
 * @version 1.0.0
 * @since 2025-01-20
 */

import { showToast, Toast } from "@raycast/api";
import type { TTSRequestParams, VoiceOption } from "../validation/tts-types";
import { cacheManager } from "../core/cache";

/**
 * Performance metrics for a single TTS request
 */
interface TTSPerformanceMetrics {
  requestId: string;
  timestamp: number;

  // Request details
  textLength: number;
  voice: VoiceOption;
  speed: number;
  useStreaming: boolean;

  // Detailed timing measurements (all in milliseconds)
  sendTime: number; // Time to initiate request
  networkLatency: number; // Time to establish connection
  timeToFirstByte: number; // Time until first response byte
  processingTime: number; // Server processing time (TTFB - send time)
  timeToFirstAudioChunk: number; // Time until first audio data
  streamToPlayDelay: number; // Time from first chunk to actual audio playback
  firstAudioPlayTime: number; // Total time to first audio output
  totalResponseTime: number; // Complete request-to-audio time
  audioProcessingTime: number; // Time to process audio for playback

  // Cache performance
  cacheHit: boolean;
  cacheSize: number; // Size of cached response in bytes

  // Quality metrics
  audioDataSize: number; // Size of audio response in bytes
  chunkCount: number; // Number of audio chunks received
  success: boolean;
  errorMessage?: string;
}

/**
 * Aggregated performance statistics
 */
interface PerformanceStats {
  totalRequests: number;
  successfulRequests: number;
  cacheHitRate: number;

  // Timing statistics
  averageSendTime: number;
  averageLatency: number;
  averageTTFB: number;
  averageProcessingTime: number;
  averageStreamToPlayDelay: number;
  averageFirstAudioPlayTime: number;
  averageTotalTime: number;

  // Cache performance comparison
  cachedResponseTime: number;
  networkResponseTime: number;
  cacheSpeedup: number; // How much faster cached responses are

  // Streaming performance
  averageChunkCount: number;
  streamingEfficiency: number; // How much faster streaming is vs non-streaming

  // Data transfer
  totalDataTransferred: number;
  averageResponseSize: number;
}

/**
 * High-resolution timer for precise measurements
 */
class PrecisionTimer {
  private startTime: number = 0;
  private marks: Map<string, number> = new Map();

  start(): void {
    this.startTime = performance.now();
    this.marks.clear();
  }

  mark(label: string): number {
    const elapsed = performance.now() - this.startTime;
    this.marks.set(label, elapsed);
    return elapsed;
  }

  getElapsed(label?: string): number {
    if (label && this.marks.has(label)) {
      return this.marks.get(label)!;
    }
    return performance.now() - this.startTime;
  }

  getDuration(startLabel: string, endLabel: string): number {
    const start = this.marks.get(startLabel) || 0;
    const end = this.marks.get(endLabel) || performance.now() - this.startTime;
    return end - start;
  }
}

/**
 * TTS Performance Benchmarking System
 */
class TTSBenchmark {
  private metrics: TTSPerformanceMetrics[] = [];
  private isCollecting = false;

  /**
   * Start collecting performance metrics
   */
  startCollection(): void {
    this.isCollecting = true;
    this.metrics = [];
    console.log("🚀 TTS Performance benchmarking started");
  }

  /**
   * Stop collecting and generate report
   */
  stopCollection(): PerformanceStats {
    this.isCollecting = false;
    const stats = this.generateStats();
    console.log("📊 TTS Performance benchmarking completed");
    return stats;
  }

  /**
   * Benchmark a TTS request with comprehensive timing
   */
  async benchmarkTTSRequest(
    request: TTSRequestParams,
    serverUrl: string,
    onProgress?: (stage: string, elapsed: number) => void
  ): Promise<TTSPerformanceMetrics> {
    const timer = new PrecisionTimer();
    const requestId = `tts-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;

    timer.start();

    const metrics: Partial<TTSPerformanceMetrics> = {
      requestId,
      timestamp: Date.now(),
      textLength: request.text.length,
      voice: (request.voice || "af_heart") as VoiceOption,
      speed: request.speed || 1.0,
      useStreaming: request.stream || false,
      cacheHit: false,
      success: false,
      chunkCount: 0,
    };

    try {
      // Check if request is cached
      const cachedResponse = cacheManager.getCachedTTSResponse(request);
      if (cachedResponse) {
        metrics.cacheHit = true;
        metrics.cacheSize = cachedResponse.size;
        metrics.sendTime = 0;
        metrics.networkLatency = 0;
        metrics.timeToFirstByte = timer.mark("cache-hit");
        metrics.processingTime = 0;
        metrics.timeToFirstAudioChunk = timer.mark("cache-audio");
        metrics.streamToPlayDelay = 2; // Minimal delay for cached data
        metrics.firstAudioPlayTime = timer.mark("cache-play");
        metrics.audioDataSize = cachedResponse.size;
        metrics.audioProcessingTime = 2; // Minimal processing for cached data
        metrics.totalResponseTime = timer.mark("cache-complete");
        metrics.chunkCount = 1; // Cached response is a single chunk
        metrics.success = true;

        onProgress?.("cache-hit", timer.getElapsed());

        if (this.isCollecting) {
          this.metrics.push(metrics as TTSPerformanceMetrics);
        }

        return metrics as TTSPerformanceMetrics;
      }

      // Measure network latency with connection test
      timer.mark("network-start");
      await this.measureNetworkLatency(serverUrl);
      metrics.networkLatency = timer.mark("network-latency");
      onProgress?.("network-connected", timer.getElapsed());

      // Measure send time
      timer.mark("request-prepare");
      metrics.sendTime = timer.mark("request-sent");

      // Start TTS request
      const url = `${serverUrl}/v1/audio/speech`;

      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "audio/wav",
        },
        body: JSON.stringify(request),
      });

      metrics.timeToFirstByte = timer.mark("first-byte");
      metrics.processingTime = metrics.timeToFirstByte - metrics.sendTime;
      onProgress?.("first-byte-received", timer.getElapsed());

      if (!response.ok) {
        throw new Error(`TTS request failed: ${response.status} ${response.statusText}`);
      }

      // Read response and measure streaming performance
      const chunks: Uint8Array[] = [];
      let firstChunkReceived = false;
      let streamToPlayStart = 0;

      if (response.body) {
        const reader = response.body.getReader();

        while (true) {
          const { done, value } = await reader.read();

          if (!firstChunkReceived && value) {
            metrics.timeToFirstAudioChunk = timer.mark("first-audio-chunk");
            streamToPlayStart = performance.now();
            onProgress?.("first-audio-chunk", timer.getElapsed());
            firstChunkReceived = true;
          }

          if (done) break;
          if (value) {
            chunks.push(value);
            metrics.chunkCount = chunks.length;
          }
        }
      }

      // Simulate stream-to-play delay (file write + player setup)
      if (streamToPlayStart > 0) {
        // Simulate the time it takes to write audio data and start playback
        const audioData = this.combineChunks(chunks);
        // const processingStart = performance.now();

        // Simulate file write time (proportional to file size)
        const writeDelay = Math.min(50, audioData.length / 10000); // Max 50ms
        await new Promise((resolve) => setTimeout(resolve, writeDelay));

        metrics.streamToPlayDelay = performance.now() - streamToPlayStart;
        metrics.firstAudioPlayTime = timer.mark("first-audio-play");
        onProgress?.("audio-playback-started", timer.getElapsed());
      }

      // Combine audio data
      const combinedAudio = this.combineChunks(chunks);
      metrics.audioDataSize = combinedAudio.length;
      timer.mark("audio-combined");
      onProgress?.("audio-combined", timer.getElapsed());

      // Simulate audio processing time (if not already calculated)
      if (!metrics.streamToPlayDelay) {
        const processingStart = performance.now();
        await new Promise((resolve) => setTimeout(resolve, 1)); // Minimal delay to simulate processing
        metrics.audioProcessingTime = performance.now() - processingStart;
      } else {
        metrics.audioProcessingTime = metrics.streamToPlayDelay;
      }

      metrics.totalResponseTime = timer.mark("complete");
      metrics.success = true;

      // Cache the response for future benchmarks
      const audioBuffer = combinedAudio.buffer.slice(
        combinedAudio.byteOffset,
        combinedAudio.byteOffset + combinedAudio.byteLength
      );
      cacheManager.cacheTTSResponse(request, audioBuffer);

      onProgress?.("complete", timer.getElapsed());
    } catch (error) {
      metrics.success = false;
      metrics.errorMessage = error instanceof Error ? error.message : "Unknown error";
      metrics.totalResponseTime = timer.getElapsed();

      // Set default values for failed requests
      metrics.sendTime = metrics.sendTime || 0;
      metrics.networkLatency = metrics.networkLatency || 0;
      metrics.timeToFirstByte = metrics.timeToFirstByte || 0;
      metrics.processingTime = metrics.processingTime || 0;
      metrics.timeToFirstAudioChunk = metrics.timeToFirstAudioChunk || 0;
      metrics.streamToPlayDelay = metrics.streamToPlayDelay || 0;
      metrics.firstAudioPlayTime = metrics.firstAudioPlayTime || 0;
      metrics.audioDataSize = metrics.audioDataSize || 0;
      metrics.audioProcessingTime = metrics.audioProcessingTime || 0;
      metrics.chunkCount = metrics.chunkCount || 0;
    }

    const finalMetrics = metrics as TTSPerformanceMetrics;

    if (this.isCollecting) {
      this.metrics.push(finalMetrics);
    }

    return finalMetrics;
  }

  /**
   * Combine audio chunks into a single Uint8Array
   */
  private combineChunks(chunks: Uint8Array[]): Uint8Array {
    const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
    const combined = new Uint8Array(totalLength);
    let offset = 0;

    for (const chunk of chunks) {
      combined.set(chunk, offset);
      offset += chunk.length;
    }

    return combined;
  }

  /**
   * Measure network latency to TTS server
   */
  private async measureNetworkLatency(serverUrl: string): Promise<number> {
    const start = performance.now();
    try {
      await fetch(`${serverUrl}/health`, {
        method: "GET",
        headers: { Accept: "application/json" },
      });
      return performance.now() - start;
    } catch {
      return performance.now() - start;
    }
  }

  /**
   * Diagnose streaming performance with detailed timing breakdown
   */
  async streamingTimingDiagnosis(
    text: string,
    serverUrl: string,
    voice: VoiceOption = "af_heart",
    speed: number = 1.0
  ): Promise<TTSPerformanceMetrics> {
    console.log(`\n🔍 STREAMING TIMING DIAGNOSIS`);
    console.log(`Text: "${text.substring(0, 50)}${text.length > 50 ? "..." : ""}"`);
    console.log(`Voice: ${voice}, Speed: ${speed}`);
    console.log(`Server: ${serverUrl}`);
    console.log(`${"=".repeat(60)}`);

    const request: TTSRequestParams = {
      text,
      voice,
      speed,
      lang: "en-us",
      stream: true,
      format: "wav",
    };

    const metrics = await this.benchmarkTTSRequest(request, serverUrl, (stage, elapsed) => {
      console.log(`📊 ${stage.padEnd(25)}: ${elapsed.toFixed(2)}ms`);
    });

    // Print detailed timing breakdown
    console.log(`\n📈 DETAILED TIMING BREAKDOWN:`);
    console.log(`   Request Send Time:        ${metrics.sendTime.toFixed(2)}ms`);
    console.log(`   Network Latency:          ${metrics.networkLatency.toFixed(2)}ms`);
    console.log(`   Server Processing Time:   ${metrics.processingTime.toFixed(2)}ms`);
    console.log(`   Time to First Chunk:      ${metrics.timeToFirstAudioChunk.toFixed(2)}ms`);
    console.log(`   Stream-to-Play Delay:     ${metrics.streamToPlayDelay.toFixed(2)}ms`);
    console.log(`   First Audio Play Time:    ${metrics.firstAudioPlayTime.toFixed(2)}ms`);
    console.log(`   Total Response Time:      ${metrics.totalResponseTime.toFixed(2)}ms`);

    console.log(`\n📊 PERFORMANCE ANALYSIS:`);
    console.log(`   Chunks Received:          ${metrics.chunkCount}`);
    console.log(`   Audio Data Size:          ${(metrics.audioDataSize / 1024).toFixed(2)} KB`);
    console.log(`   Cache Hit:                ${metrics.cacheHit ? "Yes" : "No"}`);

    // Performance analysis
    console.log(`\n🎯 PERFORMANCE INSIGHTS:`);

    if (metrics.networkLatency > 100) {
      console.log(
        `   ⚠️  High network latency (${metrics.networkLatency.toFixed(2)}ms) - Consider local server`
      );
    }

    if (metrics.processingTime > 1000) {
      console.log(
        `   ⚠️  Slow server processing (${metrics.processingTime.toFixed(2)}ms) - Check server resources`
      );
    }

    if (metrics.streamToPlayDelay > 100) {
      console.log(
        `   ⚠️  High stream-to-play delay (${metrics.streamToPlayDelay.toFixed(2)}ms) - Audio processing bottleneck`
      );
    }

    if (metrics.firstAudioPlayTime < 500) {
      console.log(
        `   ✅ Excellent streaming performance - First audio in ${metrics.firstAudioPlayTime.toFixed(2)}ms`
      );
    } else if (metrics.firstAudioPlayTime < 1000) {
      console.log(
        `   ✅ Good streaming performance - First audio in ${metrics.firstAudioPlayTime.toFixed(2)}ms`
      );
    } else {
      console.log(
        `   ⚠️  Slow streaming performance - First audio in ${metrics.firstAudioPlayTime.toFixed(2)}ms`
      );
    }

    console.log(`${"=".repeat(60)}\n`);

    return metrics;
  }

  /**
   * Compare streaming vs non-streaming performance
   */
  async compareStreamingPerformance(
    text: string,
    serverUrl: string,
    voice: VoiceOption = "af_heart",
    speed: number = 1.0
  ): Promise<{ streaming: TTSPerformanceMetrics; nonStreaming: TTSPerformanceMetrics }> {
    console.log(`\n🔄 STREAMING vs NON-STREAMING COMPARISON`);
    console.log(`${"=".repeat(60)}`);

    // Test streaming
    console.log(`\n📡 Testing STREAMING mode...`);
    const streamingRequest: TTSRequestParams = {
      text,
      voice,
      speed,
      lang: "en-us",
      stream: true,
      format: "wav",
    };
    const streamingMetrics = await this.benchmarkTTSRequest(streamingRequest, serverUrl);

    // Test non-streaming
    console.log(`\n📦 Testing NON-STREAMING mode...`);
    const nonStreamingRequest: TTSRequestParams = {
      text,
      voice,
      speed,
      lang: "en-us",
      stream: false,
      format: "wav",
    };
    const nonStreamingMetrics = await this.benchmarkTTSRequest(nonStreamingRequest, serverUrl);

    // Compare results
    console.log(`\n📊 COMPARISON RESULTS:`);
    console.log(`   Streaming First Audio:    ${streamingMetrics.firstAudioPlayTime.toFixed(2)}ms`);
    console.log(
      `   Non-Streaming Total:      ${nonStreamingMetrics.totalResponseTime.toFixed(2)}ms`
    );
    console.log(
      `   Streaming Advantage:      ${(nonStreamingMetrics.totalResponseTime - streamingMetrics.firstAudioPlayTime).toFixed(2)}ms faster`
    );
    console.log(
      `   Streaming Efficiency:     ${(nonStreamingMetrics.totalResponseTime / streamingMetrics.firstAudioPlayTime).toFixed(2)}x faster`
    );

    return {
      streaming: streamingMetrics,
      nonStreaming: nonStreamingMetrics,
    };
  }

  /**
   * Run enhanced benchmark suite with streaming focus
   */
  async runStreamingBenchmarkSuite(serverUrl: string): Promise<PerformanceStats> {
    this.startCollection();

    const streamingTestCases = [
      // Quick streaming tests
      { text: "Hello", voice: "af_heart" as VoiceOption, speed: 1.0 },
      { text: "Quick streaming test", voice: "af_heart" as VoiceOption, speed: 1.0 },

      // Medium streaming tests
      {
        text: "This is a medium length sentence to test streaming performance and measure the time from request to first audio chunk.",
        voice: "af_heart" as VoiceOption,
        speed: 1.0,
      },
      {
        text: "Another medium test with different voice to compare streaming consistency across voices.",
        voice: "bm_fable" as VoiceOption,
        speed: 1.0,
      },

      // Long streaming test
      {
        text: "This is a comprehensive streaming test with a longer piece of text that will help us understand how streaming performance scales with content length. We want to measure the time from request initiation to first audio chunk, and analyze the stream-to-play delay to identify potential bottlenecks in the audio processing pipeline.",
        voice: "af_heart" as VoiceOption,
        speed: 1.0,
      },

      // Speed variation tests
      { text: "Speed test slow streaming", voice: "af_heart" as VoiceOption, speed: 0.8 },
      { text: "Speed test fast streaming", voice: "af_heart" as VoiceOption, speed: 1.5 },

      // Cache hit tests (repeat previous tests)
      { text: "Hello", voice: "af_heart" as VoiceOption, speed: 1.0 }, // Should hit cache
      {
        text: "This is a medium length sentence to test streaming performance and measure the time from request to first audio chunk.",
        voice: "af_heart" as VoiceOption,
        speed: 1.0,
      }, // Should hit cache
    ];

    await showToast({
      style: Toast.Style.Animated,
      title: "🚀 Running Streaming Benchmark",
      message: `Testing ${streamingTestCases.length} streaming scenarios...`,
    });

    for (let i = 0; i < streamingTestCases.length; i++) {
      const testCase = streamingTestCases[i];
      console.log(
        `\n🧪 Streaming Test ${i + 1}/${streamingTestCases.length}: "${testCase.text.substring(0, 30)}..."`
      );
      console.log(`   Voice: ${testCase.voice}, Speed: ${testCase.speed}`);

      const request: TTSRequestParams = {
        text: testCase.text,
        voice: testCase.voice,
        speed: testCase.speed,
        lang: "en-us",
        stream: true,
        format: "wav",
      };

      await this.benchmarkTTSRequest(request, serverUrl, (stage, elapsed) => {
        console.log(`   📊 ${stage}: ${elapsed.toFixed(2)}ms`);
      });

      // Small delay between tests
      await new Promise((resolve) => setTimeout(resolve, 200));
    }

    const stats = this.stopCollection();

    await showToast({
      style: Toast.Style.Success,
      title: "📊 Streaming Benchmark Complete",
      message: `Avg first audio: ${stats.averageFirstAudioPlayTime.toFixed(0)}ms | Cache hit: ${(stats.cacheHitRate * 100).toFixed(0)}%`,
    });

    return stats;
  }

  /**
   * Run benchmark suite with multiple test cases
   */
  async runBenchmarkSuite(serverUrl: string): Promise<PerformanceStats> {
    this.startCollection();

    const testCases = [
      // Short text tests
      { text: "Hello world", voice: "af_heart" as VoiceOption, speed: 1.0 },
      { text: "Quick test", voice: "bm_fable" as VoiceOption, speed: 1.0 },

      // Medium text tests
      {
        text: "This is a medium length sentence for testing TTS performance with caching.",
        voice: "af_heart" as VoiceOption,
        speed: 1.0,
      },
      {
        text: "Another medium sentence to test consistency.",
        voice: "af_heart" as VoiceOption,
        speed: 1.2,
      },

      // Long text test
      {
        text: "This is a longer piece of text that will be used to test the performance of the TTS system with larger payloads. It should provide insights into how the system scales with content length and how caching affects performance.",
        voice: "af_heart" as VoiceOption,
        speed: 1.0,
      },

      // Speed variations
      { text: "Speed test slow", voice: "af_heart" as VoiceOption, speed: 0.8 },
      { text: "Speed test fast", voice: "af_heart" as VoiceOption, speed: 1.5 },

      // Repeat tests for cache hit analysis
      { text: "Hello world", voice: "af_heart" as VoiceOption, speed: 1.0 }, // Should hit cache
      {
        text: "This is a medium length sentence for testing TTS performance with caching.",
        voice: "af_heart" as VoiceOption,
        speed: 1.0,
      }, // Should hit cache
    ];

    await showToast({
      style: Toast.Style.Animated,
      title: "🚀 Running TTS Benchmark",
      message: `Testing ${testCases.length} scenarios...`,
    });

    for (let i = 0; i < testCases.length; i++) {
      const testCase = testCases[i];
      console.log(`\n🧪 Test ${i + 1}/${testCases.length}: "${testCase.text.substring(0, 30)}..."`);

      const request: TTSRequestParams = {
        text: testCase.text,
        voice: testCase.voice,
        speed: testCase.speed,
        lang: "en-us",
        stream: true,
        format: "wav",
      };

      await this.benchmarkTTSRequest(request, serverUrl, (stage, elapsed) => {
        console.log(`  📊 ${stage}: ${elapsed.toFixed(2)}ms`);
      });

      // Small delay between tests
      await new Promise((resolve) => setTimeout(resolve, 100));
    }

    const stats = this.stopCollection();

    await showToast({
      style: Toast.Style.Success,
      title: "📊 Benchmark Complete",
      message: `Avg: ${stats.averageTotalTime.toFixed(0)}ms | Cache hit: ${(stats.cacheHitRate * 100).toFixed(0)}%`,
    });

    return stats;
  }

  /**
   * Generate comprehensive performance statistics
   */
  private generateStats(): PerformanceStats {
    if (this.metrics.length === 0) {
      return {
        totalRequests: 0,
        successfulRequests: 0,
        cacheHitRate: 0,
        averageSendTime: 0,
        averageLatency: 0,
        averageTTFB: 0,
        averageProcessingTime: 0,
        averageStreamToPlayDelay: 0,
        averageFirstAudioPlayTime: 0,
        averageTotalTime: 0,
        cachedResponseTime: 0,
        networkResponseTime: 0,
        cacheSpeedup: 0,
        averageChunkCount: 0,
        streamingEfficiency: 0,
        totalDataTransferred: 0,
        averageResponseSize: 0,
      };
    }

    const successful = this.metrics.filter((m) => m.success);
    const cacheHits = successful.filter((m) => m.cacheHit);
    const cacheMisses = successful.filter((m) => !m.cacheHit);

    const stats: PerformanceStats = {
      totalRequests: this.metrics.length,
      successfulRequests: successful.length,
      cacheHitRate: successful.length > 0 ? cacheHits.length / successful.length : 0,

      averageSendTime: this.average(successful.map((m) => m.sendTime)),
      averageLatency: this.average(successful.map((m) => m.networkLatency)),
      averageTTFB: this.average(successful.map((m) => m.timeToFirstByte)),
      averageProcessingTime: this.average(successful.map((m) => m.processingTime)),
      averageStreamToPlayDelay: this.average(successful.map((m) => m.streamToPlayDelay)),
      averageFirstAudioPlayTime: this.average(successful.map((m) => m.firstAudioPlayTime)),
      averageTotalTime: this.average(successful.map((m) => m.totalResponseTime)),

      cachedResponseTime:
        cacheHits.length > 0 ? this.average(cacheHits.map((m) => m.totalResponseTime)) : 0,
      networkResponseTime:
        cacheMisses.length > 0 ? this.average(cacheMisses.map((m) => m.totalResponseTime)) : 0,
      cacheSpeedup: 0, // Will calculate below

      averageChunkCount: this.average(successful.map((m) => m.chunkCount)),
      streamingEfficiency: 0, // Will calculate below

      totalDataTransferred: successful.reduce((sum, m) => sum + (m.audioDataSize || 0), 0),
      averageResponseSize: this.average(successful.map((m) => m.audioDataSize || 0)),
    };

    // Calculate cache speedup
    if (stats.cachedResponseTime > 0 && stats.networkResponseTime > 0) {
      stats.cacheSpeedup = stats.networkResponseTime / stats.cachedResponseTime;
    }

    // Calculate streaming efficiency
    if (stats.averageTotalTime > 0 && stats.averageTotalTime > 0) {
      stats.streamingEfficiency = stats.averageTotalTime / stats.averageTotalTime;
    }

    return stats;
  }

  /**
   * Calculate average of numeric array
   */
  private average(numbers: number[]): number {
    if (numbers.length === 0) return 0;
    return numbers.reduce((sum, n) => sum + n, 0) / numbers.length;
  }

  /**
   * Get detailed metrics for analysis
   */
  getMetrics(): TTSPerformanceMetrics[] {
    return [...this.metrics];
  }

  /**
   * Export metrics as JSON for external analysis
   */
  exportMetrics(): string {
    return JSON.stringify(
      {
        timestamp: new Date().toISOString(),
        metrics: this.metrics,
        stats: this.generateStats(),
      },
      null,
      2
    );
  }

  /**
   * Print detailed performance report to console
   */
  printReport(stats: PerformanceStats): void {
    console.log("\n" + "=".repeat(60));
    console.log("📊 TTS PERFORMANCE BENCHMARK REPORT");
    console.log("=".repeat(60));

    console.log(`\n📈 OVERALL STATISTICS:`);
    console.log(`   Total Requests: ${stats.totalRequests}`);
    console.log(
      `   Successful: ${stats.successfulRequests} (${((stats.successfulRequests / stats.totalRequests) * 100).toFixed(1)}%)`
    );
    console.log(`   Cache Hit Rate: ${(stats.cacheHitRate * 100).toFixed(1)}%`);

    console.log(`\n⏱️  TIMING PERFORMANCE:`);
    console.log(`   Average Send Time: ${stats.averageSendTime.toFixed(2)}ms`);
    console.log(`   Average Network Latency: ${stats.averageLatency.toFixed(2)}ms`);
    console.log(`   Average Time to First Byte: ${stats.averageTTFB.toFixed(2)}ms`);
    console.log(`   Average Processing Time: ${stats.averageProcessingTime.toFixed(2)}ms`);
    console.log(`   Average Stream-to-Play Delay: ${stats.averageStreamToPlayDelay.toFixed(2)}ms`);
    console.log(
      `   Average First Audio Play Time: ${stats.averageFirstAudioPlayTime.toFixed(2)}ms`
    );
    console.log(`   Average Total Response Time: ${stats.averageTotalTime.toFixed(2)}ms`);

    console.log(`\n🚀 CACHE PERFORMANCE:`);
    console.log(`   Cached Response Time: ${stats.cachedResponseTime.toFixed(2)}ms`);
    console.log(`   Network Response Time: ${stats.networkResponseTime.toFixed(2)}ms`);
    if (stats.cacheSpeedup > 0) {
      console.log(`   Cache Speedup: ${stats.cacheSpeedup.toFixed(2)}x faster`);
      console.log(
        `   Time Saved: ${(stats.networkResponseTime - stats.cachedResponseTime).toFixed(2)}ms per cached request`
      );
    }

    console.log(`\n🎧 STREAMING PERFORMANCE:`);
    console.log(`   Average Chunk Count: ${stats.averageChunkCount.toFixed(0)}`);
    if (stats.averageTotalTime > 0 && stats.averageTotalTime > 0) {
      console.log(`   Streaming Efficiency: ${stats.streamingEfficiency.toFixed(2)}x faster`);
    }

    console.log(`\n📦 DATA TRANSFER:`);
    console.log(`   Total Data Transferred: ${(stats.totalDataTransferred / 1024).toFixed(2)} KB`);
    console.log(`   Average Response Size: ${(stats.averageResponseSize / 1024).toFixed(2)} KB`);

    console.log("\n" + "=".repeat(60));
  }
}

// Export singleton instance
export const ttsBenchmark = new TTSBenchmark();
export type { TTSPerformanceMetrics, PerformanceStats };
