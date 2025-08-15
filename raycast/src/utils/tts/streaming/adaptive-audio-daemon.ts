/**
 * Adaptive Audio Daemon for Variable Chunk Sizes
 *
 * Optimizes buffering and playback for CoreML precision variations
 * Monitors stream health to provide feedback for threshold optimization
 */

import { EventEmitter } from "events";
import { logger } from "@/utils/core/logger";

interface StreamHealthMetrics {
  totalStreams: number;
  successfulStreams: number;
  droppedChunks: number;
  bufferUnderruns: number;
  bufferOverruns: number;
  averageChunkSize: number;
  chunkSizeVariance: number;
  playbackLatency: number[];
  lastError?: string;
  errorCount: number;
}

interface AdaptiveBufferConfig {
  minBufferSize: number; // Minimum buffer to maintain
  maxBufferSize: number; // Maximum buffer size
  targetLatency: number; // Target playback latency (ms)
  varianceThreshold: number; // Chunk size variance threshold
  adaptationRate: number; // How quickly to adapt (0-1)
}

interface ChunkMetadata {
  sequence: number;
  size: number;
  timestamp: number;
  expectedSize?: number;
  sizeVariation?: number;
}

export class AdaptiveAudioDaemon extends EventEmitter {
  public readonly name = "AdaptiveAudioDaemon";
  private instanceId: string;

  // Buffer management
  private audioBuffer: Buffer[] = [];
  private bufferConfig: AdaptiveBufferConfig;
  private currentBufferSize = 0;
  private targetBufferSize = 0;

  // Stream health tracking
  private healthMetrics: StreamHealthMetrics;
  private chunkHistory: ChunkMetadata[] = [];
  private maxHistoryLength = 100;

  // Adaptive optimization
  private isOptimizing = false;
  private optimizationInterval?: NodeJS.Timeout;
  private performanceBaseline?: {
    successRate: number;
    averageLatency: number;
    dropRate: number;
  };

  // Playback state
  private isPlaying = false;
  private playbackStartTime?: number;
  private lastChunkTime?: number;

  constructor(initialConfig?: Partial<AdaptiveBufferConfig>) {
    super();
    this.instanceId = `adaptive-${Date.now()}`;

    // Default adaptive configuration
    this.bufferConfig = {
      minBufferSize: 32 * 1024, // 32KB minimum
      maxBufferSize: 2 * 1024 * 1024, // 2MB maximum
      targetLatency: 150, // 150ms target
      varianceThreshold: 0.15, // 15% variation threshold
      adaptationRate: 0.1, // 10% adaptation rate
      ...initialConfig,
    };

    this.targetBufferSize = this.bufferConfig.minBufferSize;

    // Initialize health metrics
    this.healthMetrics = {
      totalStreams: 0,
      successfulStreams: 0,
      droppedChunks: 0,
      bufferUnderruns: 0,
      bufferOverruns: 0,
      averageChunkSize: 0,
      chunkSizeVariance: 0,
      playbackLatency: [],
      errorCount: 0,
    };

    logger.info(`🎵 AdaptiveAudioDaemon initialized: ${this.instanceId}`, {
      component: this.name,
      method: "constructor",
      bufferConfig: this.bufferConfig,
    });
  }

  /**
   * Start adaptive optimization based on stream health
   */
  startOptimization(intervalMs: number = 30000): void {
    if (this.isOptimizing) return;

    this.isOptimizing = true;
    this.optimizationInterval = setInterval(() => {
      this.optimizeConfiguration();
    }, intervalMs);

    logger.info(`🔧 Started adaptive optimization (${intervalMs}ms interval)`, {
      component: this.name,
      method: "startOptimization",
    });
  }

  /**
   * Stop adaptive optimization
   */
  stopOptimization(): void {
    if (!this.isOptimizing) return;

    this.isOptimizing = false;
    if (this.optimizationInterval) {
      clearInterval(this.optimizationInterval);
      this.optimizationInterval = undefined;
    }

    logger.info(`⏹️ Stopped adaptive optimization`, {
      component: this.name,
      method: "stopOptimization",
    });
  }

