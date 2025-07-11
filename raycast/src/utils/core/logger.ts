/**
 * Structured Logging Utility for Raycast Kokoro TTS
 *
 * This module provides consistent structured logging throughout the TTS processor
 * with configurable log levels, proper error handling, and development-friendly output.
 *
 * Features:
 * - Structured JSON logging for production
 * - Colorized console output for development
 * - Configurable log levels based on environment
 * - Error stack trace capture
 * - Performance timing utilities
 * - Context-aware logging
 *
 * @author @darianrosebrook
 * @version 1.0.0
 * @since 2025-01-20
 */

import { createLogger, format, transports, Logger, transport } from "winston";

/**
 * Log levels for different types of messages
 */
export enum LogLevel {
  ERROR = "error",
  WARN = "warn",
  INFO = "info",
  DEBUG = "debug",
}

/**
 * Context information for structured logging
 */
interface LogContext {
  component?: string;
  method?: string;
  requestId?: string;
  userId?: string;
  voice?: string;
  textLength?: number;
  duration?: number;
  [key: string]: unknown;
}

/**
 * Performance timing context
 */
interface PerformanceContext {
  operation: string;
  startTime: number;
  context?: LogContext;
}

/**
 * Structured logger configuration
 */
interface LoggerConfig {
  level: LogLevel;
  developmentMode: boolean;
  enableConsole: boolean;
  enableFile?: boolean;
  filename?: string;
}

/**
 * Create a formatted logger instance
 */
function createFormattedLogger(config: LoggerConfig): Logger {
  const loggerTransports: transport[] = [];

  // Console transport for development
  if (config.enableConsole) {
    loggerTransports.push(
      new transports.Console({
        format: config.developmentMode
          ? format.combine(
              format.colorize(),
              format.timestamp({ format: "HH:mm:ss" }),
              format.printf(({ timestamp, level, message, ...meta }) => {
                const metaStr = Object.keys(meta).length > 0 ? JSON.stringify(meta, null, 2) : "";
                return `${timestamp} [${level}]: ${message} ${metaStr}`;
              })
            )
          : format.combine(format.timestamp(), format.errors({ stack: true }), format.json()),
      })
    );
  }

  // File transport for production logging (optional)
  if (config.enableFile && config.filename) {
    loggerTransports.push(
      new transports.File({
        filename: config.filename,
        format: format.combine(format.timestamp(), format.errors({ stack: true }), format.json()),
      })
    );
  }

  return createLogger({
    level: config.level,
    format: format.combine(
      format.timestamp(),
      format.errors({ stack: true }),
      format.metadata({ fillExcept: ["message", "level", "timestamp"] })
    ),
    transports: loggerTransports,
    // Prevent winston from exiting on error
    exitOnError: false,
  });
}

/**
 * Enhanced TTS Logger with structured logging capabilities
 */
export class TTSLogger {
  private logger: Logger;
  private developmentMode: boolean;
  private performanceTimers: Map<string, PerformanceContext> = new Map();

  constructor(config: Partial<LoggerConfig> = {}) {
    const defaultConfig: LoggerConfig = {
      level: LogLevel.INFO,
      developmentMode: process.env.NODE_ENV !== "production",
      enableConsole: true,
      enableFile: false,
    };

    const finalConfig = { ...defaultConfig, ...config };
    this.developmentMode = finalConfig.developmentMode;
    this.logger = createFormattedLogger(finalConfig);
  }

  /**
   * Log an error with full context and stack trace
   */
  error(message: string, context?: LogContext, error?: Error): void {
    const logData: { message: string; [key: string]: unknown } = {
      message,
      ...context,
    };

    if (error) {
      logData.error = {
        message: error.message,
        stack: error.stack,
        name: error.name,
      };
    }

    this.logger.error(logData);
  }

  /**
   * Log a warning with context
   */
  warn(message: string, context?: LogContext): void {
    this.logger.warn(message, context);
  }

  /**
   * Log informational message
   */
  info(message: string, context?: LogContext): void {
    this.logger.info(message, context);
  }

