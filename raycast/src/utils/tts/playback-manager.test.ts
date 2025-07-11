import { describe, it, expect, vi, beforeEach } from "vitest";
import { PlaybackManager } from "./playback-manager";
import type { PlaybackContext } from "../validation/tts-types";
import { EventEmitter } from "events";
import { Writable } from "stream";
import { ChildProcess, spawn } from "child_process";

// Mock child_process
vi.mock("child_process");

// Mock logger
vi.mock("../core/logger", () => ({
  logger: {
    info: vi.fn(),
    warn: vi.fn(),
    debug: vi.fn(),
    error: vi.fn(),
    startTiming: vi.fn(() => "timer-123"),
    endTiming: vi.fn(() => 10),
  },
}));

class MockChildProcess extends EventEmitter {
  stdin = new Writable({
    write(chunk, encoding, callback) {
      callback();
    },
  });
  stdout = new EventEmitter();
  stderr = new EventEmitter();
  killed = false;

  kill = vi.fn(() => {
    this.killed = true;
  });
}

describe("PlaybackManager", () => {
  let playbackManager: PlaybackManager;
  let mockProcess: MockChildProcess;
  let playbackContext: PlaybackContext;

  beforeEach(() => {
    vi.clearAllMocks();
    playbackManager = new PlaybackManager();
    playbackManager.initialize({});

    mockProcess = new MockChildProcess();
    vi.mocked(spawn).mockReturnValue(mockProcess as unknown as ChildProcess);

    playbackContext = {
      audioData: new Uint8Array([1, 2, 3]),
      format: {
        format: "wav",
        sampleRate: 24000,
        channels: 1,
        bitDepth: 16,
        bytesPerSample: 2,
        bytesPerSecond: 48000,
      },
      metadata: { voice: "af_bella", speed: 1, size: 3 },
      playbackOptions: { useHardwareAcceleration: true, backgroundPlayback: true },
    };
  });

  it("should initialize correctly", () => {
    expect(playbackManager.isInitialized()).toBe(true);
  });

  describe("playAudio", () => {
    it("should spawn afplay with correct arguments", async () => {
      // Don't await the promise here, let it run in the background
      playbackManager.playAudio(playbackContext, new AbortController().signal);

      // Give the event loop a chance to run and set up the process
      await new Promise((r) => setTimeout(r, 0));

      expect(spawn).toHaveBeenCalledWith("afplay", ["-"], {
        stdio: ["pipe", "ignore", "ignore"],
        detached: true,
      });
    });

    it("should resolve when playback process closes successfully", async () => {
      const playPromise = playbackManager.playAudio(playbackContext, new AbortController().signal);

      let resolved = false;
      playPromise.then(() => {
        resolved = true;
      });

      await new Promise((r) => setTimeout(r, 10));
      expect(resolved).toBe(false);

      mockProcess.emit("close", 0);
      await expect(playPromise).resolves.toBeUndefined();
    });

    it("should reject when playback process emits an error", async () => {
      const playPromise = playbackManager.playAudio(playbackContext, new AbortController().signal);
      const testError = new Error("Playback failed");

      // Wait for the process to be set up before emitting the error
      await new Promise((r) => setTimeout(r, 0));
      mockProcess.emit("error", testError);

      await expect(playPromise).rejects.toThrow(testError);
    });
  });

  describe("pause and resume", () => {
    it("should kill the process on pause", async () => {
      const playPromise = playbackManager.playAudio(playbackContext, new AbortController().signal);

      // Wait for playback to actually start
      await new Promise((r) => setTimeout(r, 10));

      playbackManager.pause();

      expect(playbackManager.isPaused()).toBe(true);
      expect(mockProcess.kill).toHaveBeenCalled();

      // Clean up
      mockProcess.emit("close", 0);
      await playPromise.catch(() => {}); // catch rejection from pause
    });
  });

  describe("stop", () => {
    it("should kill the process on stop", async () => {
      const playPromise = playbackManager.playAudio(playbackContext, new AbortController().signal);

      // Wait for playback to actually start
      await new Promise((r) => setTimeout(r, 10));

      await playbackManager.stop();
      expect(mockProcess.kill).toHaveBeenCalled();

      // Manually emit close to allow the playPromise to resolve
      mockProcess.emit("close");
      await playPromise.catch(() => {}); // catch rejection from stop
    });
  });
});
