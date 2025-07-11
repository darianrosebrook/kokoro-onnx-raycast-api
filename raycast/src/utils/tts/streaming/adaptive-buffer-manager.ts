/**
 * Adaptive Buffer Manager Module for Raycast Kokoro TTS
 *
 * This module provides intelligent buffer management that adapts to network
 * conditions and performance metrics for optimal streaming performance.
 *
 * Features:
 * - Network-aware buffer sizing
 * - Performance-based adaptation
 * - Real-time buffer optimization
 * - Latency prediction
 * - Bandwidth estimation
 * - Buffer health monitoring
 *
 * @author @darianrosebrook
 * @version 1.0.0
 * @since 2025-01-20
 */

import { logger } from "../../core/logger";
import type {
  IAdaptiveBufferManager,
  BufferConfig,
  PerformanceMetrics,
  NetworkConditions,
  BufferHealth,
  TTSProcessorConfig,
} from "../../validation/tts-types";
import { TTS_CONSTANTS } from "../../validation/tts-types";

/**
 * Buffer adaptation strategy
 */
interface BufferStrategy {
  type: "conservative" | "aggressive" | "balanced" | "adaptive";
  minBufferMs: number;
  maxBufferMs: number;
  targetLatency: number;
  adaptationRate: number;
}

/**
 * Network performance history
 */
interface NetworkHistory {
  timestamps: number[];
  latencies: number[];
  bandwidths: number[];
  packetLoss: number[];
  maxSize: number;
}

/**
 * Enhanced Adaptive Buffer Manager
 */
export class AdaptiveBufferManager implements IAdaptiveBufferManager {
  public readonly name = "AdaptiveBufferManager";
  public readonly version = "1.0.0";

  private config: {
    enableAdaptation: boolean;
    adaptationInterval: number;
    historySize: number;
    developmentMode: boolean;
  };
  private initialized = false;
  private currentBufferConfig: BufferConfig;
  private networkHistory: NetworkHistory;
  private currentStrategy: BufferStrategy;
  private lastAdaptationTime: number = 0;
  private adaptationCount: number = 0;

  constructor(config: Partial<TTSProcessorConfig> = {}) {
    this.config = {
      enableAdaptation: true,
      adaptationInterval: 5000, // 5 seconds
      historySize: 20,
      developmentMode: config.developmentMode ?? false,
    };

    // Initialize buffer configuration
    this.currentBufferConfig = {
      minBufferMs: TTS_CONSTANTS.MIN_BUFFER_MS,
      targetBufferMs: TTS_CONSTANTS.TARGET_BUFFER_MS,
      maxBufferMs: TTS_CONSTANTS.MAX_BUFFER_MS,
      sampleRate: TTS_CONSTANTS.SAMPLE_RATE,
      channels: TTS_CONSTANTS.CHANNELS,
      bytesPerSample: TTS_CONSTANTS.BYTES_PER_SAMPLE,
    };

    // Initialize network history
    this.networkHistory = {
      timestamps: [],
      latencies: [],
      bandwidths: [],
      packetLoss: [],
      maxSize: this.config.historySize,
    };

    // Initialize buffer strategy
    this.currentStrategy = {
      type: "balanced",
      minBufferMs: TTS_CONSTANTS.MIN_BUFFER_MS,
      maxBufferMs: TTS_CONSTANTS.MAX_BUFFER_MS,
      targetLatency: TTS_CONSTANTS.TARGET_TTFA_MS,
      adaptationRate: 0.1,
    };
  }

  /**
   * Initialize the buffer manager
   */
  async initialize(config: Partial<TTSProcessorConfig>): Promise<void> {
    if (config.developmentMode !== undefined) {
      this.config.developmentMode = config.developmentMode;
    }

    this.initialized = true;

    logger.info("Adaptive buffer manager initialized", {
      component: this.name,
      method: "initialize",
      config: this.config,
      initialBufferConfig: this.currentBufferConfig,
      strategy: this.currentStrategy,
    });
  }

  /**
   * Clean up resources
   */
  async cleanup(): Promise<void> {
    this.initialized = false;

    logger.debug("Adaptive buffer manager cleaned up", {
      component: this.name,
      method: "cleanup",
    });
  }

  /**
   * Check if the manager is initialized
   */
  isInitialized(): boolean {
    return this.initialized;
  }