  /**
   * Write audio chunk with adaptive buffering
   */
  async writeChunk(chunk: Buffer, metadata?: Partial<ChunkMetadata>): Promise<void> {
    const startTime = performance.now();

    try {
      // Create chunk metadata
      const chunkMeta: ChunkMetadata = {
        sequence: this.chunkHistory.length,
        size: chunk.length,
        timestamp: Date.now(),
        expectedSize: this.healthMetrics.averageChunkSize || chunk.length,
        ...metadata,
      };

      // Calculate size variation
      if (this.healthMetrics.averageChunkSize > 0) {
        chunkMeta.sizeVariation =
          Math.abs(chunk.length - this.healthMetrics.averageChunkSize) /
          this.healthMetrics.averageChunkSize;
      }

      // Add to history
      this.chunkHistory.push(chunkMeta);
      if (this.chunkHistory.length > this.maxHistoryLength) {
        this.chunkHistory.shift();
      }

      // Check for buffer overrun
      if (this.currentBufferSize + chunk.length > this.bufferConfig.maxBufferSize) {
        this.healthMetrics.bufferOverruns++;
        logger.warn(`⚠️ Buffer overrun detected`, {
          component: this.name,
          method: "writeChunk",
          currentSize: this.currentBufferSize,
          chunkSize: chunk.length,
          maxSize: this.bufferConfig.maxBufferSize,
        });

        // Drop oldest chunk to make room
        const droppedChunk = this.audioBuffer.shift();
        if (droppedChunk) {
          this.currentBufferSize -= droppedChunk.length;
          this.healthMetrics.droppedChunks++;
        }
      }

      // Add chunk to buffer
      this.audioBuffer.push(chunk);
      this.currentBufferSize += chunk.length;

      // Update metrics
      this.updateHealthMetrics(chunkMeta);

      // Start playback if we have enough buffer
      if (!this.isPlaying && this.shouldStartPlayback()) {
        this.startPlayback();
      }

      // Adapt buffer size based on chunk variation
      this.adaptBufferSize(chunkMeta);

      const processingTime = performance.now() - startTime;
      logger.debug(`📝 Chunk written: ${chunk.length} bytes (${processingTime.toFixed(2)}ms)`, {
        component: this.name,
        method: "writeChunk",
        bufferSize: this.currentBufferSize,
        bufferChunks: this.audioBuffer.length,
        sizeVariation: chunkMeta.sizeVariation?.toFixed(3),
      });
    } catch (error) {
      this.healthMetrics.errorCount++;
      this.healthMetrics.lastError = error instanceof Error ? error.message : String(error);

      logger.error(`❌ Chunk write failed: ${this.healthMetrics.lastError}`, {
        component: this.name,
        method: "writeChunk",
        error,
      });

      throw error;
    }
  }

  /**
   * Signal end of stream
   */
  async endStream(): Promise<void> {
    logger.info(`🏁 Stream ending`, {
      component: this.name,
      method: "endStream",
      remainingChunks: this.audioBuffer.length,
      bufferSize: this.currentBufferSize,
    });

    // Play remaining buffer
    while (this.audioBuffer.length > 0) {
      await this.playNextChunk();
    }

    this.isPlaying = false;
    this.healthMetrics.totalStreams++;

    // Determine if stream was successful
    const errorRate = this.healthMetrics.errorCount / Math.max(this.chunkHistory.length, 1);
    const dropRate = this.healthMetrics.droppedChunks / Math.max(this.chunkHistory.length, 1);

    if (errorRate < 0.05 && dropRate < 0.1) {
      // Less than 5% errors, 10% drops
      this.healthMetrics.successfulStreams++;
    }

    this.emit("completed", this.getStreamHealth());

    logger.info(`✅ Stream completed`, {
      component: this.name,
      method: "endStream",
      health: this.getStreamHealth(),
    });
  }

  /**
   * Start playback when buffer conditions are met
   */
  private startPlayback(): void {
    if (this.isPlaying) return;

    this.isPlaying = true;
    this.playbackStartTime = performance.now();

    logger.info(`▶️ Starting adaptive playback`, {
      component: this.name,
      method: "startPlayback",
      bufferSize: this.currentBufferSize,
      targetBuffer: this.targetBufferSize,
    });

    // Start playback loop
    this.playbackLoop();
  }

