/**
 * Runtime Validation Schemas for Raycast Kokoro TTS
 *
 * This module provides comprehensive runtime validation using zod schemas
 * to ensure type safety and prevent runtime errors from invalid data.
 *
 * Features:
 * - TTS request validation with bounds checking
 * - Response validation for audio data
 * - Configuration validation with safe defaults
 * - Performance metrics validation
 * - Clear error messages for debugging
 * - Automatic data coercion where appropriate
 *
 * @author @darianrosebrook
 * @version 1.0.0
 * @since 2025-01-20
 */

import { z } from "zod";
import { logger } from "../core/logger";

/**
 * Voice option validation schema
 */
export const VoiceOptionSchema = z.string().min(1).max(50);

/**
 * TTS request validation schema
 */
const TTSRequestSchema = z.object({
  text: z
    .string()
    .min(1, "Text cannot be empty")
    .max(2000, "Text cannot exceed 2000 characters")
    .transform((text) => text.trim()),

  voice: VoiceOptionSchema.default("af_heart").describe("Voice to use for TTS synthesis"),

  speed: z
    .number()
    .min(0.1, "Speed must be at least 0.1")
    .max(3.0, "Speed cannot exceed 3.0")
    .default(1.0)
    .describe("Speech speed multiplier"),

  lang: z.string().min(2).max(10).default("en-us").optional().describe("Language code"),

  stream: z.boolean().default(true).optional().describe("Enable streaming mode"),

  format: z.enum(["wav", "pcm"]).default("wav").optional().describe("Audio format"),
});

/**
 * TTS response validation schema
 */
const TTSResponseSchema = z.object({
  audioData: z
    .instanceof(ArrayBuffer)
    .refine((buffer) => buffer.byteLength > 0, "Audio data cannot be empty"),

  format: z.string().min(1).describe("Audio format"),

  duration: z.number().positive().optional().describe("Audio duration in seconds"),

  size: z.number().positive().describe("Audio data size in bytes"),

  voice: VoiceOptionSchema.describe("Voice used for synthesis"),

  speed: z.number().positive().describe("Speed used for synthesis"),
});

/**
 * TTS configuration validation schema
 */
const TTSConfigSchema = z.object({
  voice: VoiceOptionSchema.default("af_heart").describe("Default voice for TTS"),

  speed: z.number().min(0.1).max(3.0).default(1.0).describe("Default speech speed"),

  serverUrl: z
    .string()
    .url("Server URL must be a valid URL")
    .or(z.string().regex(/^https?:\/\/localhost(:\d+)?$/, "Must be a valid URL or localhost"))
    .transform((url) => url.replace(/\/+$/, ""))
    .default("http://localhost:8000")
    .describe("TTS server URL"),

  useStreaming: z.boolean().default(true).describe("Enable streaming mode by default"),

  sentencePauses: z.boolean().default(false).describe("Add pauses between sentences"),

  maxSentenceLength: z
    .number()
    .min(0)
    .max(500)
    .default(0)
    .describe("Maximum sentence length (0 = no limit)"),
});

/**
 * Performance metrics validation schema
 */
const PerformanceMetricsSchema = z.object({
  requestId: z.string().min(1),

  timeToFirstByte: z.number().nonnegative().describe("Time to first byte in milliseconds"),

  timeToFirstAudio: z.number().nonnegative().describe("Time to first audio in milliseconds"),

  streamingEfficiency: z.number().min(0).max(1).describe("Streaming efficiency ratio"),

  cacheHit: z.boolean().describe("Whether request was served from cache"),

  bufferSize: z.number().positive().optional().describe("Buffer size in milliseconds"),

  underruns: z.number().nonnegative().default(0).describe("Number of buffer underruns"),

  retryAttempts: z.number().nonnegative().default(0).describe("Number of retry attempts"),

  totalDuration: z.number().nonnegative().describe("Total request duration in milliseconds"),
});

/**
 * Server health validation schema
 */
export const ServerHealthSchema = z.object({
  status: z.enum(["healthy", "unhealthy", "unknown"]).describe("Server health status"),

  latency: z.number().nonnegative().describe("Server response latency in milliseconds"),

  timestamp: z.number().positive().describe("Health check timestamp"),

  version: z.string().optional().describe("API version"),

  uptime: z.number().nonnegative().optional().describe("Server uptime in seconds"),
});

/**
 * Error context validation schema
 */
export const ErrorContextSchema = z.object({
  code: z.string().min(1).describe("Error code"),

  message: z.string().min(1).describe("Error message"),

  stack: z.string().optional().describe("Error stack trace"),

  context: z.record(z.unknown()).optional().describe("Additional error context"),

  timestamp: z
    .number()
    .positive()
    .default(() => Date.now())
    .describe("Error timestamp"),
});

/**
 * Validation utility functions
 */
