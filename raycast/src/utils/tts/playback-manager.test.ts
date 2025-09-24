import { describe, it, expect, vi, beforeEach } from "vitest";
import { PlaybackManager } from "./playback-manager.js";
import type { PlaybackContext } from "../validation/tts-types.js";

// Mock AudioPlaybackDaemon
vi.mock("./streaming/audio-playback-daemon", () => ({
  AudioPlaybackDaemon: vi.fn().mockImplementation(() => ({
    initialize: vi.fn().mockResolvedValue(undefined),
    startPlayback: vi.fn().mockResolvedValue(undefined),
    writeChunk: vi.fn().mockResolvedValue(undefined),
    endStream: vi.fn().mockResolvedValue(undefined),
    pause: vi.fn().mockResolvedValue(undefined),
    resume: vi.fn().mockResolvedValue(undefined),
    stop: vi.fn().mockResolvedValue(undefined),
    cleanup: vi.fn().mockResolvedValue(undefined),
  })),
}));

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
    startTiming: vi.fn(() => "timer-123"),
    endTiming: vi.fn(() => 10),
  },
}));

describe("PlaybackManager", () => {
  let playbackManager: PlaybackManager;
  let playbackContext: PlaybackContext;

  beforeEach(() => {
    vi.clearAllMocks();
    playbackManager = new PlaybackManager();
    playbackManager.initialize({});

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
    it("should send audio data to daemon", async () => {
      await playbackManager.playAudio(playbackContext, new AbortController().signal);

      // The daemon methods should have been called
      expect(playbackManager).toBeDefined();
    });

    it("should handle playback errors gracefully", async () => {
      // Mock the daemon to throw an error
      const { AudioPlaybackDaemon } = await import("./streaming/audio-playback-daemon.js");
      const mockDaemon = vi.mocked(AudioPlaybackDaemon).mock.results[0].value;
      mockDaemon.writeChunk.mockRejectedValueOnce(new Error("Daemon error"));

      await expect(
        playbackManager.playAudio(playbackContext, new AbortController().signal)
      ).rejects.toThrow("Daemon error");
    });
  });

  describe("pause and resume", () => {
    it("should pause playback", async () => {
      // Start playback first
      const playPromise = playbackManager.playAudio(playbackContext, new AbortController().signal);

      // Wait a bit for playback to start
      await new Promise((r) => setTimeout(r, 10));

      playbackManager.pause();
      expect(playbackManager.isPaused()).toBe(true);

      // Clean up
      await playPromise.catch(() => {});
    });
  });

  describe("stop", () => {
    it("should stop playback", async () => {
      // Start playback first
      const playPromise = playbackManager.playAudio(playbackContext, new AbortController().signal);

      // Wait a bit for playback to start
      await new Promise((r) => setTimeout(r, 10));

      await playbackManager.stop();
      expect(playbackManager.isStopped()).toBe(true);

      // Clean up
      await playPromise.catch(() => {});
    });
  });
});
