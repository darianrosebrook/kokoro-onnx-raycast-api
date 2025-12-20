import { describe, it, expect, vi, beforeEach } from "vitest";
import { ValidationUtils, VoiceOptionSchema, ErrorContextSchema } from "./validation.js";

// Mock logger
vi.mock("../core/logger", () => ({
  logger: {
    info: vi.fn(),
    warn: vi.fn(),
    debug: vi.fn(),
    error: vi.fn(),
    consoleInfo: vi.fn(),
    consoleDebug: vi.fn(),
    consoleWarn: vi.fn(),
    consoleError: vi.fn(),
  },
}));

describe("ValidationUtils", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("VoiceOptionSchema", () => {
    it("should validate valid voice options", () => {
      expect(() => VoiceOptionSchema.parse("af_heart")).not.toThrow();
      expect(() => VoiceOptionSchema.parse("af_bella")).not.toThrow();
      expect(() => VoiceOptionSchema.parse("a")).not.toThrow(); // min length
      expect(() => VoiceOptionSchema.parse("a".repeat(50))).not.toThrow(); // max length
    });

    it("should reject invalid voice options", () => {
      expect(() => VoiceOptionSchema.parse("")).toThrow();
      expect(() => VoiceOptionSchema.parse("a".repeat(51))).toThrow();
      expect(() => VoiceOptionSchema.parse(123)).toThrow();
      expect(() => VoiceOptionSchema.parse(null)).toThrow();
    });
  });

  describe("validateTTSRequest", () => {
    it("should validate a complete TTS request", () => {
      const request = {
        text: "Hello world",
        voice: "af_heart",
        speed: 1.25,
        lang: "en-us",
        stream: true,
        format: "wav",
      };

      const result = ValidationUtils.validateTTSRequest(request);
      expect(result.success).toBe(true);
      expect(result.data).toEqual({
        text: "Hello world",
        voice: "af_heart",
        speed: 1.25,
        lang: "en-us",
        stream: true,
        format: "wav",
      });
    });

    it("should validate a minimal TTS request with defaults", () => {
      const request = {
        text: "Hello world",
      };

      const result = ValidationUtils.validateTTSRequest(request);
      expect(result.success).toBe(true);
      expect(result.data).toEqual({
        text: "Hello world",
        voice: "af_heart",
        speed: 1.0,
      });
    });

    it("should trim whitespace from text", () => {
      const request = {
        text: "  Hello world  ",
      };

      const result = ValidationUtils.validateTTSRequest(request);
      expect(result.success).toBe(true);
      expect(result.data?.text).toBe("Hello world");
    });

    it("should reject empty text", () => {
      const request = {
        text: "",
        voice: "af_heart",
      };

      const result = ValidationUtils.validateTTSRequest(request);
      expect(result.success).toBe(false);
      expect(result.errors).toContain("text: Text cannot be empty");
    });

    it("should reject text that is too long", () => {
      const request = {
        text: "a".repeat(2001),
        voice: "af_heart",
      };

      const result = ValidationUtils.validateTTSRequest(request);
      expect(result.success).toBe(false);
      expect(result.errors).toContain("text: Text cannot exceed 2000 characters");
    });

    it("should reject invalid speed values", () => {
      const request = {
        text: "Hello world",
        speed: 0.05, // Too low
      };

      const result = ValidationUtils.validateTTSRequest(request);
      expect(result.success).toBe(false);
      expect(result.errors).toContain("speed: Speed must be at least 0.1");
    });

    it("should reject speed values that are too high", () => {
      const request = {
        text: "Hello world",
        speed: 3.5, // Too high
      };

      const result = ValidationUtils.validateTTSRequest(request);
      expect(result.success).toBe(false);
      expect(result.errors).toContain("speed: Speed cannot exceed 3.0");
    });

    it("should reject invalid format values", () => {
      const request = {
        text: "Hello world",
        format: "mp3", // Invalid format
      };

      const result = ValidationUtils.validateTTSRequest(request);
      expect(result.success).toBe(false);
      expect(result.errors).toContain(
        "format: Invalid enum value. Expected 'wav' | 'pcm', received 'mp3'"
      );
    });
  });

  describe("validateTTSResponse", () => {
    it("should validate a complete TTS response", () => {
      const audioData = new ArrayBuffer(1024);
      const response = {
        audioData,
        format: "wav",
        duration: 2.5,
        size: 1024,
        voice: "af_heart",
        speed: 1.0,
      };

      const result = ValidationUtils.validateTTSResponse(response);
      expect(result.success).toBe(true);
      expect(result.data).toEqual(response);
    });

    it("should reject empty audio data", () => {
      const audioData = new ArrayBuffer(0);
      const response = {
        audioData,
        format: "wav",
        size: 0,
        voice: "af_heart",
        speed: 1.0,
      };

      const result = ValidationUtils.validateTTSResponse(response);
      expect(result.success).toBe(false);
      expect(result.errors).toContain("audioData: Audio data cannot be empty");
    });

    it("should reject invalid audio data type", () => {
      const response = {
        audioData: "not an array buffer",
        format: "wav",
        size: 1024,
        voice: "af_heart",
        speed: 1.0,
      };

      const result = ValidationUtils.validateTTSResponse(response);
      expect(result.success).toBe(false);
      expect(result.errors).toContain("audioData: Input not instance of ArrayBuffer");
    });

    it("should reject negative size", () => {
      const audioData = new ArrayBuffer(1024);
      const response = {
        audioData,
        format: "wav",
        size: -1,
        voice: "af_heart",
        speed: 1.0,
      };

      const result = ValidationUtils.validateTTSResponse(response);
      expect(result.success).toBe(false);
      expect(result.errors).toContain("size: Number must be greater than 0");
    });
  });

  describe("validateTTSConfig", () => {
    it("should validate a complete TTS config", () => {
      const config = {
        voice: "af_heart",
        speed: 1.25,
        serverUrl: "http://localhost:8080",
        useStreaming: true,
        sentencePauses: false,
        maxSentenceLength: 100,
      };

      const result = ValidationUtils.validateTTSConfig(config);
      expect(result.success).toBe(true);
      expect(result.data).toEqual(config);
    });

    it("should validate config with defaults", () => {
      const config = {};

      const result = ValidationUtils.validateTTSConfig(config);
      expect(result.success).toBe(true);
      expect(result.data).toEqual({
        voice: "af_heart",
        speed: 1.0,
        serverUrl: "http://localhost:8080",
        useStreaming: true,
        sentencePauses: false,
        maxSentenceLength: 0,
      });
    });

    it("should validate localhost URLs", () => {
      const config = {
        serverUrl: "http://localhost:3000",
      };

      const result = ValidationUtils.validateTTSConfig(config);
      expect(result.success).toBe(true);
      expect(result.data?.serverUrl).toBe("http://localhost:3000");
    });

    it("should normalize server URLs by removing trailing slashes", () => {
      const config = {
        serverUrl: "http://localhost:8080/",
      };

      const result = ValidationUtils.validateTTSConfig(config);
      expect(result.success).toBe(true);
      expect(result.data?.serverUrl).toBe("http://localhost:8080");
    });

    it("should reject invalid server URLs", () => {
      const config = {
        serverUrl: "not-a-url",
      };

      const result = ValidationUtils.validateTTSConfig(config);
      expect(result.success).toBe(false);
      expect(result.errors).toContain("serverUrl: Server URL must be a valid URL");
    });

    it("should reject invalid max sentence length", () => {
      const config = {
        maxSentenceLength: 501, // Too high
      };

      const result = ValidationUtils.validateTTSConfig(config);
      expect(result.success).toBe(false);
      expect(result.errors).toContain(
        "maxSentenceLength: Number must be less than or equal to 500"
      );
    });
  });

  describe("validatePerformanceMetrics", () => {
    it("should validate complete performance metrics", () => {
      const metrics = {
        requestId: "test-123",
        timeToFirstByte: 150,
        timeToFirstAudio: 300,
        streamingEfficiency: 0.95,
        cacheHit: true,
        bufferSize: 400,
        underruns: 0,
        retryAttempts: 1,
        totalDuration: 2500,
      };

      const result = ValidationUtils.validatePerformanceMetrics(metrics);
      expect(result.success).toBe(true);
      expect(result.data).toEqual(metrics);
    });

    it("should validate metrics with defaults", () => {
      const metrics = {
        requestId: "test-123",
        timeToFirstByte: 150,
        timeToFirstAudio: 300,
        streamingEfficiency: 0.95,
        cacheHit: true,
        totalDuration: 2500,
      };

      const result = ValidationUtils.validatePerformanceMetrics(metrics);
      expect(result.success).toBe(true);
      expect(result.data).toEqual({
        ...metrics,
        underruns: 0,
        retryAttempts: 0,
      });
    });

    it("should reject invalid streaming efficiency", () => {
      const metrics = {
        requestId: "test-123",
        timeToFirstByte: 150,
        timeToFirstAudio: 300,
        streamingEfficiency: 1.5, // Too high
        cacheHit: true,
        totalDuration: 2500,
      };

      const result = ValidationUtils.validatePerformanceMetrics(metrics);
      expect(result.success).toBe(false);
      expect(result.errors).toContain(
        "streamingEfficiency: Number must be less than or equal to 1"
      );
    });

    it("should reject negative values", () => {
      const metrics = {
        requestId: "test-123",
        timeToFirstByte: -50,
        timeToFirstAudio: 300,
        streamingEfficiency: 0.95,
        cacheHit: true,
        totalDuration: 2500,
      };

      const result = ValidationUtils.validatePerformanceMetrics(metrics);
      expect(result.success).toBe(false);
      expect(result.errors).toContain("timeToFirstByte: Number must be greater than or equal to 0");
    });
  });

  describe("validateServerHealth", () => {
    it("should validate complete server health data", () => {
      const health = {
        status: "healthy",
        latency: 50,
        timestamp: Date.now(),
        version: "1.0.0",
        uptime: 3600,
      };

      const result = ValidationUtils.validateServerHealth(health);
      expect(result.success).toBe(true);
      expect(result.data).toEqual(health);
    });

    it("should validate minimal server health data", () => {
      const health = {
        status: "healthy",
        latency: 50,
        timestamp: Date.now(),
      };

      const result = ValidationUtils.validateServerHealth(health);
      expect(result.success).toBe(true);
      expect(result.data).toEqual(health);
    });

    it("should reject invalid status values", () => {
      const health = {
        status: "invalid-status",
        latency: 50,
        timestamp: Date.now(),
      };

      const result = ValidationUtils.validateServerHealth(health);
      expect(result.success).toBe(false);
      expect(result.errors).toContain(
        "status: Invalid enum value. Expected 'healthy' | 'unhealthy' | 'unknown', received 'invalid-status'"
      );
    });

    it("should reject negative latency", () => {
      const health = {
        status: "healthy",
        latency: -10,
        timestamp: Date.now(),
      };

      const result = ValidationUtils.validateServerHealth(health);
      expect(result.success).toBe(false);
      expect(result.errors).toContain("latency: Number must be greater than or equal to 0");
    });
  });

  describe("ErrorContextSchema", () => {
    it("should validate complete error context", () => {
      const errorContext = {
        code: "NETWORK_ERROR",
        message: "Connection failed",
        stack: "Error: Connection failed\n    at fetch",
        context: { url: "http://localhost:8080" },
        timestamp: Date.now(),
      };

      expect(() => ErrorContextSchema.parse(errorContext)).not.toThrow();
    });

    it("should validate minimal error context with default timestamp", () => {
      const errorContext = {
        code: "NETWORK_ERROR",
        message: "Connection failed",
      };

      const result = ErrorContextSchema.parse(errorContext);
      expect(result.code).toBe("NETWORK_ERROR");
      expect(result.message).toBe("Connection failed");
      expect(result.timestamp).toBeGreaterThan(0);
    });

    it("should reject empty code", () => {
      const errorContext = {
        code: "",
        message: "Connection failed",
      };

      expect(() => ErrorContextSchema.parse(errorContext)).toThrow();
    });

    it("should reject empty message", () => {
      const errorContext = {
        code: "NETWORK_ERROR",
        message: "",
      };

      expect(() => ErrorContextSchema.parse(errorContext)).toThrow();
    });
  });

  describe("Error Handling", () => {
    it("should handle non-zod errors gracefully", () => {
      // This tests the extractZodErrors method indirectly
      const invalidData = null;
      const result = ValidationUtils.validateTTSRequest(invalidData);
      expect(result.success).toBe(false);
      expect(result.errors).toBeDefined();
      expect(result.errors?.length).toBeGreaterThan(0);
    });

    it("should provide detailed error messages for multiple validation failures", () => {
      const invalidRequest = {
        text: "",
        speed: 5.0,
        format: "invalid",
      };

      const result = ValidationUtils.validateTTSRequest(invalidRequest);
      expect(result.success).toBe(false);
      expect(result.errors?.length).toBeGreaterThan(1);
      expect(result.errors).toContain("text: Text cannot be empty");
      expect(result.errors).toContain("speed: Speed cannot exceed 3.0");
      expect(result.errors).toContain(
        "format: Invalid enum value. Expected 'wav' | 'pcm', received 'invalid'"
      );
    });
  });
});
