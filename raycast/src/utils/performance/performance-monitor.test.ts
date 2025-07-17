import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { PerformanceMonitor } from "./performance-monitor";
import { TTSEvent, TTSProcessorConfig } from "../validation/tts-types";

// Mock logger
vi.mock("../core/logger", () => ({
  logger: {
    info: vi.fn(),
    warn: vi.fn(),
    debug: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock validation
vi.mock("../validation/validation", () => ({
  ValidationUtils: {
    validatePerformanceMetrics: vi.fn((data) => ({ success: true, data })),
  },
}));

describe("PerformanceMonitor", () => {
  let monitor: PerformanceMonitor;
  let mockConfig: TTSProcessorConfig;

  beforeEach(() => {
    vi.clearAllMocks();
    mockConfig = {
      developmentMode: true,
      format: "wav",
      onStatusUpdate: vi.fn(),
      voice: "af_heart",
      speed: 1.0,
      serverUrl: "https://api.tts.com",
      daemonUrl: "http://localhost:8081",
      useStreaming: true,
      sentencePauses: true,
      maxSentenceLength: 100,
      performanceProfile: "balanced",
      autoSelectProfile: false,
      showPerformanceMetrics: false,
    };
    monitor = new PerformanceMonitor(mockConfig);
  });

  afterEach(async () => {
    await monitor.cleanup();
  });

  describe("Constructor and Initialization", () => {
    it("should construct with default configuration", () => {
      const defaultMonitor = new PerformanceMonitor();
      expect(defaultMonitor.name).toBe("PerformanceMonitor");
      expect(defaultMonitor.version).toBe("1.0.0");
      expect(defaultMonitor.isInitialized()).toBe(false);
    });

    it("should construct with custom configuration", () => {
      const customConfig = {
        developmentMode: true,
        adaptiveBuffering: false,
      };
      const customMonitor = new PerformanceMonitor(customConfig);
      expect(customMonitor.isInitialized()).toBe(false);
    });

    it("should initialize successfully", async () => {
      await monitor.initialize(mockConfig);
      expect(monitor.isInitialized()).toBe(true);
    });

    it("should throw error when tracking without initialization", () => {
      expect(() => monitor.startTracking("test-request")).toThrow(
        "Performance monitor not initialized"
      );
    });
  });

  describe("Performance Tracking", () => {
    beforeEach(async () => {
      await monitor.initialize(mockConfig);
    });

    it("should start tracking a request", () => {
      monitor.startTracking("test-request");
      expect(monitor.getActiveSessionsCount()).toBe(1);
      expect(monitor.getSessionInfo("test-request")).toBeDefined();
    });

    it("should record metrics for a request", () => {
      monitor.startTracking("test-request");
      monitor.recordMetric("timeToFirstByte", 150);
      monitor.recordMetric("timeToFirstAudio", 300);

      const session = monitor.getSessionInfo("test-request");
      expect(session?.metrics.timeToFirstByte).toBe(150);
      expect(session?.metrics.timeToFirstAudio).toBe(300);
    });

    it("should end tracking and return metrics", () => {
      monitor.startTracking("test-request");
      monitor.recordMetric("timeToFirstByte", 150);
      monitor.recordMetric("timeToFirstAudio", 300);

      const metrics = monitor.endTracking("test-request");
      expect(metrics.timeToFirstByte).toBe(150);
      expect(metrics.timeToFirstAudio).toBe(300);
      expect(monitor.getActiveSessionsCount()).toBe(0);
    });

    it("should handle multiple concurrent sessions", () => {
      monitor.startTracking("request-1");
      monitor.startTracking("request-2");
      monitor.startTracking("request-3");

      expect(monitor.getActiveSessionsCount()).toBe(3);

      monitor.endTracking("request-1");
      expect(monitor.getActiveSessionsCount()).toBe(2);

      monitor.endTracking("request-2");
      monitor.endTracking("request-3");
      expect(monitor.getActiveSessionsCount()).toBe(0);
    });

    it("should update global metrics", () => {
      monitor.startTracking("test-request");
      monitor.recordMetric("timeToFirstByte", 150);
      monitor.recordMetric("streamingEfficiency", 0.95);

      const globalMetrics = monitor.getMetrics();
      expect(globalMetrics.timeToFirstByte).toBe(150);
      expect(globalMetrics.streamingEfficiency).toBe(0.95);
    });
  });

  describe("Event System", () => {
    beforeEach(async () => {
      await monitor.initialize(mockConfig);
    });

    it("should add and remove event listeners", () => {
      const listener = vi.fn();
      monitor.addEventListener(TTSEvent.STREAMING_STARTED, listener);
      monitor.removeEventListener(TTSEvent.STREAMING_STARTED, listener);

      // Should not throw when removing non-existent listener
      expect(() => monitor.removeEventListener(TTSEvent.STREAMING_STARTED, vi.fn())).not.toThrow();
    });

    it("should emit events to registered listeners", () => {
      const listener = vi.fn();
      monitor.addEventListener(TTSEvent.STREAMING_STARTED, listener);

      monitor.emitEvent(TTSEvent.STREAMING_STARTED, { requestId: "test" });
      expect(listener).toHaveBeenCalledWith({
        event: TTSEvent.STREAMING_STARTED,
        data: { requestId: "test" },
        timestamp: expect.any(Number),
      });
    });

    it("should handle multiple listeners for the same event", () => {
      const listener1 = vi.fn();
      const listener2 = vi.fn();
      monitor.addEventListener(TTSEvent.STREAMING_STARTED, listener1);
      monitor.addEventListener(TTSEvent.STREAMING_STARTED, listener2);

      monitor.emitEvent(TTSEvent.STREAMING_STARTED, { requestId: "test" });
      expect(listener1).toHaveBeenCalledTimes(1);
      expect(listener2).toHaveBeenCalledTimes(1);
    });
  });

  describe("Performance Analysis", () => {
    beforeEach(async () => {
      await monitor.initialize(mockConfig);
    });

    it("should generate recommendations based on metrics", () => {
      monitor.startTracking("test-request");
      monitor.recordMetric("timeToFirstAudio", 800); // Above threshold
      monitor.recordMetric("streamingEfficiency", 0.7); // Below threshold
      monitor.recordMetric("underrunCount", 5); // Above threshold

      const recommendations = monitor.getRecommendations();
      expect(recommendations.length).toBeGreaterThan(0);
      expect(recommendations.some((r) => r.type === "buffer")).toBe(true);
      expect(recommendations.some((r) => r.type === "network")).toBe(true);
    });

    it("should update performance thresholds", () => {
      const newThresholds = {
        targetTTFA: 500,
        targetEfficiency: 0.98,
        maxLatency: 800,
      };

      monitor.updateThresholds(newThresholds);
      const thresholds = monitor.getThresholds();
      expect(thresholds.targetTTFA).toBe(500);
      expect(thresholds.targetEfficiency).toBe(0.98);
      expect(thresholds.maxLatency).toBe(800);
    });

    it("should calculate cache hit rate correctly", () => {
      monitor.startTracking("test-request");
      monitor.recordMetric("cacheHits", 8);
      monitor.recordMetric("cacheMisses", 2);
      monitor.endTracking("test-request");

      const metrics = monitor.getMetrics();
      expect(metrics.cacheHits).toBe(8);
      expect(metrics.cacheMisses).toBe(2);
    });

    it("should calculate success rate correctly", () => {
      monitor.startTracking("test-request");
      monitor.recordMetric("streamingSuccesses", 9);
      monitor.recordMetric("streamingFailures", 1);

      const metrics = monitor.getMetrics();
      expect(metrics.streamingSuccesses).toBe(9);
      expect(metrics.streamingFailures).toBe(1);
    });
  });

  describe("Session Management", () => {
    beforeEach(async () => {
      await monitor.initialize(mockConfig);
    });

    it("should clear all sessions", () => {
      monitor.startTracking("request-1");
      monitor.startTracking("request-2");
      expect(monitor.getActiveSessionsCount()).toBe(2);

      monitor.clearSessions();
      expect(monitor.getActiveSessionsCount()).toBe(0);
    });

    it("should return null for non-existent session", () => {
      expect(monitor.getSessionInfo("non-existent")).toBeNull();
    });

    it("should handle session cleanup on end tracking", () => {
      monitor.startTracking("test-request");
      expect(monitor.getActiveSessionsCount()).toBe(1);

      monitor.endTracking("test-request");
      expect(monitor.getActiveSessionsCount()).toBe(0);
      expect(monitor.getSessionInfo("test-request")).toBeNull();
    });
  });

  describe("Performance Reporting", () => {
    beforeEach(async () => {
      await monitor.initialize(mockConfig);
    });

    it("should log performance report without errors", () => {
      monitor.startTracking("test-request");
      monitor.recordMetric("timeToFirstAudio", 300);
      monitor.recordMetric("streamingEfficiency", 0.95);
      monitor.endTracking("test-request");

      expect(() => monitor.logPerformanceReport()).not.toThrow();
    });

    it("should handle reporting with no active sessions", () => {
      expect(() => monitor.logPerformanceReport()).not.toThrow();
    });
  });

  describe("Error Handling", () => {
    it("should handle cleanup when not initialized", async () => {
      expect(() => monitor.cleanup()).not.toThrow();
    });

    it("should handle end tracking for non-existent session", async () => {
      await monitor.initialize(mockConfig);
      expect(() => monitor.endTracking("non-existent")).toThrow(
        "No active session found for request: non-existent"
      );
    });

    it("should handle record metric for non-existent session", async () => {
      await monitor.initialize(mockConfig);
      expect(() => monitor.recordMetric("testMetric", 100)).not.toThrow();
    });
  });
});
