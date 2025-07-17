/**
 * Performance System Integration for Raycast Kokoro TTS
 *
 * This module provides integration between the performance monitor,
 * adaptive buffer manager, and performance benchmark systems to create
 * a comprehensive performance optimization ecosystem.
 *
 * Features:
 * - Unified performance monitoring across all systems
 * - Automatic buffer optimization based on real-time metrics
 * - Benchmark-driven configuration updates
 * - Continuous performance improvement
 *
 * @author @darianrosebrook
 * @version 1.0.0
 * @since 2025-07-17
 */

import { PerformanceMonitor } from "./performance-monitor.js";
import { AdaptiveBufferManager } from "../tts/streaming/adaptive-buffer-manager.js";
import { TTSBenchmark } from "./performance-benchmark.js";
import { logger } from "../core/logger.js";
import type { TTSProcessorConfig, BufferConfig } from "../validation/tts-types.js";

/**
 * Integrated performance management system
 */
export class PerformanceIntegration {
  private readonly name = "PerformanceIntegration";
  private performanceMonitor: PerformanceMonitor;
  private adaptiveBufferManager: AdaptiveBufferManager;
  private benchmark: TTSBenchmark;
  private initialized = false;

  constructor(config: Partial<TTSProcessorConfig> = {}) {
    // Initialize performance monitor
    this.performanceMonitor = new PerformanceMonitor(config);

    // Initialize adaptive buffer manager
    this.adaptiveBufferManager = new AdaptiveBufferManager();

    // Initialize benchmark system
    this.benchmark = new TTSBenchmark();

    // Set up integrations
    this.setupIntegrations();

    logger.consoleInfo("Performance integration system created", {
      component: this.name,
      method: "constructor",
    });
  }

  /**
   * Initialize the integrated performance system
   */
  async initialize(config: Partial<TTSProcessorConfig>): Promise<void> {
    // Initialize performance monitor
    await this.performanceMonitor.initialize(config);

    // Initialize adaptive buffer manager
    await this.adaptiveBufferManager.initialize(config);

    this.initialized = true;

    logger.consoleInfo("Performance integration system initialized", {
      component: this.name,
      method: "initialize",
    });
  }

  /**
   * Set up cross-system integrations
   */
  private setupIntegrations(): void {
    // Connect adaptive buffer manager to performance monitor
    this.adaptiveBufferManager.setPerformanceMonitor(this.performanceMonitor);

    // Connect benchmark system to both monitor and buffer manager
    this.benchmark.setPerformanceMonitor(this.performanceMonitor);
    this.benchmark.setAdaptiveBufferManager(this.adaptiveBufferManager);

    logger.debug("Cross-system integrations established", {
      component: this.name,
      method: "setupIntegrations",
    });
  }

  /**
   * Get current buffer configuration
   */
  getBufferConfig(): BufferConfig {
    return this.adaptiveBufferManager.getBufferConfig();
  }

  /**
   * Get current performance metrics
   */
  getPerformanceMetrics() {
    return this.performanceMonitor.getMetrics();
  }

  /**
   * Get performance recommendations
   */
  getRecommendations() {
    return this.performanceMonitor.getRecommendations();
  }

  /**
   * Update buffer based on performance metrics
   */
  updateBuffer(metrics: {
    timeToFirstAudio: number;
    underrunCount: number;
    streamingEfficiency: number;
  }): void {
    this.adaptiveBufferManager.updateBuffer(metrics);
  }

  /**
   * Run performance benchmark and update configurations
   */
  async runBenchmark(serverUrl: string): Promise<{
    stats: any;
    optimalConfig: any;
  }> {
    // Run benchmark suite
    const stats = await this.benchmark.runBenchmarkSuite(serverUrl);

    // Generate optimal configuration from benchmark results
    const optimalConfig = this.benchmark.generateOptimalBufferConfig();

    logger.consoleInfo("Benchmark completed and configurations updated", {
      component: this.name,
      method: "runBenchmark",
      stats,
      optimalConfig,
    });

    return { stats, optimalConfig };
  }

  /**
   * Get integrated performance report
   */
  getIntegratedReport(): {
    bufferConfig: BufferConfig;
    performanceMetrics: any;
    recommendations: any[];
    health: {
      status: string;
      score: number;
    };
  } {
    const bufferConfig = this.getBufferConfig();
    const performanceMetrics = this.getPerformanceMetrics();
    const recommendations = this.getRecommendations();
    const bufferHealth = this.adaptiveBufferManager.getBufferHealth({
      timeToFirstAudio: performanceMetrics.timeToFirstAudio,
      underrunCount: performanceMetrics.underrunCount,
      streamingEfficiency: performanceMetrics.streamingEfficiency,
    });

    return {
      bufferConfig,
      performanceMetrics,
      recommendations,
      health: bufferHealth,
    };
  }

  /**
   * Clean up resources
   */
  async cleanup(): Promise<void> {
    await this.performanceMonitor.cleanup();
    this.adaptiveBufferManager.stopMonitoring();
    this.initialized = false;

    logger.debug("Performance integration system cleaned up", {
      component: this.name,
      method: "cleanup",
    });
  }

  /**
   * Check if the system is initialized
   */
  isInitialized(): boolean {
    return this.initialized;
  }
}

/**
 * Global performance integration instance
 */
export const performanceIntegration = new PerformanceIntegration();