  /**
   * Continuous playback loop
   */
  private async playbackLoop(): Promise<void> {
    while (this.isPlaying && this.audioBuffer.length > 0) {
      try {
        await this.playNextChunk();

        // Check for buffer underrun
        if (
          this.currentBufferSize < this.bufferConfig.minBufferSize &&
          this.audioBuffer.length > 0
        ) {
          this.healthMetrics.bufferUnderruns++;
          logger.warn(`⚠️ Buffer underrun detected`, {
            component: this.name,
            method: "playbackLoop",
            currentSize: this.currentBufferSize,
            minSize: this.bufferConfig.minBufferSize,
          });
        }

        // Dynamic delay based on buffer level
        const delay = this.calculatePlaybackDelay();
        if (delay > 0) {
          await new Promise((resolve) => setTimeout(resolve, delay));
        }
      } catch (error) {
        logger.error(`❌ Playback error: ${error}`, {
          component: this.name,
          method: "playbackLoop",
          error,
        });
        break;
      }
    }
  }

  /**
   * Play the next chunk in the buffer
   */
  private async playNextChunk(): Promise<void> {
    const chunk = this.audioBuffer.shift();
    if (!chunk) return;

    const chunkStartTime = performance.now();
    this.currentBufferSize -= chunk.length;

    // Simulate chunk playback (in real implementation, this would send to audio system)
    this.emit("audioChunk", chunk);

    const playbackTime = performance.now() - chunkStartTime;
    this.healthMetrics.playbackLatency.push(playbackTime);

    // Keep only recent latency measurements
    if (this.healthMetrics.playbackLatency.length > 50) {
      this.healthMetrics.playbackLatency.shift();
    }

    this.lastChunkTime = performance.now();

    logger.debug(`🎵 Chunk played: ${chunk.length} bytes (${playbackTime.toFixed(2)}ms)`, {
      component: this.name,
      method: "playNextChunk",
      remainingBuffer: this.currentBufferSize,
    });
  }

  /**
   * Determine if playback should start
   */
  private shouldStartPlayback(): boolean {
    return this.currentBufferSize >= this.targetBufferSize;
  }

  /**
   * Calculate dynamic playback delay based on buffer level
   */
  private calculatePlaybackDelay(): number {
    const bufferRatio = this.currentBufferSize / this.targetBufferSize;

    if (bufferRatio > 2.0) {
      // Buffer is very full, play faster
      return 10;
    } else if (bufferRatio > 1.5) {
      // Buffer is moderately full, normal speed
      return 20;
    } else if (bufferRatio > 0.5) {
      // Buffer is getting low, slow down slightly
      return 30;
    } else {
      // Buffer is very low, pause briefly to let it fill
      return 50;
    }
  }

  /**
   * Adapt buffer size based on chunk variation patterns
   */
  private adaptBufferSize(chunkMeta: ChunkMetadata): void {
    if (this.chunkHistory.length < 5) return; // Need some history

    // Calculate recent variance
    const recentChunks = this.chunkHistory.slice(-10);
    const sizes = recentChunks.map((c) => c.size);
    const avgSize = sizes.reduce((a, b) => a + b, 0) / sizes.length;
    const variance =
      sizes.reduce((acc, size) => acc + Math.pow(size - avgSize, 2), 0) / sizes.length;
    const standardDeviation = Math.sqrt(variance);
    const coefficientOfVariation = standardDeviation / avgSize;

    // If chunk sizes vary significantly, increase buffer size
    if (coefficientOfVariation > this.bufferConfig.varianceThreshold) {
      const increase = this.targetBufferSize * this.bufferConfig.adaptationRate;
      const newTargetSize = Math.min(
        this.targetBufferSize + increase,
        this.bufferConfig.maxBufferSize
      );

      if (newTargetSize !== this.targetBufferSize) {
        logger.info(`📈 Increasing buffer size due to chunk variation`, {
          component: this.name,
          method: "adaptBufferSize",
          oldTarget: this.targetBufferSize,
          newTarget: Math.round(newTargetSize),
          variation: coefficientOfVariation.toFixed(3),
          threshold: this.bufferConfig.varianceThreshold,
        });

        this.targetBufferSize = newTargetSize;
      }
    }
    // If chunks are consistent, we could decrease buffer size (but be conservative)
    else if (coefficientOfVariation < this.bufferConfig.varianceThreshold * 0.5) {
      const decrease = this.targetBufferSize * this.bufferConfig.adaptationRate * 0.5;
      const newTargetSize = Math.max(
        this.targetBufferSize - decrease,
        this.bufferConfig.minBufferSize
      );

      if (newTargetSize !== this.targetBufferSize) {
        logger.info(`📉 Decreasing buffer size due to consistent chunks`, {
          component: this.name,
          method: "adaptBufferSize",
          oldTarget: this.targetBufferSize,
          newTarget: Math.round(newTargetSize),
          variation: coefficientOfVariation.toFixed(3),
        });

        this.targetBufferSize = newTargetSize;
      }
    }
  }