  /**
   * Update buffer configuration based on performance metrics
   */
  updateBuffer(metrics: PerformanceMetrics, networkConditions?: NetworkConditions): BufferConfig {
    if (!this.initialized || !this.config.enableAdaptation) {
      return this.currentBufferConfig;
    }

    // Update network history
    if (networkConditions) {
      this.updateNetworkHistory(networkConditions);
    }

    // Check if it's time to adapt
    const now = performance.now();
    if (now - this.lastAdaptationTime < this.config.adaptationInterval) {
      return this.currentBufferConfig;
    }

    // Calculate new buffer configuration
    const newBufferConfig = this.calculateOptimalBuffer(metrics, networkConditions);

    // Apply adaptation
    this.applyBufferAdaptation(newBufferConfig);

    this.lastAdaptationTime = now;
    this.adaptationCount++;

    logger.info("Buffer configuration updated", {
      component: this.name,
      method: "updateBuffer",
      adaptationCount: this.adaptationCount,
      oldTargetBuffer: this.currentBufferConfig.targetBufferMs,
      newTargetBuffer: newBufferConfig.targetBufferMs,
      metrics: {
        timeToFirstAudio: metrics.timeToFirstAudio,
        streamingEfficiency: metrics.streamingEfficiency,
        underrunCount: metrics.underrunCount,
      },
    });

    return this.currentBufferConfig;
  }

  /**
   * Get current buffer configuration
   */
  getBufferConfig(): BufferConfig {
    return { ...this.currentBufferConfig };
  }

  /**
   * Get buffer health assessment
   */
  getBufferHealth(metrics: PerformanceMetrics): BufferHealth {
    const health = this.assessBufferHealth(metrics);

    logger.debug("Buffer health assessment", {
      component: this.name,
      method: "getBufferHealth",
      health,
      metrics: {
        timeToFirstAudio: metrics.timeToFirstAudio,
        streamingEfficiency: metrics.streamingEfficiency,
        underrunCount: metrics.underrunCount,
      },
    });

    return health;
  }

  /**
   * Predict optimal buffer size for given conditions
   */
  predictOptimalBuffer(networkConditions: NetworkConditions): number {
    if (!this.initialized) {
      return this.currentBufferConfig.targetBufferMs;
    }

    const predictedBuffer = this.calculatePredictedBuffer(networkConditions);

    logger.debug("Buffer size prediction", {
      component: this.name,
      method: "predictOptimalBuffer",
      networkConditions,
      predictedBuffer,
    });

    return predictedBuffer;
  }

  /**
   * Estimate network bandwidth
   */
  estimateBandwidth(): number {
    if (this.networkHistory.bandwidths.length === 0) {
      return 0;
    }

    // Calculate weighted average of recent bandwidth measurements
    const recentBandwidths = this.networkHistory.bandwidths.slice(-5);
    const weights = recentBandwidths.map((_, index) => index + 1);
    const totalWeight = weights.reduce((sum, weight) => sum + weight, 0);

    const weightedSum = recentBandwidths.reduce(
      (sum, bandwidth, index) => sum + bandwidth * weights[index],
      0
    );

    return weightedSum / totalWeight;
  }

  /**
   * Get network conditions summary
   */
  getNetworkConditions(): NetworkConditions {
    const latency = this.calculateAverageLatency();
    const bandwidth = this.estimateBandwidth();
    const packetLoss = this.calculatePacketLoss();

    return {
      latency,
      bandwidth,
      packetLoss,
      timestamp: performance.now(),
    };
  }

  /**
   * Update buffer strategy
   */
  updateStrategy(strategy: Partial<BufferStrategy>): void {
    this.currentStrategy = { ...this.currentStrategy, ...strategy };

    logger.info("Buffer strategy updated", {
      component: this.name,
      method: "updateStrategy",
      strategy: this.currentStrategy,
    });
  }

  /**
   * Get current strategy
   */
  getStrategy(): BufferStrategy {
    return { ...this.currentStrategy };
  }

