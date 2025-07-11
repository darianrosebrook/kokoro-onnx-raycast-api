import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { RetryManager } from "./retry-manager";

// Mock logger
vi.mock("../core/logger", () => ({
  logger: {
    info: vi.fn(),
    warn: vi.fn(),
    debug: vi.fn(),
    error: vi.fn(),
  },
}));

describe("RetryManager", () => {
  let retryManager: RetryManager;

  beforeEach(() => {
    retryManager = new RetryManager();
    retryManager.initialize({});
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("should succeed on the first attempt", async () => {
    const operation = vi.fn().mockResolvedValue("success");
    const result = await retryManager.executeWithRetry(operation, "test");

    expect(operation).toHaveBeenCalledTimes(1);
    expect(result.success).toBe(true);
    expect(result.data).toBe("success");
    expect(result.error).toBeNull();
  });

  it("should succeed after a few retries", async () => {
    const operation = vi
      .fn()
      .mockRejectedValueOnce(new Error("fail 1"))
      .mockRejectedValueOnce(new Error("fail 2"))
      .mockResolvedValue("success");

    const retryPromise = retryManager.executeWithRetry(operation, "test-retry");

    // Let the promise chain start
    await vi.advanceTimersToNextTimerAsync(); // First failure, schedule delay
    await vi.advanceTimersToNextTimerAsync(); // Second failure, schedule delay

    const result = await retryPromise;

    expect(operation).toHaveBeenCalledTimes(3);
    expect(result.success).toBe(true);
    expect(result.data).toBe("success");
  });

  it("should fail after all retries", async () => {
    const operation = vi.fn().mockRejectedValue(new Error("persistent failure"));

    const retryPromise = retryManager.executeWithRetry(operation, "test-fail", { maxAttempts: 2 });

    // Advance timers
    await vi.runAllTimersAsync();

    const result = await retryPromise;

    expect(operation).toHaveBeenCalledTimes(3); // 1 initial + 2 retries
    expect(result.success).toBe(false);
    expect(result.data).toBeNull();
    expect(result.error?.message).toBe("persistent failure");
  });

  it("should not retry on a non-retryable error", async () => {
    const operation = vi.fn().mockRejectedValue(new Error("fatal"));
    const retryCondition = (error: Error) => error.message !== "fatal";

    const result = await retryManager.executeWithRetry(operation, "test-fatal", { retryCondition });

    expect(operation).toHaveBeenCalledTimes(1);
    expect(result.success).toBe(false);
    expect(result.error?.message).toBe("fatal");
  }, 10000); // Increase timeout

  describe("Circuit Breaker", () => {
    it("should open the circuit after enough failures", async () => {
      const operation = vi.fn().mockRejectedValue(new Error("fail"));

      // Fail enough times to open the circuit
      for (let i = 0; i < 5; i++) {
        await retryManager.executeWithRetry(operation, "trip-circuit", { maxAttempts: 0 });
      }

      const state = retryManager.getCircuitBreakerState();
      expect(state.isOpen).toBe(true);

      // This attempt should be blocked
      const result = await retryManager.executeWithRetry(operation, "blocked");
      expect(operation).toHaveBeenCalledTimes(5); // Not called again
      expect(result.circuitBreakerOpen).toBe(true);
      expect(result.error?.message).toBe("Circuit breaker is open");
    });

    it("should close the circuit after a timeout", async () => {
      const operation = vi.fn().mockRejectedValue(new Error("fail"));
      const successOperation = vi.fn().mockResolvedValue("ok");

      // Trip the circuit
      for (let i = 0; i < 5; i++) {
        await retryManager.executeWithRetry(operation, "trip-circuit", { maxAttempts: 0 });
      }
      expect(retryManager.getCircuitBreakerState().isOpen).toBe(true);

      // Wait for the timeout
      await vi.advanceTimersByTimeAsync(60001);

      // A new request should be allowed and reset the brea[ker on success
      await retryManager.executeWithRetry(successOperation, "half-open-success");

      expect(retryManager.getCircuitBreakerState().isOpen).toBe(false);
    });
  });
});