  /**
   * Update health metrics with new chunk data
   */
  private updateHealthMetrics(chunkMeta: ChunkMetadata): void {
    // Update average chunk size (rolling average)
    if (this.healthMetrics.averageChunkSize === 0) {
      this.healthMetrics.averageChunkSize = chunkMeta.size;
    } else {
      this.healthMetrics.averageChunkSize =
        this.healthMetrics.averageChunkSize * 0.9 + chunkMeta.size * 0.1;
    }

    // Update chunk size variance
    if (chunkMeta.sizeVariation !== undefined) {
      this.healthMetrics.chunkSizeVariance =
        this.healthMetrics.chunkSizeVariance * 0.9 + chunkMeta.sizeVariation * 0.1;
    }
  }

  /**
   * Optimize configuration based on performance metrics
   */
  private optimizeConfiguration(): void {
    const health = this.getStreamHealth();

    logger.info(`🔍 Optimizing configuration based on performance`, {
      component: this.name,
      method: "optimizeConfiguration",
      health,
    });

    // Establish baseline if not set
    if (!this.performanceBaseline) {
      this.performanceBaseline = {
        successRate: health.successRate,
        averageLatency: health.averageLatency,
        dropRate: health.dropRate,
      };
      return;
    }

    const improvement = {
      successRate: health.successRate - this.performanceBaseline.successRate,
      latency: this.performanceBaseline.averageLatency - health.averageLatency, // Lower is better
      dropRate: this.performanceBaseline.dropRate - health.dropRate, // Lower is better
    };

    // Emit optimization recommendations
    this.emit("optimizationRecommendation", {
      currentHealth: health,
      baseline: this.performanceBaseline,
      improvement,
      recommendations: this.generateRecommendations(health, improvement),
    });

    // Update baseline with current performance
    this.performanceBaseline = {
      successRate: health.successRate,
      averageLatency: health.averageLatency,
      dropRate: health.dropRate,
    };
  }

  /**
   * Generate optimization recommendations
   */
  private generateRecommendations(health: any, improvement: any): string[] {
    const recommendations: string[] = [];

    if (health.dropRate > 0.05) {
      // More than 5% drops
      recommendations.push("Increase buffer size to reduce drops");
    }

    if (health.averageLatency > this.bufferConfig.targetLatency * 1.5) {
      recommendations.push("Decrease buffer size to reduce latency");
    }

    if (health.successRate < 0.95) {
      // Less than 95% success
      recommendations.push("Increase variation threshold tolerance");
    }

    if (improvement.successRate < -0.1) {
      // Success rate dropped
      recommendations.push("Revert recent buffer changes");
    }

    return recommendations;
  }

  /**
   * Get current stream health metrics
   */
  getStreamHealth(): any {
    const totalChunks = Math.max(this.chunkHistory.length, 1);
    const successRate =
      this.healthMetrics.successfulStreams / Math.max(this.healthMetrics.totalStreams, 1);
    const dropRate = this.healthMetrics.droppedChunks / totalChunks;
    const averageLatency =
      this.healthMetrics.playbackLatency.length > 0
        ? this.healthMetrics.playbackLatency.reduce((a, b) => a + b, 0) /
          this.healthMetrics.playbackLatency.length
        : 0;

    return {
      ...this.healthMetrics,
      successRate,
      dropRate,
      averageLatency,
      currentBufferSize: this.currentBufferSize,
      targetBufferSize: this.targetBufferSize,
      bufferConfig: this.bufferConfig,
      isOptimizing: this.isOptimizing,
    };
  }

  /**
   * Reset metrics for new optimization cycle
   */
  resetMetrics(): void {
    this.healthMetrics = {
      totalStreams: 0,
      successfulStreams: 0,
      droppedChunks: 0,
      bufferUnderruns: 0,
      bufferOverruns: 0,
      averageChunkSize: 0,
      chunkSizeVariance: 0,
      playbackLatency: [],
      errorCount: 0,
    };

    this.chunkHistory = [];
    this.performanceBaseline = undefined;

    logger.info(`🔄 Metrics reset for new optimization cycle`, {
      component: this.name,
      method: "resetMetrics",
    });
  }
}
