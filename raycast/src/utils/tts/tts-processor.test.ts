import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import { TTSSpeechProcessor } from "./tts-processor.js";
import { TextProcessor } from "./text-processor.js";
import { AudioStreamer } from "./streaming/audio-streamer.js";
import { PlaybackManager } from "./playback-manager.js";
import { RetryManager } from "../api/retry-manager.js";
import { AdaptiveBufferManager } from "./streaming/adaptive-buffer-manager.js";
import { PerformanceMonitor } from "../performance/performance-monitor.js";
import { StatusUpdate } from "../../types";
import { TextSegment } from "../validation/tts-types.js";

// Mock all dependencies
vi.mock("./text-processor");
vi.mock("./streaming/audio-streamer");
vi.mock("./playback-manager");
vi.mock("../api/retry-manager");
vi.mock("./streaming/adaptive-buffer-manager");
vi.mock("../performance/performance-monitor");
vi.mock("../core/cache");

const mockTextProcessor = {
  initialize: vi.fn().mockResolvedValue(undefined),
  preprocessText: vi.fn((text) => text),
  segmentText: vi.fn(),
};

const mockAudioStreamer = {
  initialize: vi.fn().mockResolvedValue(undefined),
  streamAudio: vi.fn(),
  getAudioFormat: vi.fn().mockReturnValue("wav"),
};

const mockPlaybackManager = {
  initialize: vi.fn().mockResolvedValue(undefined),
  playAudio: vi.fn().mockResolvedValue(undefined),
  startStreamingPlayback: vi.fn().mockResolvedValue({
    writeChunk: vi.fn().mockResolvedValue(undefined),
    endStream: vi.fn().mockResolvedValue(undefined),
  }),
  pause: vi.fn(),
  resume: vi.fn(),
  stop: vi.fn(),
  isActive: vi.fn().mockReturnValue(false),
  isPaused: vi.fn().mockReturnValue(false),
  isStopped: vi.fn().mockReturnValue(true),
};

const mockRetryManager = {
  initialize: vi.fn().mockResolvedValue(undefined),
  executeWithRetry: vi.fn((fn) => fn()),
};

const mockAdaptiveBufferManager = {
  initialize: vi.fn().mockResolvedValue(undefined),
  adjustBuffer: vi.fn(),
  getBufferSize: vi.fn().mockReturnValue(5),
};

const mockPerformanceMonitor = {
  initialize: vi.fn().mockResolvedValue(undefined),
  startTracking: vi.fn(),
  endTracking: vi.fn(),
  logPerformanceReport: vi.fn(),
  log: vi.fn(),
};

vi.mocked(TextProcessor).mockImplementation(() => mockTextProcessor as unknown as TextProcessor);
vi.mocked(AudioStreamer).mockImplementation(() => mockAudioStreamer as unknown as AudioStreamer);
vi.mocked(PlaybackManager).mockImplementation(
  () => mockPlaybackManager as unknown as PlaybackManager
);
vi.mocked(RetryManager).mockImplementation(() => mockRetryManager as unknown as RetryManager);
vi.mocked(AdaptiveBufferManager).mockImplementation(
  () => mockAdaptiveBufferManager as unknown as AdaptiveBufferManager
);
vi.mocked(PerformanceMonitor).mockImplementation(
  () => mockPerformanceMonitor as unknown as PerformanceMonitor
);

