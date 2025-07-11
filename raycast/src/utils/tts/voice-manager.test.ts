import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  fetchAvailableVoices,
  getValidatedVoice,
  formatVoiceName,
  categorizeVoice,
  generateVoiceOptions,
  clearVoiceCache,
} from "./voice-manager";

// Mock fetch globally
global.fetch = vi.fn();

describe("VoiceManager", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clearVoiceCache();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("fetchAvailableVoices", () => {
    it("should fetch voices from server successfully", async () => {
      const mockVoices = ["af_heart", "af_bella", "am_joe"];
      const mockResponse = { voices: mockVoices };

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response);

      const result = await fetchAvailableVoices("http://localhost:8000");

      expect(fetch).toHaveBeenCalledWith("http://localhost:8000/voices");
      expect(result).toEqual(mockVoices);
    });

    it("should return cached voices if cache is valid", async () => {
      const mockVoices = ["af_heart", "af_bella"];
      const mockResponse = { voices: mockVoices };

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response);

      // First call - should fetch from server
      const result1 = await fetchAvailableVoices("http://localhost:8000");
      expect(result1).toEqual(mockVoices);

      // Second call - should use cache
      const result2 = await fetchAvailableVoices("http://localhost:8000");
      expect(result2).toEqual(mockVoices);

      // Should only call fetch once
      expect(fetch).toHaveBeenCalledTimes(1);
    });

    it("should handle server error gracefully", async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 500,
      } as Response);

      const result = await fetchAvailableVoices("http://localhost:8000");

      expect(result).toEqual([]);
    });

    it("should handle network error gracefully", async () => {
      vi.mocked(fetch).mockRejectedValueOnce(new Error("Network error"));

      const result = await fetchAvailableVoices("http://localhost:8000");

      expect(result).toEqual([]);
    });

    it("should handle missing voices array in response", async () => {
      const mockResponse = {};

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response);

      const result = await fetchAvailableVoices("http://localhost:8000");

      expect(result).toEqual([]);
    });
  });

  describe("getValidatedVoice", () => {
    it("should return requested voice if available", async () => {
      const mockVoices = ["af_heart", "af_bella", "am_joe"];
      const mockResponse = { voices: mockVoices };

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response);

      const result = await getValidatedVoice("af_heart", "http://localhost:8000");

      expect(result).toBe("af_heart");
    });

    it("should return similar voice as fallback", async () => {
      const mockVoices = ["af_bella", "am_joe", "bf_sarah"];
      const mockResponse = { voices: mockVoices };

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response);

      const result = await getValidatedVoice("af_heart", "http://localhost:8000");

      expect(result).toBe("af_bella"); // Similar prefix "af"
    });

    it("should return first available voice if no similar voice found", async () => {
      const mockVoices = ["am_joe", "bf_sarah"];
      const mockResponse = { voices: mockVoices };

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response);

      const result = await getValidatedVoice("af_heart", "http://localhost:8000");

      expect(result).toBe("am_joe"); // First available voice
    });

    it("should return requested voice if no voices available", async () => {
      const mockResponse = { voices: [] };

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response);

      const result = await getValidatedVoice("af_heart", "http://localhost:8000");

      expect(result).toBe("af_heart");
    });

    it("should return requested voice on server error", async () => {
      vi.mocked(fetch).mockRejectedValueOnce(new Error("Server error"));

      const result = await getValidatedVoice("af_heart", "http://localhost:8000");

      expect(result).toBe("af_heart");
    });
  });

  describe("formatVoiceName", () => {
    it("should format voice name correctly", () => {
      expect(formatVoiceName("af_heart")).toBe("Heart (Female)");
      expect(formatVoiceName("am_joe")).toBe("Joe (Male)");
      expect(formatVoiceName("bf_sarah")).toBe("Sarah (Female)");
    });

    it("should handle voices without gender prefix", () => {
      expect(formatVoiceName("voice_test")).toBe("Test ()");
      expect(formatVoiceName("test")).toBe("test");
    });

    it("should capitalize voice names", () => {
      expect(formatVoiceName("af_bella")).toBe("Bella (Female)");
      expect(formatVoiceName("am_mike")).toBe("Mike (Male)");
    });
  });

  describe("categorizeVoice", () => {
    it("should categorize American English voices", () => {
      expect(categorizeVoice("af_heart")).toEqual({
        flag: "🇺🇸",
        category: "American English",
      });
      expect(categorizeVoice("am_joe")).toEqual({
        flag: "🇺🇸",
        category: "American English",
      });
    });

    it("should categorize British English voices", () => {
      expect(categorizeVoice("bf_sarah")).toEqual({
        flag: "🇬🇧",
        category: "British English",
      });
      expect(categorizeVoice("bm_james")).toEqual({
        flag: "🇬🇧",
        category: "British English",
      });
    });

    it("should categorize Chinese voices", () => {
      expect(categorizeVoice("cf_mei")).toEqual({
        flag: "🇨🇳",
        category: "Chinese",
      });
      expect(categorizeVoice("cm_wei")).toEqual({
        flag: "🇨🇳",
        category: "Chinese",
      });
    });

    it("should categorize French voices", () => {
      expect(categorizeVoice("df_marie")).toEqual({
        flag: "🇫🇷",
        category: "French",
      });
      expect(categorizeVoice("dm_pierre")).toEqual({
        flag: "🇫🇷",
        category: "French",
      });
    });

    it("should default to US English for unknown patterns", () => {
      expect(categorizeVoice("unknown_voice")).toEqual({
        flag: "🇺🇸",
        category: "English",
      });
      expect(categorizeVoice("test")).toEqual({
        flag: "🇺🇸",
        category: "English",
      });
    });
  });

  describe("generateVoiceOptions", () => {
    it("should generate voice options with proper formatting", async () => {
      const mockVoices = ["af_heart", "af_bella", "am_joe", "bf_sarah"];
      const mockResponse = { voices: mockVoices };

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response);

      const result = await generateVoiceOptions("http://localhost:8000");

      expect(result).toEqual([
        { value: "af_bella", title: "🇺🇸 Bella (Female)" },
        { value: "af_heart", title: "🇺🇸 Heart (Female)" },
        { value: "am_joe", title: "🇺🇸 Joe (Male)" },
        { value: "bf_sarah", title: "🇬🇧 Sarah (Female)" },
      ]);
    });

    it("should throw error when no voices available", async () => {
      const mockResponse = { voices: [] };

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response);

      await expect(generateVoiceOptions("http://localhost:8000")).rejects.toThrow(
        "No voices available from server"
      );
    });

    it("should handle server error gracefully", async () => {
      vi.mocked(fetch).mockRejectedValueOnce(new Error("Server error"));

      await expect(generateVoiceOptions("http://localhost:8000")).rejects.toThrow(
        "No voices available from server"
      );
    });

    it("should sort voices within categories", async () => {
      const mockVoices = ["af_heart", "af_bella", "am_joe", "am_mike"];
      const mockResponse = { voices: mockVoices };

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response);

      const result = await generateVoiceOptions("http://localhost:8000");

      // Should be sorted alphabetically within American English category
      expect(result[0].value).toBe("af_bella");
      expect(result[1].value).toBe("af_heart");
      expect(result[2].value).toBe("am_joe");
      expect(result[3].value).toBe("am_mike");
    });
  });

  describe("clearVoiceCache", () => {
    it("should clear the voice cache", async () => {
      const mockVoices = ["af_heart", "af_bella"];
      const mockResponse = { voices: mockVoices };

      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        json: async () => mockResponse,
      } as Response);

      // First call - populate cache
      await fetchAvailableVoices("http://localhost:8000");
      expect(fetch).toHaveBeenCalledTimes(1);

      // Second call - should use cache
      await fetchAvailableVoices("http://localhost:8000");
      expect(fetch).toHaveBeenCalledTimes(1);

      // Clear cache
      clearVoiceCache();

      // Third call - should fetch again
      await fetchAvailableVoices("http://localhost:8000");
      expect(fetch).toHaveBeenCalledTimes(2);
    });
  });

  describe("Cache Behavior", () => {
    it("should respect cache duration", async () => {
      vi.useFakeTimers();

      const mockVoices = ["af_heart"];
      const mockResponse = { voices: mockVoices };

      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        json: async () => mockResponse,
      } as Response);

      // First call
      await fetchAvailableVoices("http://localhost:8000");
      expect(fetch).toHaveBeenCalledTimes(1);

      // Second call within cache duration
      await fetchAvailableVoices("http://localhost:8000");
      expect(fetch).toHaveBeenCalledTimes(1);

      // Mock time to expire cache (5 minutes + 1 second)
      vi.advanceTimersByTime(5 * 60 * 1000 + 1000);

      // Third call after cache expiration
      await fetchAvailableVoices("http://localhost:8000");
      expect(fetch).toHaveBeenCalledTimes(2);

      vi.useRealTimers();
    });
  });
});
