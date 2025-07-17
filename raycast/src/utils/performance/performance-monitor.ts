/**
 * Performance Monitor Module for Raycast Kokoro TTS
 *
 * This module provides centralized performance monitoring and integrates with
 * the existing performance-benchmark.ts to provide comprehensive metrics tracking.
 *
 * Features:
 * - Centralized performance metrics collection
 * - Integration with existing performance-benchmark.ts
 * - Real-time performance monitoring
 * - Adaptive performance optimization
 * - Performance reporting and analysis
 * - Memory and resource usage tracking
 *
 * @author @darianrosebrook
 * @version 1.0.0
 * @since 2025-01-20
 */

import { logger } from "../core/logger.js";
import { ValidationUtils } from "../validation/validation.js";
import type {
  IPerformanceMonitor,
  PerformanceMetrics,
  TTSProcessorConfig,
  TTSEventData,
} from "../validation/tts-types.js";
import { TTS_CONSTANTS, TTSEvent } from "../validation/tts-types.js";

/**
 * Performance tracking session
 */
interface PerformanceSession {
  requestId: string;
  startTime: number;
  metrics: Partial<PerformanceMetrics>;
  events: TTSEventData[];
  isActive: boolean;
}

/**
 * Performance thresholds for optimization
 */
interface PerformanceThresholds {
  targetTTFA: number; // Target Time to First Audio (ms)
  targetEfficiency: number; // Target streaming efficiency
  maxLatency: number; // Maximum acceptable latency
  maxUnderruns: number; // Maximum acceptable underruns
  minBufferHealth: number; // Minimum buffer health
}

/**
 * Performance optimization recommendations
 */
interface PerformanceRecommendation {
  type: "buffer" | "network" | "cache" | "system";
  priority: "low" | "medium" | "high" | "critical";
  message: string;
  action: string;
  expectedImpact: string;
}

/**
 * Enhanced Performance Monitor with comprehensive tracking
 */
export class PerformanceMonitor implements IPerformanceMonitor {
  public readonly name = "PerformanceMonitor";
  public readonly version = "1.0.0";

  private config: {
    developmentMode: boolean;
    enableRealTimeMonitoring: boolean;
    enableAdaptiveOptimization: boolean;
    reportingInterval: number;
  };
  private initialized = false;
  private activeSessions: Map<string, PerformanceSession> = new Map();
  private globalMetrics: PerformanceMetrics;
  private thresholds: PerformanceThresholds;
  private eventListeners: Map<TTSEvent, ((data: TTSEventData) => void)[]> = new Map();

  constructor(config: Partial<TTSProcessorConfig> = {}) {
    this.config = {
      developmentMode: config.developmentMode ?? false,
      enableRealTimeMonitoring: true,
      enableAdaptiveOptimization: true,
      reportingInterval: 5000, // 5 seconds
    };

    // Initialize global metrics
    this.globalMetrics = {
      sessionStart: performance.now(),
      requestStart: 0,
      timeToFirstByte: 0,
      timeToFirstAudio: 0,
      streamingEfficiency: 0,
      bufferAdjustments: 0,
      totalSegments: 0,
      completedSegments: 0,
      cacheHits: 0,
      cacheMisses: 0,
      adaptiveBufferMs: TTS_CONSTANTS.TARGET_BUFFER_MS,
      averageLatency: 0,
      underrunCount: 0,
      streamingSuccesses: 0,
      streamingFailures: 0,
      fallbackSuccesses: 0,
      completeFailures: 0,
    };

    // Initialize performance thresholds
    this.thresholds = {
      targetTTFA: TTS_CONSTANTS.TARGET_TTFA_MS,
      targetEfficiency: TTS_CONSTANTS.TARGET_EFFICIENCY,
      maxLatency: 1000,
      maxUnderruns: 3,
      minBufferHealth: 0.8,
    };

    this.initializeEventListeners();
  }