  /**
   * Reset buffer configuration to defaults
   */
  resetToDefaults(): void {
    this.currentBufferConfig = {
      minBufferMs: TTS_CONSTANTS.MIN_BUFFER_MS,
      targetBufferMs: TTS_CONSTANTS.TARGET_BUFFER_MS,
      maxBufferMs: TTS_CONSTANTS.MAX_BUFFER_MS,
      sampleRate: TTS_CONSTANTS.SAMPLE_RATE,
      channels: TTS_CONSTANTS.CHANNELS,
      bytesPerSample: TTS_CONSTANTS.BYTES_PER_SAMPLE,
    };

    this.networkHistory = {
      timestamps: [],
      latencies: [],
      bandwidths: [],
      packetLoss: [],
      maxSize: this.config.historySize,
    };

    this.adaptationCount = 0;

    logger.info("Buffer configuration reset to defaults", {
      component: this.name,
      method: "resetToDefaults",
      bufferConfig: this.currentBufferConfig,
    });
  }

  /**
   * Update network history with new measurements
   */
  private updateNetworkHistory(conditions: NetworkConditions): void {
    const now = performance.now();

    // Add new measurements
    this.networkHistory.timestamps.push(now);
    this.networkHistory.latencies.push(conditions.latency);
    this.networkHistory.bandwidths.push(conditions.bandwidth);
    this.networkHistory.packetLoss.push(conditions.packetLoss);

    // Maintain history size
    if (this.networkHistory.timestamps.length > this.networkHistory.maxSize) {
      this.networkHistory.timestamps.shift();
      this.networkHistory.latencies.shift();
      this.networkHistory.bandwidths.shift();
      this.networkHistory.packetLoss.shift();
    }
  }

  /**
   * Calculate optimal buffer configuration
   */
  private calculateOptimalBuffer(
    metrics: PerformanceMetrics,
    networkConditions?: NetworkConditions
  ): BufferConfig {
    const currentConfig = this.currentBufferConfig;
    let newTargetBuffer = currentConfig.targetBufferMs;

    // Base adaptation on performance metrics
    if (metrics.timeToFirstAudio > this.currentStrategy.targetLatency) {
      // Increase buffer if latency is too high
      newTargetBuffer += this.currentStrategy.adaptationRate * 100;
    } else if (metrics.timeToFirstAudio < this.currentStrategy.targetLatency * 0.7) {
      // Decrease buffer if latency is very low
      newTargetBuffer -= this.currentStrategy.adaptationRate * 50;
    }

    // Adjust based on streaming efficiency
    if (metrics.streamingEfficiency < TTS_CONSTANTS.TARGET_EFFICIENCY) {
      newTargetBuffer += this.currentStrategy.adaptationRate * 75;
    } else if (metrics.streamingEfficiency > 0.95) {
      newTargetBuffer -= this.currentStrategy.adaptationRate * 25;
    }

    // Adjust based on underruns
    if (metrics.underrunCount > 0) {
      newTargetBuffer += metrics.underrunCount * 50;
    }

    // Apply network conditions if available
    if (networkConditions) {
      newTargetBuffer = this.applyNetworkAdaptation(newTargetBuffer, networkConditions);
    }

    // Clamp to valid range
    newTargetBuffer = Math.max(
      this.currentStrategy.minBufferMs,
      Math.min(this.currentStrategy.maxBufferMs, newTargetBuffer)
    );

    return {
      ...currentConfig,
      targetBufferMs: newTargetBuffer,
    };
  }

  /**
   * Apply network-based adaptation
   */
  private applyNetworkAdaptation(targetBuffer: number, conditions: NetworkConditions): number {
    let adjustedBuffer = targetBuffer;

    // Adjust based on latency
    if (conditions.latency > 200) {
      adjustedBuffer += 50; // High latency requires larger buffer
    } else if (conditions.latency < 50) {
      adjustedBuffer -= 25; // Low latency allows smaller buffer
    }

    // Adjust based on bandwidth
    if (conditions.bandwidth < 1000000) {
      // < 1 Mbps
      adjustedBuffer += 100; // Low bandwidth requires larger buffer
    } else if (conditions.bandwidth > 10000000) {
      // > 10 Mbps
      adjustedBuffer -= 50; // High bandwidth allows smaller buffer
    }

    // Adjust based on packet loss
    if (conditions.packetLoss > 0.01) {
      // > 1%
      adjustedBuffer += 75; // High packet loss requires larger buffer
    }

    return adjustedBuffer;
  }

