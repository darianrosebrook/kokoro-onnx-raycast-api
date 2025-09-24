/**
 * Centralized Performance Tracking System
 *
 * This module provides a unified performance tracking system that creates
 * a consistent, trackable flow from text input to audio playback.
 *
 * @author @darianrosebrook
 * @version 1.0.0
 */

import { performance } from "perf_hooks";

export interface PerformanceEvent {
  requestId: string;
  stage: string;
  timestamp: number;
  duration?: number;
  metadata: Record<string, unknown>;
}

export interface RequestFlow {
  requestId: string;
  startTime: number;
  events: PerformanceEvent[];
  text: string;
  voice: string;
  speed: number;
  completed: boolean;
  totalDuration?: number;
}

export interface PerformanceMetrics {
  // Core timing metrics
  requestStartToFirstByte: number; // Total time from request start to first server response
  serverProcessingTime: number; // Time server took to process request
  firstByteToFirstAudio: number; // Time from first byte to first audio chunk
  totalTimeToFirstAudio: number; // End-to-end TTFA (request start to first audio)

  // Streaming metrics
  totalStreamingTime: number; // Total time from first chunk to last chunk
  audioGenerationTime: number; // Time to generate all audio data
  chunkCount: number; // Total number of audio chunks
  averageChunkTime: number; // Average time between chunks
  streamingEfficiency: number; // audio_duration / streaming_time

  // Quality metrics
  audioDuration: number; // Actual audio duration in seconds
  cacheHit: boolean; // Whether request was served from cache
  providerUsed: string; // Which inference provider was used

  // Error tracking
  errors: string[]; // Any errors encountered
  warnings: string[]; // Any warnings encountered
}

export class PerformanceTracker {
  private static instance: PerformanceTracker;
  private activeFlows: Map<string, RequestFlow> = new Map();
  private completedFlows: RequestFlow[] = [];

  private constructor() {}

  static getInstance(): PerformanceTracker {
    if (!PerformanceTracker.instance) {
      PerformanceTracker.instance = new PerformanceTracker();
    }
    return PerformanceTracker.instance;
  }

  /**
   * Start tracking a new TTS request
   */
  startRequest(requestId: string, text: string, voice: string, speed: number): void {
    const flow: RequestFlow = {
      requestId,
      startTime: performance.now(),
      events: [],
      text,
      voice,
      speed,
      completed: false,
    };

    this.activeFlows.set(requestId, flow);

    this.logEvent(requestId, "REQUEST_START", {
      textLength: text.length,
      voice,
      speed,
    });
  }

  /**
   * Record a performance event
   */
  logEvent(requestId: string, stage: string, metadata: Record<string, unknown> = {}): void {
    const flow = this.activeFlows.get(requestId);
    if (!flow) {
      console.warn(`PerformanceTracker: No active flow for request ${requestId}`);
      return;
    }

    const event: PerformanceEvent = {
      requestId,
      stage,
      timestamp: performance.now(),
      metadata,
    };

    flow.events.push(event);

    // Log with consistent format
    console.log(`[PERF:${requestId}] ${stage}`, {
      timestamp: new Date().toISOString(),
      stage,
      ...metadata,
    });
  }

  /**
   * Complete a request and calculate final metrics
   */
  completeRequest(requestId: string): PerformanceMetrics | null {
    const flow = this.activeFlows.get(requestId);
    if (!flow) {
      console.warn(`PerformanceTracker: No active flow for request ${requestId}`);
      return null;
    }

    flow.completed = true;
    flow.totalDuration = performance.now() - flow.startTime;

    const metrics = this.calculateMetrics(flow);

    // Move to completed flows
    this.activeFlows.delete(requestId);
    this.completedFlows.push(flow);

    // Log final summary
    this.logFinalSummary(requestId, metrics);

    return metrics;
  }

