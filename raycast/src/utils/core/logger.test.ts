import { describe, it, expect, vi, beforeEach } from "vitest";
import { TTSLogger, LogLevel } from "./logger.js";

// Mock winston to prevent actual logging
vi.mock("winston", () => ({
  createLogger: vi.fn(() => ({
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
    log: vi.fn(),
    level: "info",
  })),
  format: {
    combine: vi.fn(),
    timestamp: vi.fn(),
    printf: vi.fn(),
    colorize: vi.fn(),
    json: vi.fn(),
  },
  transports: {
    Console: vi.fn(),
    File: vi.fn(),
  },
}));

describe("TTSLogger", () => {
  let logger: TTSLogger;

  beforeEach(() => {
    vi.clearAllMocks();
    logger = new TTSLogger({ developmentMode: true });
  });

  it("should instantiate without errors", () => {
    expect(() => new TTSLogger()).not.toThrow();
  });

  it("should instantiate with custom config", () => {
    const logger = new TTSLogger({
      level: LogLevel.DEBUG,
      developmentMode: true,
    });
    expect(logger).toBeInstanceOf(TTSLogger);
  });

  it("should log error messages without throwing", () => {
    expect(() => logger.error("Test error message")).not.toThrow();
  });

  it("should log warning messages without throwing", () => {
    expect(() => logger.warn("Test warning message")).not.toThrow();
  });

  it("should log info messages without throwing", () => {
    expect(() => logger.info("Test info message")).not.toThrow();
  });

  it("should log debug messages without throwing", () => {
    expect(() => logger.debug("Test debug message")).not.toThrow();
  });

  it("should accept context information", () => {
    const context = {
      component: "TestComponent",
      method: "testMethod",
      requestId: "req-123",
      userId: "user-456",
    };

    expect(() => logger.info("Test message with context", context)).not.toThrow();
  });

  it("should accept error objects", () => {
    const testError = new Error("Test error");

    expect(() => logger.error("Test error message", undefined, testError)).not.toThrow();
  });

  it("should handle different log levels", () => {
    // Test with different log levels
    const errorLogger = new TTSLogger({ level: LogLevel.ERROR });
    const warnLogger = new TTSLogger({ level: LogLevel.WARN });
    const infoLogger = new TTSLogger({ level: LogLevel.INFO });
    const debugLogger = new TTSLogger({ level: LogLevel.DEBUG });

    expect(errorLogger).toBeDefined();
    expect(warnLogger).toBeDefined();
    expect(infoLogger).toBeDefined();
    expect(debugLogger).toBeDefined();
  });

  it("should handle performance timing", () => {
    const timerId = "test-timer";

    // Start timing
    expect(() => logger.startTiming(timerId)).not.toThrow();
  });

  it("should handle empty context", () => {
    expect(() => logger.info("Message with empty context", {})).not.toThrow();
  });

  it("should handle undefined context", () => {
    expect(() => logger.info("Message with undefined context", undefined)).not.toThrow();
  });

  it("should handle large context objects", () => {
    const largeContext = {
      data: Array.from({ length: 100 }, (_, i) => ({ index: i, value: `item-${i}` })),
      metadata: {
        source: "test",
        timestamp: new Date().toISOString(),
        nested: {
          level1: {
            level2: {
              level3: "deep value",
            },
          },
        },
      },
    };

    expect(() => logger.info("Message with large context", largeContext)).not.toThrow();
  });

  it("should handle concurrent logging", async () => {
    const logPromises = Array.from({ length: 50 }, (_, i) =>
      Promise.resolve().then(() => logger.info(`Concurrent log ${i}`))
    );

    await expect(Promise.all(logPromises)).resolves.not.toThrow();
  });

  it("should handle rapid successive logging", () => {
    expect(() => {
      for (let i = 0; i < 100; i++) {
        logger.debug(`Rapid log message ${i}`);
      }
    }).not.toThrow();
  });

  it("should handle special characters in messages", () => {
    const specialMessages = [
      "Message with unicode: 🚀 éñ∑∂🔥",
      "Message with newlines:\nline1\nline2",
      "Message with tabs:\tcol1\tcol2",
      "Message with quotes: \"single\" and 'double'",
      "Message with slashes: \\ and /",
    ];

    expect(() => {
      specialMessages.forEach((message) => {
        logger.info(message);
      });
    }).not.toThrow();
  });

  it("should handle numeric context values", () => {
    const numericContext = {
      count: 42,
      ratio: 3.14159,
      flag: true,
      zero: 0,
      negative: -123,
      large: Number.MAX_SAFE_INTEGER,
    };

    expect(() => logger.info("Numeric context test", numericContext)).not.toThrow();
  });

  it("should handle null and undefined in context", () => {
    const mixedContext = {
      nullValue: null,
      undefinedValue: undefined,
      emptyString: "",
      zero: 0,
      false: false,
    };

    expect(() => logger.info("Mixed context test", mixedContext)).not.toThrow();
  });

  it("should handle circular references in context", () => {
    const circularObj: any = { name: "test" };
    circularObj.self = circularObj;

    expect(() => logger.info("Circular reference test", { data: circularObj })).not.toThrow();
  });

  it("should handle very long messages efficiently", () => {
    const largeMessage = "x".repeat(10000);

    const startTime = Date.now();
    logger.info(largeMessage);
    const endTime = Date.now();

    // Should complete within reasonable time (less than 100ms for 10KB)
    expect(endTime - startTime).toBeLessThan(100);
  });

  it("should support multiple loggers with different configurations", () => {
    const devLogger = new TTSLogger({ developmentMode: true, level: LogLevel.DEBUG });
    const prodLogger = new TTSLogger({ developmentMode: false, level: LogLevel.ERROR });

    expect(devLogger).toBeDefined();
    expect(prodLogger).toBeDefined();

    // Both should work without throwing
    expect(() => devLogger.debug("Dev debug")).not.toThrow();
    expect(() => prodLogger.debug("Prod debug")).not.toThrow();
  });
});