  /**
   * Apply buffer adaptation
   */
  private applyBufferAdaptation(newConfig: BufferConfig): void {
    const oldConfig = this.currentBufferConfig;
    this.currentBufferConfig = newConfig;

    // Log buffer adjustment
    logger.logBufferAdjustment(
      oldConfig.targetBufferMs,
      newConfig.targetBufferMs,
      "adaptive-optimization"
    );
  }

  /**
   * Assess buffer health based on metrics
   */
  private assessBufferHealth(metrics: PerformanceMetrics): BufferHealth {
    const health: BufferHealth = {
      score: 1.0,
      status: "healthy",
      issues: [],
      recommendations: [],
    };

    // Check Time to First Audio
    if (metrics.timeToFirstAudio > this.currentStrategy.targetLatency) {
      health.score -= 0.3;
      health.issues.push("high_latency");
      health.recommendations.push("Increase buffer size to reduce latency");
    }

    // Check streaming efficiency
    if (metrics.streamingEfficiency < TTS_CONSTANTS.TARGET_EFFICIENCY) {
      health.score -= 0.2;
      health.issues.push("low_efficiency");
      health.recommendations.push("Optimize buffer strategy for better efficiency");
    }

    // Check underruns
    if (metrics.underrunCount > 0) {
      health.score -= 0.4;
      health.issues.push("buffer_underruns");
      health.recommendations.push("Increase buffer size to prevent underruns");
    }

    // Determine status
    if (health.score >= 0.8) {
      health.status = "healthy";
    } else if (health.score >= 0.6) {
      health.status = "degraded";
    } else {
      health.status = "poor";
    }

    return health;
  }

  /**
   * Calculate predicted buffer size
   */
  private calculatePredictedBuffer(conditions: NetworkConditions): number {
    let predictedBuffer = this.currentBufferConfig.targetBufferMs;

    // Base prediction on network conditions
    if (conditions.latency > 100) {
      predictedBuffer += conditions.latency * 0.5;
    }

    if (conditions.bandwidth < 5000000) {
      // < 5 Mbps
      predictedBuffer += 200;
    }

    if (conditions.packetLoss > 0.005) {
      // > 0.5%
      predictedBuffer += 150;
    }

    // Clamp to valid range
    return Math.max(
      this.currentStrategy.minBufferMs,
      Math.min(this.currentStrategy.maxBufferMs, predictedBuffer)
    );
  }

  /**
   * Calculate average latency from history
   */
  private calculateAverageLatency(): number {
    if (this.networkHistory.latencies.length === 0) {
      return 0;
    }

    const recentLatencies = this.networkHistory.latencies.slice(-5);
    return recentLatencies.reduce((sum, latency) => sum + latency, 0) / recentLatencies.length;
  }

  /**
   * Calculate packet loss rate from history
   */
  private calculatePacketLoss(): number {
    if (this.networkHistory.packetLoss.length === 0) {
      return 0;
    }

    const recentPacketLoss = this.networkHistory.packetLoss.slice(-5);
    return recentPacketLoss.reduce((sum, loss) => sum + loss, 0) / recentPacketLoss.length;
  }

  /**
   * Get adaptation statistics
   */
  getAdaptationStats(): {
    adaptationCount: number;
    lastAdaptationTime: number;
    averageAdaptationInterval: number;
  } {
    const now = performance.now();
    const averageInterval =
      this.adaptationCount > 0 ? (now - this.lastAdaptationTime) / this.adaptationCount : 0;

    return {
      adaptationCount: this.adaptationCount,
      lastAdaptationTime: this.lastAdaptationTime,
      averageAdaptationInterval: averageInterval,
    };
  }

  /**
   * Log buffer manager statistics
   */
  logBufferStats(): void {
    const stats = this.getAdaptationStats();
    const networkConditions = this.getNetworkConditions();
    const bufferHealth = this.getBufferHealth({
      timeToFirstAudio: networkConditions.latency,
      streamingEfficiency: 0.9, // Default value
      underrunCount: 0,
    } as PerformanceMetrics);

    logger.info("Buffer Manager Statistics", {
      component: this.name,
      method: "logBufferStats",
      stats,
      networkConditions,
      bufferHealth,
      currentConfig: this.currentBufferConfig,
      strategy: this.currentStrategy,
    });
  }
}