  /**
   * Log debug information (only in development)
   */
  debug(message: string, context?: LogContext): void {
    if (this.developmentMode || this.logger.level === "debug") {
      this.logger.debug(message, context);
    }
  }

  /**
   * Start performance timing for an operation
   */
  startTiming(operation: string, context?: LogContext): string {
    const timerId = `${operation}-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;

    this.performanceTimers.set(timerId, {
      operation,
      startTime: performance.now(),
      context,
    });

    this.debug(`Started timing: ${operation}`, { ...context, timerId });
    return timerId;
  }

  /**
   * End performance timing and log result
   */
  endTiming(timerId: string, additionalContext?: LogContext): number {
    const timer = this.performanceTimers.get(timerId);

    if (!timer) {
      this.warn("Timer not found", { timerId });
      return 0;
    }

    const duration = performance.now() - timer.startTime;
    const context = {
      ...timer.context,
      ...additionalContext,
      duration: parseFloat(duration.toFixed(2)),
      timerId,
    };

    this.info(`Completed: ${timer.operation}`, context);
    this.performanceTimers.delete(timerId);

    return duration;
  }

  /**
   * Log TTS request start
   */
  logTTSStart(text: string, voice: string, speed: number, requestId: string): void {
    this.info("TTS request started", {
      component: "TTSProcessor",
      method: "speak",
      requestId,
      voice,
      speed,
      textLength: text.length,
      textPreview: text.substring(0, 50) + (text.length > 50 ? "..." : ""),
    });
  }

  /**
   * Log TTS request completion
   */
  logTTSComplete(requestId: string, duration: number, success: boolean): void {
    const level = success ? "info" : "error";
    const message = `TTS request ${success ? "completed" : "failed"}`;

    this.logger.log(level, message, {
      component: "TTSProcessor",
      method: "speak",
      requestId,
      duration: parseFloat(duration.toFixed(2)),
      success,
    });
  }

  /**
   * Log streaming performance metrics
   */
  logStreamingMetrics(metrics: {
    requestId: string;
    timeToFirstByte: number;
    timeToFirstAudio: number;
    streamingEfficiency: number;
    cacheHit: boolean;
  }): void {
    this.info("Streaming performance metrics", {
      component: "AudioStreamer",
      method: "handleStreaming",
      ...metrics,
    });
  }

  /**
   * Log cache performance
   */
  logCachePerformance(operation: "hit" | "miss", cacheType: string, context?: LogContext): void {
    this.debug(`Cache ${operation}: ${cacheType}`, {
      component: "CacheManager",
      cacheType,
      operation,
      ...context,
    });
  }

  /**
   * Log buffer adjustments
   */
  logBufferAdjustment(oldSize: number, newSize: number, reason: string): void {
    this.info("Buffer size adjusted", {
      component: "AdaptiveBufferManager",
      method: "adjustBuffer",
      oldSize,
      newSize,
      reason,
    });
  }

  /**
   * Log network retry attempts
   */
  logRetryAttempt(attempt: number, maxAttempts: number, error: Error, delay: number): void {
    this.warn(`Retry attempt ${attempt}/${maxAttempts}`, {
      component: "RetryManager",
      method: "retryWithExponentialBackoff",
      attempt,
      maxAttempts,
      error: error.message,
      delay,
    });
  }

  /**
   * Get current log level
   */
  getLevel(): string {
    return this.logger.level;
  }

  /**
   * Set log level dynamically
   */
  setLevel(level: LogLevel): void {
    this.logger.level = level;
  }

  /**
   * Check if development mode is enabled
   */
  isDevelopmentMode(): boolean {
    return this.developmentMode;
  }

  /**
   * Clean up performance timers
   */
  cleanup(): void {
    this.performanceTimers.clear();
  }
}

// Create default logger instance
const defaultLogger = new TTSLogger({
  level: LogLevel.INFO,
  developmentMode: process.env.NODE_ENV !== "production",
});

// Export default logger and class
export { defaultLogger as logger };
export default TTSLogger;
