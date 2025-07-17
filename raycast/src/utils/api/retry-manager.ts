/**
 * Retry Manager Module for Raycast Kokoro TTS
 *
 * This module implements sophisticated retry logic with exponential backoff
 * for better error recovery and system resilience.
 *
 * Features:
 * - Exponential backoff with jitter
 * - Configurable retry strategies
 * - Error classification and handling
 * - Circuit breaker pattern
 * - Retry metrics and monitoring
 * - Graceful degradation
 *
 * @author @darianrosebrook
 * @version 1.0.0
 * @since 2025-01-20
 */

import { logger } from "../core/logger";
import type {
  RetryConfig,
  RetryStrategy,
  RetryResult,
  RetryError,
  RetryMetrics,
  TTSProcessorConfig,
} from "../validation/tts-types.js";

/**
 * Retry attempt information
 */
interface RetryAttempt {
  attempt: number;
  startTime: number;
  delay: number;
  error: Error;
  isRetryable: boolean;
}

/**
 * Circuit breaker state
 */
interface CircuitBreakerState {
  isOpen: boolean;
  failureCount: number;
  lastFailureTime: number;
  nextAttemptTime: number;
  successCount: number;
}

/**
 * Enhanced Retry Manager with exponential backoff
 */
export class RetryManager {
  public readonly name = "RetryManager";
  public readonly version = "1.0.0";

  private config: {
    maxAttempts: number;
    baseDelayMs: number;
    maxDelayMs: number;
    retryCondition: (error: Error) => boolean;
    retryableErrors: string[];
    nonRetryableErrors: string[];
    enableCircuitBreaker: boolean;
    circuitBreakerThreshold: number;
    circuitBreakerTimeout: number;
    developmentMode: boolean;
  };
  private initialized = false;
  private retryMetrics: RetryMetrics = {
    totalAttempts: 0,
    successfulRetries: 0,
    failedRetries: 0,
    totalRetryTime: 0,
    averageRetryDelay: 0,
    circuitBreakerTrips: 0,
  };
  private circuitBreaker: CircuitBreakerState = {
    isOpen: false,
    failureCount: 0,
    lastFailureTime: 0,
    nextAttemptTime: 0,
    successCount: 0,
  };

  constructor(config: Partial<TTSProcessorConfig> = {}) {
    this.config = {
      maxAttempts: 3,
      baseDelayMs: 1000, // 1 second
      maxDelayMs: 30000, // 30 seconds
      retryCondition: (_error: Error) => true,
      retryableErrors: [],
      nonRetryableErrors: [],
      enableCircuitBreaker: true,
      circuitBreakerThreshold: 5,
      circuitBreakerTimeout: 60000, // 1 minute
      developmentMode: config.developmentMode ?? false,
    };
  }

  /**
   * Initialize the retry manager
   */
  async initialize(config: Partial<TTSProcessorConfig>): Promise<void> {
    if (config.developmentMode !== undefined) {
      this.config.developmentMode = config.developmentMode;
    }

    this.initialized = true;

    logger.consoleInfo("Retry manager initialized", {
      component: this.name,
      method: "initialize",
      config: this.config,
    });
  }

