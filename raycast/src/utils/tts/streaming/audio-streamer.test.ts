import { describe, it, expect, vi, beforeEach } from "vitest";
import { AudioStreamer } from "./audio-streamer.js";
import { CachedTTSResponse, cacheManager } from "../../core/cache.js";
import type { TTSRequestParams, StreamingContext } from "../../validation/tts-types.js";
import { Readable } from "stream";

// Mock dependencies
vi.mock("../../core/logger", () => ({
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
    logCachePerformance: vi.fn(),
  },
}));

vi.mock("../../core/cache");

// Mock global fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe("AudioStreamer", () => {
  let audioStreamer: AudioStreamer;
  let request: TTSRequestParams;
  let context: StreamingContext;

  beforeEach(() => {
    vi.clearAllMocks();
    audioStreamer = new AudioStreamer({ serverUrl: "http://test.com" });
    audioStreamer.initialize({});

    request = {
      text: "hello world",
      voice: "af_bella",
      speed: 1,
      lang: "en",
      stream: true,
      format: "wav",
    };

    context = {
      requestId: "req-1",
      segments: ["hello world"],
      currentSegmentIndex: 0,
      totalSegments: 1,
      abortController: new AbortController(),
      startTime: Date.now(),
    };
  });

  it("should construct and initialize without errors", () => {
    expect(audioStreamer).toBeInstanceOf(AudioStreamer);
    expect(audioStreamer.isInitialized()).toBe(true);
  });

  describe("streamAudio - Cache Logic", () => {
    it("should return data from cache if available", async () => {
      const mockAudioData = new ArrayBuffer(8);
      const mockCachedResponse: CachedTTSResponse = {
        audioData: mockAudioData,
        size: 8,
        format: "wav",
        voice: "af_bella",
        speed: 1,
        timestamp: Date.now(),
      };
      vi.mocked(cacheManager.getCachedTTSResponse).mockReturnValue(mockCachedResponse);

      const onChunk = vi.fn();
      const result = await audioStreamer.streamAudio(request, context, onChunk);

      expect(cacheManager.getCachedTTSResponse).toHaveBeenCalledWith(request);
      expect(mockFetch).not.toHaveBeenCalled();
      expect(onChunk).toHaveBeenCalledWith({
        data: new Uint8Array(mockAudioData),
        index: 0,
        timestamp: expect.any(Number),
      });
      expect(result).toBeUndefined();
    });

    it("should fetch from server if not in cache", async () => {
      vi.mocked(cacheManager.getCachedTTSResponse).mockReturnValue(null);

      const mockStream = new Readable();
      mockStream.push(new Uint8Array([1, 2, 3]));
      mockStream.push(null); // End stream

      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        body: Readable.toWeb(mockStream),
      });

      await audioStreamer.streamAudio(request, context, vi.fn());

      expect(mockFetch).toHaveBeenCalledWith("http://test.com/v1/audio/speech", expect.any(Object));
    });
  });

  describe("streamAudio - Error Handling", () => {
    it("should throw if fetch response is not ok", async () => {
      vi.mocked(cacheManager.getCachedTTSResponse).mockReturnValue(null);
      mockFetch.mockResolvedValue({
        ok: false,
        status: 500,
        statusText: "Server Error",
      });

      await expect(audioStreamer.streamAudio(request, context, vi.fn())).rejects.toThrow(
        "TTS request failed: 500 Server Error"
      );
    });

    it("should throw if response body is null", async () => {
      vi.mocked(cacheManager.getCachedTTSResponse).mockReturnValue(null);
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        body: null,
      });

      await expect(audioStreamer.streamAudio(request, context, vi.fn())).rejects.toThrow(
        "Streaming not supported by this environment"
      );
    });
  });
});