  /**
   * Calculate performance metrics from flow events
   */
  private calculateMetrics(flow: RequestFlow): PerformanceMetrics {
    const events = flow.events;
    const startTime = flow.startTime;

    // Find key timing events
    const _requestStart = events.find((e) => e.stage === "REQUEST_START");
    const firstByte = events.find((e) => e.stage === "FIRST_BYTE_RECEIVED");
    const firstAudio = events.find((e) => e.stage === "FIRST_AUDIO_CHUNK");
    const lastChunk = events.find((e) => e.stage === "LAST_AUDIO_CHUNK");
    const serverProcessing = events.find((e) => e.stage === "SERVER_PROCESSING_COMPLETE");

    // Calculate core metrics
    const requestStartToFirstByte = firstByte ? firstByte.timestamp - startTime : 0;
    const firstByteToFirstAudio =
      firstAudio && firstByte ? firstAudio.timestamp - firstByte.timestamp : 0;
    const totalTimeToFirstAudio = firstAudio ? firstAudio.timestamp - startTime : 0;
    const serverProcessingTime = serverProcessing ? serverProcessing.metadata.processingTimeMs : 0;

    // Calculate streaming metrics
    const chunkCount = events.filter((e) => e.stage === "AUDIO_CHUNK_RECEIVED").length;
    const audioDurationMs = (lastChunk?.metadata.audioDurationMs as number) || 0;
    const audioDuration = audioDurationMs / 1000;

    // Use streaming duration from metadata if available, otherwise calculate from timestamps
    let streamingEfficiency = 0;
    let totalStreamingTime = 0;
    if (
      lastChunk &&
      lastChunk.metadata.streamingDurationMs &&
      typeof lastChunk.metadata.streamingDurationMs === "number"
    ) {
      // Use the streaming duration provided in metadata
      totalStreamingTime = lastChunk.metadata.streamingDurationMs as number;
      const streamingTimeSeconds = totalStreamingTime / 1000;
      streamingEfficiency = audioDuration / streamingTimeSeconds;
    } else if (lastChunk && firstAudio) {
      // Fallback to calculating from timestamps
      totalStreamingTime = (lastChunk.timestamp - firstAudio.timestamp) * 1000;
      const streamingTimeSeconds = totalStreamingTime / 1000;
      streamingEfficiency = audioDuration / streamingTimeSeconds;
    }

    // Calculate average chunk time
    const chunkEvents = events.filter((e) => e.stage === "AUDIO_CHUNK_RECEIVED");
    let averageChunkTime = 0;
    if (chunkEvents.length > 1) {
      const chunkTimes = [];
      for (let i = 1; i < chunkEvents.length; i++) {
        chunkTimes.push(chunkEvents[i].timestamp - chunkEvents[i - 1].timestamp);
      }
      averageChunkTime = chunkTimes.reduce((a, b) => a + b, 0) / chunkTimes.length;
    }

    // Extract metadata
    const cacheHit = events.some((e) => e.stage === "CACHE_HIT");
    const providerUsed =
      events.find((e) => e.stage === "INFERENCE_START")?.metadata.provider || "unknown";

    // Collect errors and warnings
    const errors = events.filter((e) => e.stage === "ERROR").map((e) => e.metadata.error as string);
    const warnings = events
      .filter((e) => e.stage === "WARNING")
      .map((e) => e.metadata.warning as string);

    return {
      requestStartToFirstByte: requestStartToFirstByte as number,
      serverProcessingTime: serverProcessingTime as number,
      firstByteToFirstAudio: firstByteToFirstAudio as number,
      totalTimeToFirstAudio: totalTimeToFirstAudio as number,
      totalStreamingTime: totalStreamingTime as number,
      audioGenerationTime: serverProcessingTime as number,
      chunkCount: chunkCount as number,
      averageChunkTime: averageChunkTime as number,
      streamingEfficiency: streamingEfficiency as number,
      audioDuration: audioDuration as number,
      cacheHit: cacheHit as boolean,
      providerUsed: providerUsed as string,
      errors,
      warnings,
    };
  }

  /**
   * Log final performance summary
   */
  private logFinalSummary(requestId: string, metrics: PerformanceMetrics): void {
    const status = metrics.totalTimeToFirstAudio <= 800 ? "✅ PASS" : " FAIL";

    console.log(`[PERF:${requestId}] FINAL_SUMMARY`, {
      timestamp: new Date().toISOString(),
      status,
      metrics: {
        totalTimeToFirstAudio: `${metrics.totalTimeToFirstAudio.toFixed(2)}ms`,
        serverProcessingTime: `${metrics.serverProcessingTime.toFixed(2)}ms`,
        streamingEfficiency: `${(metrics.streamingEfficiency * 100).toFixed(1)}%`,
        chunkCount: metrics.chunkCount,
        audioDuration: `${metrics.audioDuration.toFixed(2)}s`,
        cacheHit: metrics.cacheHit,
        providerUsed: metrics.providerUsed,
      },
      errors: metrics.errors.length > 0 ? metrics.errors : undefined,
      warnings: metrics.warnings.length > 0 ? metrics.warnings : undefined,
    });
  }

  /**
   * Get all completed flows for analysis
   */
  getCompletedFlows(): RequestFlow[] {
    return [...this.completedFlows];
  }

  /**
   * Clear completed flows (for memory management)
   */
  clearCompletedFlows(): void {
    this.completedFlows = [];
  }
}