  /**
   * Clean up resources
   */
  async cleanup(): Promise<void> {
    this.initialized = false;

    logger.debug("Retry manager cleaned up", {
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
   * Execute function with retry logic
   */
  async executeWithRetry<T>(
    operation: () => Promise<T>,
    context: string,
    customConfig?: Partial<RetryConfig>
  ): Promise<RetryResult<T>> {
    if (!this.initialized) {
      throw new Error("Retry manager not initialized");
    }

    const config = { ...this.config, ...customConfig };
    const startTime = performance.now();
    let lastError: Error | null = null;
    const attempts: RetryAttempt[] = [];

    // Check circuit breaker
    if (this.shouldBlockRequest()) {
      const error = new Error("Circuit breaker is open");
      return {
        success: false,
        data: null,
        error,
        attempts: [],
        metrics: this.getRetryMetrics(),
        circuitBreakerOpen: true,
      };
    }

    for (let attempt = 0; attempt <= config.maxAttempts; attempt++) {
      const attemptStartTime = performance.now();

      try {
        // Execute operation
        const result = await operation();

        // Record success
        this.recordSuccess();

        const totalTime = performance.now() - startTime;
        this.updateMetrics(attempt, totalTime);

        logger.consoleInfo("Operation succeeded", {
          component: this.name,
          method: "executeWithRetry",
          context,
          attempt: attempt + 1,
          totalTime: `${totalTime.toFixed(2)}ms`,
        });

        return {
          success: true,
          data: result,
          error: null,
          attempts,
          metrics: this.getRetryMetrics(),
          circuitBreakerOpen: false,
        };
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));
        const attemptTime = performance.now() - attemptStartTime;

        // Classify error
        const retryError = this.classifyError(lastError);
        const isRetryable = this.isRetryableError(retryError, attempt, config);

        // Record attempt
        const retryAttempt: RetryAttempt = {
          attempt: attempt + 1,
          startTime: attemptStartTime,
          delay: 0,
          error: lastError,
          isRetryable,
        };
        attempts.push(retryAttempt);

        logger.warn("Operation failed", {
          component: this.name,
          method: "executeWithRetry",
          context,
          attempt: attempt + 1,
          error: lastError.message,
          isRetryable,
          attemptTime: `${attemptTime.toFixed(2)}ms`,
        });

        // Record failure
        this.recordFailure();

        // Check if we should retry
        if (
          (config.retryCondition && !config.retryCondition(lastError)) ||
          !isRetryable ||
          attempt === config.maxAttempts
        ) {
          break;
        }

        // Calculate delay
        const delay = this.calculateDelay(attempt, config);
        retryAttempt.delay = delay;

        logger.consoleInfo("Retrying operation", {
          component: this.name,
          method: "executeWithRetry",
          context,
          attempt: attempt + 1,
          delay: `${delay.toFixed(0)}ms`,
        });

        // Wait before retry
        await this.delay(delay);
      }
    }

    // All attempts failed
    const totalTime = performance.now() - startTime;
    this.updateMetrics(attempts.length, totalTime);

    logger.error("All retry attempts failed", {
      component: this.name,
      method: "executeWithRetry",
      context,
      totalAttempts: attempts.length,
      totalTime: `${totalTime.toFixed(2)}ms`,
      finalError: lastError?.message,
    });

    return {
      success: false,
      data: null,
      error: lastError!,
      attempts,
      metrics: this.getRetryMetrics(),
      circuitBreakerOpen: this.circuitBreaker.isOpen,
    };
  }

  /**
   * Execute function with custom retry strategy
   */
  async executeWithStrategy<T>(
    operation: () => Promise<T>,
    strategy: RetryStrategy,
    context: string
  ): Promise<RetryResult<T>> {
    const config: RetryConfig = {
      maxAttempts: strategy.maxRetries ?? this.config.maxAttempts,
      baseDelayMs: strategy.baseDelay ?? this.config.baseDelayMs,
      maxDelayMs: strategy.maxDelay ?? this.config.maxDelayMs,
      retryCondition: (_error: Error) => true,
      retryableErrors: strategy.retryableErrors ?? [],
      nonRetryableErrors: strategy.nonRetryableErrors ?? [],
    };

    return this.executeWithRetry(operation, context, config);
  }

  /**
   * Get retry metrics
   */
  getRetryMetrics(): RetryMetrics {
    return { ...this.retryMetrics };
  }

  /**
   * Reset retry metrics
   */
  resetMetrics(): void {
    this.retryMetrics = {
      totalAttempts: 0,
      successfulRetries: 0,
      failedRetries: 0,
      totalRetryTime: 0,
      averageRetryDelay: 0,
      circuitBreakerTrips: 0,
    };

    logger.consoleInfo("Retry metrics reset", {
      component: this.name,
      method: "resetMetrics",
    });
  }

  /**
   * Get circuit breaker state
   */
  getCircuitBreakerState(): CircuitBreakerState {
    return { ...this.circuitBreaker };
  }

  /**
   * Reset circuit breaker
   */
  resetCircuitBreaker(): void {
    this.circuitBreaker = {
      isOpen: false,
      failureCount: 0,
      lastFailureTime: 0,
      nextAttemptTime: 0,
      successCount: 0,
    };

    logger.consoleInfo("Circuit breaker reset", {
      component: this.name,
      method: "resetCircuitBreaker",
    });
  }

  /**
   * Update retry configuration
   */
  updateConfig(config: Partial<RetryConfig>): void {
    this.config = { ...this.config, ...config };

    logger.consoleInfo("Retry configuration updated", {
      component: this.name,
      method: "updateConfig",
      config: this.config,
    });
  }

  /**
   * Get current configuration
   */
  getConfig(): RetryConfig {
    return { ...this.config };
  }

  /**
   * Check if circuit breaker should block request
   */
  private shouldBlockRequest(): boolean {
    if (!this.config.enableCircuitBreaker) {
      return false;
    }

    if (!this.circuitBreaker.isOpen) {
      return false;
    }

    // Check if timeout has passed
    if (performance.now() >= this.circuitBreaker.nextAttemptTime) {
      this.circuitBreaker.isOpen = false;
      this.circuitBreaker.failureCount = 0;
      return false;
    }

    return true;
  }

  /**
   * Record successful operation
   */
  private recordSuccess(): void {
    this.circuitBreaker.successCount++;
    this.circuitBreaker.failureCount = 0;

    // Close circuit breaker if it was open
    if (this.circuitBreaker.isOpen) {
      this.circuitBreaker.isOpen = false;

      logger.consoleInfo("Circuit breaker closed after success", {
        component: this.name,
        method: "recordSuccess",
        successCount: this.circuitBreaker.successCount,
      });
    }
  }

  /**
   * Record failed operation
   */
  private recordFailure(): void {
    this.circuitBreaker.failureCount++;
    this.circuitBreaker.lastFailureTime = performance.now();

    // Check if circuit breaker should open
    if (this.circuitBreaker.failureCount >= this.config.circuitBreakerThreshold) {
      this.circuitBreaker.isOpen = true;
      this.circuitBreaker.nextAttemptTime = performance.now() + this.config.circuitBreakerTimeout;
      this.retryMetrics.circuitBreakerTrips++;

      logger.warn("Circuit breaker opened", {
        component: this.name,
        method: "recordFailure",
        failureCount: this.circuitBreaker.failureCount,
        threshold: this.config.circuitBreakerThreshold,
        nextAttemptTime: new Date(this.circuitBreaker.nextAttemptTime).toISOString(),
      });
    }
  }

  /**
   * Classify error for retry decision
   */
  private classifyError(error: Error): RetryError {
    const message = error.message.toLowerCase();
    const name = error.name.toLowerCase();

    // Network errors
    if (message.includes("network") || message.includes("fetch") || message.includes("timeout")) {
      return { type: "network", retryable: true, priority: "high" };
    }

    // Server errors (5xx)
    if (
      message.includes("500") ||
      message.includes("502") ||
      message.includes("503") ||
      message.includes("504")
    ) {
      return { type: "server", retryable: true, priority: "high" };
    }

    // Client errors (4xx) - generally not retryable
    if (
      message.includes("400") ||
      message.includes("401") ||
      message.includes("403") ||
      message.includes("404")
    ) {
      return { type: "client", retryable: false, priority: "low" };
    }

    // Rate limiting
    if (message.includes("rate limit") || message.includes("429")) {
      return { type: "rate_limit", retryable: true, priority: "medium" };
    }

    // Timeout errors
    if (message.includes("timeout") || name.includes("timeout")) {
      return { type: "timeout", retryable: true, priority: "medium" };
    }

    // Connection errors
    if (
      message.includes("connection") ||
      message.includes("econnrefused") ||
      message.includes("enotfound")
    ) {
      return { type: "connection", retryable: true, priority: "high" };
    }

    // Unknown error - assume retryable
    return { type: "unknown", retryable: true, priority: "medium" };
  }

  /**
   * Check if error is retryable
   */
  private isRetryableError(error: RetryError, attempt: number, config: RetryConfig): boolean {
    // Check if we've exceeded max retries
    if (attempt >= config.maxAttempts) {
      return false;
    }

    // Check error classification
    if (!error.retryable) {
      return false;
    }

    // Check custom retryable errors
    if (config.retryableErrors && config.retryableErrors.length > 0) {
      const errorMessage = error.message?.toLowerCase() || "";
      return config.retryableErrors.some((pattern) => errorMessage.includes(pattern.toLowerCase()));
    }

    // Check custom non-retryable errors
    if (config.nonRetryableErrors && config.nonRetryableErrors.length > 0) {
      const errorMessage = error.message?.toLowerCase() || "";
      return !config.nonRetryableErrors.some((pattern) =>
        errorMessage.includes(pattern.toLowerCase())
      );
    }

    return true;
  }

  /**
   * Calculate delay with exponential backoff and jitter
   */
  private calculateDelay(attempt: number, config: RetryConfig): number {
    // Exponential backoff
    const exponentialDelay = config.baseDelayMs * Math.pow(2, attempt);

    // Apply maximum delay limit
    const cappedDelay = Math.min(exponentialDelay, config.maxDelayMs);

    // Add jitter to prevent thundering herd
    const jitter = cappedDelay * 0.1 * (Math.random() - 0.5);
    const finalDelay = cappedDelay + jitter;

    return Math.max(0, finalDelay);
  }

  /**
   * Wait for specified delay
   */
  private delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Update retry metrics
   */
  private updateMetrics(attempts: number, totalTime: number): void {
    this.retryMetrics.totalAttempts += attempts;
    this.retryMetrics.totalRetryTime += totalTime;

    if (attempts > 1) {
      this.retryMetrics.successfulRetries++;
    } else {
      this.retryMetrics.failedRetries++;
    }

    // Update average retry delay
    if (this.retryMetrics.totalAttempts > 0) {
      this.retryMetrics.averageRetryDelay =
        this.retryMetrics.totalRetryTime / this.retryMetrics.totalAttempts;
    }
  }

  /**
   * Log retry statistics
   */
  logRetryStats(): void {
    const metrics = this.getRetryMetrics();
    const circuitState = this.getCircuitBreakerState();

    logger.consoleInfo("Retry Statistics", {
      component: this.name,
      method: "logRetryStats",
      metrics: {
        totalAttempts: metrics.totalAttempts,
        successfulRetries: metrics.successfulRetries,
        failedRetries: metrics.failedRetries,
        successRate:
          metrics.totalAttempts > 0
            ? ((metrics.successfulRetries / metrics.totalAttempts) * 100).toFixed(1) + "%"
            : "0%",
        averageRetryDelay: `${metrics.averageRetryDelay.toFixed(2)}ms`,
        circuitBreakerTrips: metrics.circuitBreakerTrips,
      },
      circuitBreaker: {
        isOpen: circuitState.isOpen,
        failureCount: circuitState.failureCount,
        successCount: circuitState.successCount,
        lastFailureTime:
          circuitState.lastFailureTime > 0
            ? new Date(circuitState.lastFailureTime).toISOString()
            : "Never",
      },
    });
  }
}