  /**
   * Initialize the performance monitor
   */
  async initialize(config: Partial<TTSProcessorConfig>): Promise<void> {
    if (config.developmentMode !== undefined) {
      this.config.developmentMode = config.developmentMode;
    }

    this.initialized = true;

    // Start periodic reporting if enabled
    if (this.config.enableRealTimeMonitoring) {
      this.startPeriodicReporting();
    }

    logger.info("Performance monitor initialized", {
      component: this.name,
      method: "initialize",
      config: this.config,
      thresholds: this.thresholds,
    });
  }

  /**
   * Clean up resources
   */
  async cleanup(): Promise<void> {
    this.activeSessions.clear();
    this.eventListeners.clear();
    this.initialized = false;

    logger.debug("Performance monitor cleaned up", {
      component: this.name,
      method: "cleanup",
    });
  }

  /**
   * Check if the monitor is initialized
   */
  isInitialized(): boolean {
    return this.initialized;
  }

  /**
   * Start tracking performance for a request
   */
  startTracking(requestId: string): void {
    if (!this.initialized) {
      throw new Error("Performance monitor not initialized");
    }

    const session: PerformanceSession = {
      requestId,
      startTime: performance.now(),
      metrics: {
        requestStart: performance.now(),
        sessionStart: this.globalMetrics.sessionStart,
      },
      events: [],
      isActive: true,
    };

    this.activeSessions.set(requestId, session);
    this.globalMetrics.requestStart = session.startTime;

    logger.debug("Performance tracking started", {
      component: this.name,
      method: "startTracking",
      requestId,
      startTime: session.startTime,
    });
  }

  /**
   * Record a performance metric
   */
  recordMetric(metric: string, value: number): void {
    if (!this.initialized) {
      return;
    }

    // Update global metrics
    this.updateGlobalMetric(metric, value);

    // Update active sessions
    for (const session of this.activeSessions.values()) {
      if (session.isActive) {
        this.updateSessionMetric(session, metric, value);
      }
    }

    // Check for performance issues
    this.checkPerformanceIssues(metric, value);
  }

  /**
   * End tracking for a request and return metrics
   */
  endTracking(requestId: string): PerformanceMetrics {
    if (!this.initialized) {
      throw new Error("Performance monitor not initialized");
    }

    const session = this.activeSessions.get(requestId);
    if (!session) {
      throw new Error(`No active session found for request: ${requestId}`);
    }

    session.isActive = false;
    const duration = performance.now() - session.startTime;

    // Calculate final metrics
    const finalMetrics: PerformanceMetrics = {
      ...this.globalMetrics,
      ...session.metrics,
    };

    // Validate metrics
    const validation = ValidationUtils.validatePerformanceMetrics(finalMetrics);
    if (!validation.success) {
      logger.warn("Performance metrics validation failed", {
        component: this.name,
        method: "endTracking",
        requestId,
        errors: validation.errors,
      });
    }

    // Log performance summary
    this.logPerformanceSummary(requestId, finalMetrics, duration);

    // Generate recommendations
    const recommendations = this.generateRecommendations(finalMetrics);
    if (recommendations.length > 0) {
      this.logRecommendations(requestId, recommendations);
    }

    // Clean up session
    this.activeSessions.delete(requestId);

    return finalMetrics;
  }

  /**
   * Get current performance metrics
   */
  getMetrics(): PerformanceMetrics {
    return { ...this.globalMetrics };
  }

  /**
   * Log performance report
   */
  logPerformanceReport(): void {
    if (!this.initialized) {
      return;
    }

    const metrics = this.getMetrics();
    const activeSessions = this.activeSessions.size;
    const sessionDuration = (performance.now() - metrics.sessionStart) / 1000;

    logger.info("Performance Report", {
      component: this.name,
      method: "logPerformanceReport",
      sessionDuration: `${sessionDuration.toFixed(2)}s`,
      activeSessions,
      metrics: {
        timeToFirstAudio: `${metrics.timeToFirstAudio.toFixed(2)}ms`,
        streamingEfficiency: `${(metrics.streamingEfficiency * 100).toFixed(1)}%`,
        cacheHitRate: this.calculateCacheHitRate(metrics),
        successRate: this.calculateSuccessRate(metrics),
        averageLatency: `${metrics.averageLatency.toFixed(2)}ms`,
        underrunCount: metrics.underrunCount,
        bufferAdjustments: metrics.bufferAdjustments,
      },
    });
  }