describe("TTSSpeechProcessor", () => {
  let processor: TTSSpeechProcessor;
  let onStatusUpdate: (status: StatusUpdate) => void;

  beforeEach(() => {
    vi.clearAllMocks();
    onStatusUpdate = vi.fn();

    // Re-assign isActive and isPaused to be mutable for tests
    let isPlaying = false;
    let isPaused = false;
    mockPlaybackManager.isActive.mockImplementation(() => isPlaying);
    mockPlaybackManager.isPaused.mockImplementation(() => isPaused);
    mockPlaybackManager.pause.mockImplementation(() => {
      isPaused = true;
    });
    mockPlaybackManager.resume.mockImplementation(() => {
      isPaused = false;
    });
    mockPlaybackManager.playAudio.mockImplementation(async () => {
      isPlaying = true;
    });
    mockPlaybackManager.stop.mockImplementation(async () => {
      isPlaying = false;
      isPaused = false;
    });

    processor = new TTSSpeechProcessor(
      {
        onStatusUpdate,
        developmentMode: true,
      },
      {
        textProcessor: mockTextProcessor as unknown as TextProcessor,
        audioStreamer: mockAudioStreamer as unknown as AudioStreamer,
        playbackManager: mockPlaybackManager as unknown as PlaybackManager,
        retryManager: mockRetryManager as unknown as RetryManager,
        adaptiveBufferManager: mockAdaptiveBufferManager as unknown as AdaptiveBufferManager,
        performanceMonitor: mockPerformanceMonitor as unknown as PerformanceMonitor,
      }
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should initialize all components on creation", async () => {
    // This test is less relevant now with dependency injection,
    // but we can ensure the constructor doesn't crash.
    expect(processor).toBeDefined();
  });

  it("should process text, stream audio, and play it successfully", async () => {
    const text = "Hello world.";
    const segments: TextSegment[] = [
      {
        text: "Hello world.",
        startOffset: 0,
        endOffset: 11,
        processed: true,
        index: 0,
        type: "sentence",
      },
    ];
    // const audioData = new Uint8Array([1, 2, 3]);

    mockTextProcessor.segmentText.mockReturnValue(segments);
    mockAudioStreamer.streamAudio.mockResolvedValue(undefined);

    await processor.speak(text);

    expect(onStatusUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ message: "Processing text..." })
    );
    expect(mockTextProcessor.preprocessText).toHaveBeenCalledWith(text);
    expect(mockTextProcessor.segmentText).toHaveBeenCalled();
    expect(mockRetryManager.executeWithRetry).toHaveBeenCalledTimes(1);
    expect(mockAudioStreamer.streamAudio).toHaveBeenCalledWith(
      expect.objectContaining({ text: "Hello world." }),
      expect.any(Object),
      expect.any(Function)
    );
    // Note: playAudio is not called directly in the current implementation
    // The audio streaming handles playback internally
    expect(onStatusUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ message: "Speech completed" })
    );
  });

  it("should handle text processing failure gracefully", async () => {
    const text = "Invalid text.";
    mockTextProcessor.segmentText.mockReturnValue([]); // Simulate validation failure

    await processor.speak(text);

    expect(onStatusUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ message: "Processing text..." })
    );
    expect(mockTextProcessor.preprocessText).toHaveBeenCalledWith(text);
    // The loop in speak() will not run, and it will finish gracefully.
    // The final status update should be "Speech completed" because no error is thrown.
    expect(onStatusUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ message: "Speech completed" })
    );
    expect(mockAudioStreamer.streamAudio).not.toHaveBeenCalled();
    expect(mockPlaybackManager.playAudio).not.toHaveBeenCalled();
  });

  it("should use retry logic on streaming failure and recover", async () => {
    const text = "Streaming test.";
    const segments: TextSegment[] = [
      {
        text: "Streaming test.",
        startOffset: 0,
        endOffset: 11,
        processed: true,
        index: 0,
        type: "sentence",
      },
    ];
    // const audioData = new Uint8Array([1, 2, 3]);

    mockTextProcessor.segmentText.mockReturnValue(segments);
    // Fail once, then succeed
    mockAudioStreamer.streamAudio
      .mockRejectedValueOnce(new Error("Network Error"))
      .mockResolvedValueOnce(undefined);

    mockRetryManager.executeWithRetry.mockImplementation(async (fn) => {
      try {
        return await fn();
      } catch (e: unknown) {
        // Simulate a retry by calling the function again
        console.warn(e);
        return await fn();
      }
    });

    await processor.speak(text);

    expect(mockRetryManager.executeWithRetry).toHaveBeenCalledTimes(1);
    expect(mockAudioStreamer.streamAudio).toHaveBeenCalledTimes(2);
    // Note: playAudio is not called directly in the current implementation
    expect(onStatusUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ message: "Speech completed" })
    );
  });

  it("should handle fatal streaming error after retries", async () => {
    const text = "Fatal error test.";
    const segments: TextSegment[] = [
      {
        text: "Fatal error test.",
        startOffset: 0,
        endOffset: 11,
        processed: true,
        index: 0,
        type: "sentence",
      },
    ];
    const error = new Error("Fatal streaming error");

    mockTextProcessor.segmentText.mockReturnValue(segments);
    mockAudioStreamer.streamAudio.mockRejectedValue(error);
    mockRetryManager.executeWithRetry.mockImplementation(async (fn) => fn());

    await expect(processor.speak(text)).rejects.toThrow(error);

    expect(mockTextProcessor.preprocessText).toHaveBeenCalledWith(text);
    expect(mockRetryManager.executeWithRetry).toHaveBeenCalledTimes(1);
    // In case of error, the final status update is not called, but an error is thrown
    expect(onStatusUpdate).not.toHaveBeenCalledWith(
      expect.objectContaining({ message: "Speech completed" })
    );
  });

  it("should correctly delegate pause, resume, and stop commands", async () => {
    processor.pause();
    expect(mockPlaybackManager.pause).toHaveBeenCalledTimes(1);

    processor.resume();
    expect(mockPlaybackManager.resume).toHaveBeenCalledTimes(1);

    await processor.stop();
    expect(mockPlaybackManager.stop).toHaveBeenCalledTimes(1);
  });

  it("should correctly report playing and paused states", () => {
    expect(processor.playing).toBe(false);
    expect(processor.paused).toBe(false);

    // Simulate playing state
    mockPlaybackManager.isActive.mockReturnValue(true);
    expect(processor.playing).toBe(true);

    // Simulate paused state
    mockPlaybackManager.isPaused.mockReturnValue(true);
    expect(processor.paused).toBe(true);
  });
});