export class ValidationUtils {
  /**
   * Validate TTS request with detailed error reporting
   */
  static validateTTSRequest(data: unknown): {
    success: boolean;
    data?: z.infer<typeof TTSRequestSchema>;
    errors?: string[];
  } {
    try {
      const validated = TTSRequestSchema.parse(data);

      logger.debug("TTS request validation successful", {
        component: "ValidationUtils",
        method: "validateTTSRequest",
        textLength: validated.text.length,
        voice: validated.voice,
        speed: validated.speed,
      });

      return {
        success: true,
        data: validated,
      };
    } catch (error) {
      const errors = this.extractZodErrors(error);

      logger.warn("TTS request validation failed", {
        component: "ValidationUtils",
        method: "validateTTSRequest",
        errors,
        rawData: data,
      });

      return {
        success: false,
        errors,
      };
    }
  }

  /**
   * Validate TTS response with error handling
   */
  static validateTTSResponse(data: unknown): {
    success: boolean;
    data?: z.infer<typeof TTSResponseSchema>;
    errors?: string[];
  } {
    try {
      const validated = TTSResponseSchema.parse(data);

      logger.debug("TTS response validation successful", {
        component: "ValidationUtils",
        method: "validateTTSResponse",
        format: validated.format,
        size: validated.size,
      });

      return {
        success: true,
        data: validated,
      };
    } catch (error) {
      const errors = this.extractZodErrors(error);

      logger.error("TTS response validation failed", {
        component: "ValidationUtils",
        method: "validateTTSResponse",
        errors,
      });

      return {
        success: false,
        errors,
      };
    }
  }

  /**
   * Validate TTS configuration with safe defaults
   */
  static validateTTSConfig(data: unknown): {
    success: boolean;
    data?: z.infer<typeof TTSConfigSchema>;
    errors?: string[];
  } {
    try {
      const validated = TTSConfigSchema.parse(data);

      logger.debug("TTS config validation successful", {
        component: "ValidationUtils",
        method: "validateTTSConfig",
        voice: validated.voice,
        serverUrl: validated.serverUrl,
        useStreaming: validated.useStreaming,
      });

      return {
        success: true,
        data: validated,
      };
    } catch (error) {
      const errors = this.extractZodErrors(error);

      logger.warn("TTS config validation failed, using defaults", {
        component: "ValidationUtils",
        method: "validateTTSConfig",
        errors,
      });

      // Return defaults on validation failure
      return {
        success: false,
        errors,
        data: TTSConfigSchema.parse({}), // This will use all defaults
      };
    }
  }

  /**
   * Validate performance metrics
   */
  static validatePerformanceMetrics(data: unknown): {
    success: boolean;
    data?: z.infer<typeof PerformanceMetricsSchema>;
    errors?: string[];
  } {
    try {
      const validated = PerformanceMetricsSchema.parse(data);
      return {
        success: true,
        data: validated,
      };
    } catch (error) {
      const errors = this.extractZodErrors(error);

      logger.warn("Performance metrics validation failed", {
        component: "ValidationUtils",
        method: "validatePerformanceMetrics",
        errors,
      });

      return {
        success: false,
        errors,
      };
    }
  }

  /**
   * Validate server health response
   */
  static validateServerHealth(data: unknown): {
    success: boolean;
    data?: z.infer<typeof ServerHealthSchema>;
    errors?: string[];
  } {
    try {
      const validated = ServerHealthSchema.parse(data);
      return {
        success: true,
        data: validated,
      };
    } catch (error) {
      const errors = this.extractZodErrors(error);

      logger.warn("Server health validation failed", {
        component: "ValidationUtils",
        method: "validateServerHealth",
        errors,
      });

      return {
        success: false,
        errors,
      };
    }
  }

  /**
   * Extract human-readable errors from zod validation errors
   */
  private static extractZodErrors(error: unknown): string[] {
    if (error instanceof z.ZodError) {
      return error.issues.map((issue) => {
        const path = issue.path.join(".");
        return `${path}: ${issue.message}`;
      });
    }

    return [error instanceof Error ? error.message : "Unknown validation error"];
  }
}

/**
 * Type definitions for validated data
 */
export type ValidatedTTSRequest = z.infer<typeof TTSRequestSchema>;
export type ValidatedTTSResponse = z.infer<typeof TTSResponseSchema>;
export type ValidatedTTSConfig = z.infer<typeof TTSConfigSchema>;
export type ValidatedPerformanceMetrics = z.infer<typeof PerformanceMetricsSchema>;
export type ValidatedServerHealth = z.infer<typeof ServerHealthSchema>;
export type ValidatedErrorContext = z.infer<typeof ErrorContextSchema>;

/**
 * Export schemas for external use
 */
// Export all schemas
export { TTSRequestSchema, TTSResponseSchema, TTSConfigSchema, PerformanceMetricsSchema };