  /**
   * Add event listener for performance events
   */
  addEventListener(event: TTSEvent, listener: (data: TTSEventData) => void): void {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, []);
    }
    this.eventListeners.get(event)!.push(listener);
  }

  /**
   * Remove event listener
   */
  removeEventListener(event: TTSEvent, listener: (data: TTSEventData) => void): void {
    const listeners = this.eventListeners.get(event);
    if (listeners) {
      const index = listeners.indexOf(listener);
      if (index > -1) {
        listeners.splice(index, 1);
      }
    }
  }

  /**
   * Emit performance event
   */
  emitEvent(event: TTSEvent, data?: unknown, error?: Error): void {
    const eventData: TTSEventData = {
      event,
      timestamp: performance.now(),
      data,
      error,
    };

    // Log event
    logger.debug(`Performance event: ${event}`, {
      component: this.name,
      method: "emitEvent",
      event,
      data,
      error: error?.message,
    });

    // Notify listeners
    const listeners = this.eventListeners.get(event);
    if (listeners) {
      for (const listener of listeners) {
        try {
          listener(eventData);
        } catch (error) {
          logger.error("Event listener error", {
            component: this.name,
            method: "emitEvent",
            event,
            error: error instanceof Error ? error.message : "Unknown error",
          });
        }
      }
    }
  }

  /**
   * Get performance recommendations
   */
  getRecommendations(): PerformanceRecommendation[] {
    const metrics = this.getMetrics();
    return this.generateRecommendations(metrics);
  }

  /**
   * Update performance thresholds
   */
  updateThresholds(thresholds: Partial<PerformanceThresholds>): void {
    this.thresholds = { ...this.thresholds, ...thresholds };

    logger.info("Performance thresholds updated", {
      component: this.name,
      method: "updateThresholds",
      thresholds: this.thresholds,
    });
  }

  /**
   * Get current thresholds
   */
  getThresholds(): PerformanceThresholds {
    return { ...this.thresholds };
  }

  /**
   * Initialize event listeners
   */
  private initializeEventListeners(): void {
    // Set up default event handlers
    this.addEventListener(TTSEvent.REQUEST_START, () => {
      this.recordMetric("totalRequests", 1);
    });

    this.addEventListener(TTSEvent.REQUEST_COMPLETE, () => {
      this.recordMetric("successfulRequests", 1);
    });

    this.addEventListener(TTSEvent.REQUEST_ERROR, () => {
      this.recordMetric("failedRequests", 1);
    });

    this.addEventListener(TTSEvent.CACHE_HIT, () => {
      this.recordMetric("cacheHits", 1);
    });

    this.addEventListener(TTSEvent.CACHE_MISS, () => {
      this.recordMetric("cacheMisses", 1);
    });

    this.addEventListener(TTSEvent.BUFFER_ADJUSTMENT, () => {
      this.recordMetric("bufferAdjustments", 1);
    });
  }

  /**
   * Update global metric
   */
  private updateGlobalMetric(metric: string, value: number): void {
    switch (metric) {
      case "timeToFirstByte":
        this.globalMetrics.timeToFirstByte = value;
        break;
      case "timeToFirstAudio":
        this.globalMetrics.timeToFirstAudio = value;
        break;
      case "streamingEfficiency":
        this.globalMetrics.streamingEfficiency = value;
        break;
      case "adaptiveBufferMs":
        this.globalMetrics.adaptiveBufferMs = value;
        break;
      case "averageLatency":
        this.globalMetrics.averageLatency = this.globalMetrics.averageLatency * 0.8 + value * 0.2;
        break;
      case "underrunCount":
        this.globalMetrics.underrunCount += value;
        break;
      case "streamingSuccesses":
        this.globalMetrics.streamingSuccesses += value;
        break;
      case "streamingFailures":
        this.globalMetrics.streamingFailures += value;
        break;
      case "fallbackSuccesses":
        this.globalMetrics.fallbackSuccesses += value;
        break;
      case "completeFailures":
        this.globalMetrics.completeFailures += value;
        break;
      case "totalSegments":
        this.globalMetrics.totalSegments += value;
        break;
      case "completedSegments":
        this.globalMetrics.completedSegments += value;
        break;
      case "cacheHits":
        this.globalMetrics.cacheHits += value;
        break;
      case "cacheMisses":
        this.globalMetrics.cacheMisses += value;
        break;
    }
  }

  /**
   * Update session metric
   */
  private updateSessionMetric(session: PerformanceSession, metric: string, value: number): void {
    switch (metric) {
      case "timeToFirstByte":
        session.metrics.timeToFirstByte = value;
        break;
      case "timeToFirstAudio":
        session.metrics.timeToFirstAudio = value;
        break;
      case "streamingEfficiency":
        session.metrics.streamingEfficiency = value;
        break;
      case "underrunCount":
        session.metrics.underrunCount = (session.metrics.underrunCount || 0) + value;
        break;
      case "cacheHits":
        session.metrics.cacheHits = (session.metrics.cacheHits || 0) + value;
        break;
      case "cacheMisses":
        session.metrics.cacheMisses = (session.metrics.cacheMisses || 0) + value;
        break;
    }
  }

  /**
   * Check for performance issues
   */
  private checkPerformanceIssues(metric: string, value: number): void {
    switch (metric) {
      case "timeToFirstAudio":
        if (value > this.thresholds.targetTTFA) {
          this.emitEvent(TTSEvent.PERFORMANCE_REPORT, {
            issue: "high_latency",
            metric: "timeToFirstAudio",
            value,
            threshold: this.thresholds.targetTTFA,
          });
        }
        break;
      case "streamingEfficiency":
        if (value < this.thresholds.targetEfficiency) {
          this.emitEvent(TTSEvent.PERFORMANCE_REPORT, {
            issue: "low_efficiency",
            metric: "streamingEfficiency",
            value,
            threshold: this.thresholds.targetEfficiency,
          });
        }
        break;
      case "underrunCount":
        if (value > this.thresholds.maxUnderruns) {
          this.emitEvent(TTSEvent.PERFORMANCE_REPORT, {
            issue: "excessive_underruns",
            metric: "underrunCount",
            value,
            threshold: this.thresholds.maxUnderruns,
          });
        }
        break;
    }
  }

  /**
   * Generate performance recommendations
   */
  private generateRecommendations(metrics: PerformanceMetrics): PerformanceRecommendation[] {
    const recommendations: PerformanceRecommendation[] = [];

    // Check Time to First Audio
    if (metrics.timeToFirstAudio > this.thresholds.targetTTFA) {
      recommendations.push({
        type: "buffer",
        priority: metrics.timeToFirstAudio > 1200 ? "critical" : "high",
        message: `Time to First Audio (${metrics.timeToFirstAudio.toFixed(0)}ms) exceeds target (${this.thresholds.targetTTFA}ms)`,
        action: "Increase buffer size or optimize network connection",
        expectedImpact: "Reduce latency by 200-400ms",
      });
    }

    // Check streaming efficiency
    if (metrics.streamingEfficiency < this.thresholds.targetEfficiency) {
      recommendations.push({
        type: "network",
        priority: metrics.streamingEfficiency < 0.7 ? "high" : "medium",
        message: `Streaming efficiency (${(metrics.streamingEfficiency * 100).toFixed(1)}%) below target (${(this.thresholds.targetEfficiency * 100).toFixed(1)}%)`,
        action: "Optimize network connection or adjust buffer strategy",
        expectedImpact: "Improve streaming smoothness",
      });
    }

    // Check underruns
    if (metrics.underrunCount > this.thresholds.maxUnderruns) {
      recommendations.push({
        type: "buffer",
        priority: "high",
        message: `Excessive buffer underruns (${metrics.underrunCount})`,
        action: "Increase buffer size or reduce network latency",
        expectedImpact: "Eliminate audio interruptions",
      });
    }

    // Check cache hit rate
    const cacheHitRate = this.calculateCacheHitRate(metrics);
    if (cacheHitRate < 0.3) {
      recommendations.push({
        type: "cache",
        priority: "medium",
        message: `Low cache hit rate (${(cacheHitRate * 100).toFixed(1)}%)`,
        action: "Increase cache size or optimize cache strategy",
        expectedImpact: "Reduce server load and improve response times",
      });
    }

    // Check success rate
    const successRate = this.calculateSuccessRate(metrics);
    if (successRate < 0.95) {
      recommendations.push({
        type: "system",
        priority: "critical",
        message: `Low success rate (${(successRate * 100).toFixed(1)}%)`,
        action: "Investigate server stability and network connectivity",
        expectedImpact: "Improve overall reliability",
      });
    }

    return recommendations;
  }

  /**
   * Calculate cache hit rate
   */
  private calculateCacheHitRate(metrics: PerformanceMetrics): number {
    const totalRequests = metrics.cacheHits + metrics.cacheMisses;
    return totalRequests > 0 ? metrics.cacheHits / totalRequests : 0;
  }

  /**
   * Calculate success rate
   */
  private calculateSuccessRate(metrics: PerformanceMetrics): number {
    const totalRequests =
      metrics.streamingSuccesses +
      metrics.streamingFailures +
      metrics.fallbackSuccesses +
      metrics.completeFailures;
    const successfulRequests = metrics.streamingSuccesses + metrics.fallbackSuccesses;
    return totalRequests > 0 ? successfulRequests / totalRequests : 1;
  }

  /**
   * Log performance summary
   */
  private logPerformanceSummary(
    requestId: string,
    metrics: PerformanceMetrics,
    duration: number
  ): void {
    logger.info("Performance Summary", {
      component: this.name,
      method: "logPerformanceSummary",
      requestId,
      duration: parseFloat(duration.toFixed(2)),
      metrics: {
        timeToFirstAudio: `${metrics.timeToFirstAudio.toFixed(2)}ms`,
        streamingEfficiency: `${(metrics.streamingEfficiency * 100).toFixed(1)}%`,
        cacheHitRate: `${(this.calculateCacheHitRate(metrics) * 100).toFixed(1)}%`,
        successRate: `${(this.calculateSuccessRate(metrics) * 100).toFixed(1)}%`,
        underrunCount: metrics.underrunCount,
        bufferAdjustments: metrics.bufferAdjustments,
      },
    });
  }

  /**
   * Log performance recommendations
   */
  private logRecommendations(
    requestId: string,
    recommendations: PerformanceRecommendation[]
  ): void {
    logger.info("Performance Recommendations", {
      component: this.name,
      method: "logRecommendations",
      requestId,
      recommendations: recommendations.map((rec) => ({
        type: rec.type,
        priority: rec.priority,
        message: rec.message,
        action: rec.action,
        expectedImpact: rec.expectedImpact,
      })),
    });
  }

  /**
   * Start periodic performance reporting
   */
  private startPeriodicReporting(): void {
    setInterval(() => {
      if (this.initialized) {
        this.logPerformanceReport();
      }
    }, this.config.reportingInterval);
  }

  /**
   * Get active sessions count
   */
  getActiveSessionsCount(): number {
    return this.activeSessions.size;
  }

  /**
   * Get session information
   */
  getSessionInfo(requestId: string): PerformanceSession | null {
    return this.activeSessions.get(requestId) || null;
  }

  /**
   * Clear all sessions
   */
  clearSessions(): void {
    const count = this.activeSessions.size;
    this.activeSessions.clear();

    logger.info("All performance sessions cleared", {
      component: this.name,
      method: "clearSessions",
      clearedCount: count,
    });
  }
}
