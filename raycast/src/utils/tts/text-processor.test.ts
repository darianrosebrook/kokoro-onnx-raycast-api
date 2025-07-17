import { describe, it, expect, vi, beforeEach } from "vitest";
import { TextProcessor } from "./text-processor.js";
// import { TTSLogger } from "../core/logger.js";
// import { ValidationUtils } from "../validation/validation.js";
import type { TextProcessingConfig } from "../validation/tts-types.js";

// Mock logger to prevent console output and allow for spying
vi.mock("../core/logger", () => {
  const mockLogger = {
    info: vi.fn(),
    warn: vi.fn(),
    debug: vi.fn(),
    error: vi.fn(),
    startTiming: vi.fn(() => "timer-123"),
    endTiming: vi.fn(() => 10),
  };
  // Mock the default export and the named export `logger`
  return {
    TTSLogger: vi.fn(() => mockLogger),
    logger: mockLogger,
  };
});

// Mock validation utils
vi.mock("../validation/validation", () => ({
  ValidationUtils: {
    isTextValid: vi.fn(() => ({ isValid: true, errors: [] })),
  },
}));

describe("TextProcessor", () => {
  let textProcessor: TextProcessor;

  beforeEach(() => {
    vi.clearAllMocks();
    textProcessor = new TextProcessor();
  });

  describe("Constructor and Initialization", () => {
    it("should construct with default configuration", () => {
      expect(textProcessor).toBeInstanceOf(TextProcessor);
      // We can inspect the private config if we want, but it's better to test behavior
    });

    it("should construct with custom configuration", () => {
      const config: Partial<TextProcessingConfig> = {
        maxChunkSize: 500,
        sentencePauses: true,
      };
      const customProcessor = new TextProcessor(config);
      // Again, test behavior rather than implementation details.
      expect(customProcessor).toBeInstanceOf(TextProcessor);
    });

    it("should initialize and update its config", async () => {
      expect(textProcessor.isInitialized()).toBe(false);
      await textProcessor.initialize({ sentencePauses: true, maxSentenceLength: 120 });
      expect(textProcessor.isInitialized()).toBe(true);
      // How to verify config update? We need a getter or test via behavior.
      // Let's add a `getStats` or similar method to the main class if needed.
    });
  });

  describe("Preprocessing", () => {
    it("should return an empty string if input is empty or whitespace", () => {
      expect(textProcessor.preprocessText("")).toBe("");
      expect(textProcessor.preprocessText("   ")).toBe("");
    });

    it("should normalize whitespace", () => {
      const input = "  Hello    world.  This is   a test.  ";
      const expected = "Hello world. This is a test.";
      // Disable other preprocessors to isolate this one
      textProcessor.configurePreprocessor("expand-abbreviations", false);
      textProcessor.configurePreprocessor("process-numbers", false);
      textProcessor.configurePreprocessor("handle-urls", false);
      textProcessor.configurePreprocessor("fix-punctuation", false);

      expect(textProcessor.preprocessText(input)).toBe(expected);
    });

    it("should expand common abbreviations", () => {
      const input = "e.g. i.e. etc.";
      const expected = "for example that is etcetera";
      // We need to enable the abbreviation preprocessor for this test
      textProcessor.configurePreprocessor("expand-abbreviations", true);

      // Disable others to isolate
      textProcessor.configurePreprocessor("normalize-whitespace", false); // Turn off for predictable spacing
      textProcessor.configurePreprocessor("process-numbers", false);
      textProcessor.configurePreprocessor("handle-urls", false);
      textProcessor.configurePreprocessor("fix-punctuation", false);

      expect(textProcessor.preprocessText(input)).toBe(expected);
    });

    it("should handle URLs", () => {
      const input = "Visit https://example.com or www.test.com for more info.";
      const expected = "Visit web link or web link for more info.";
      textProcessor.configurePreprocessor("handle-urls", true);

      // Disable others
      textProcessor.configurePreprocessor("normalize-whitespace", false);
      textProcessor.configurePreprocessor("expand-abbreviations", false);
      textProcessor.configurePreprocessor("process-numbers", false);
      textProcessor.configurePreprocessor("fix-punctuation", false);

      expect(textProcessor.preprocessText(input)).toBe(expected);
    });
  });

  describe("Segmentation", () => {
    it("should return an empty array for empty input", () => {
      expect(textProcessor.segmentText("")).toEqual([]);
    });

    it("should segment text by sentences if paragraphs are too long", () => {
      const input = "First sentence. Second sentence! A third one?";
      // The whole string is 44 chars. By setting maxLength < 44, we force it
      // to move past the paragraph strategy.
      const segments = textProcessor.segmentText(input, 40);
      expect(segments).toHaveLength(3);
      expect(segments[0].text).toBe("First sentence.");
      expect(segments[1].text).toBe("Second sentence!");
      expect(segments[2].text).toBe("A third one?");
    });

    it("should segment text by chunks when sentences are too long", () => {
      const longSentence =
        "This is a very long sentence that will definitely exceed the maximum length and must be chunked.";
      const segments = textProcessor.segmentText(longSentence, 30);
      expect(segments.length).toBeGreaterThan(1);
      expect(segments[0].text).toBe("This is a very long sentence");
      expect(segments[1].text).toBe("that will definitely exceed");
    });

    it("should handle paragraphs correctly", () => {
      const input = "Paragraph one.\n\nParagraph two. It has two sentences.";
      const segments = textProcessor.segmentText(input, 200);
      expect(segments).toHaveLength(2);
      expect(segments[0].text).toBe("Paragraph one.");
      expect(segments[1].text).toBe("Paragraph two. It has two sentences.");
    });
  });

  describe("Validation", () => {
    it("should return valid for correct text", () => {
      const result = textProcessor.validateText("some valid text");
      expect(result.isValid).toBe(true);
      expect(result.errors).toEqual([]);
    });

    it("should return invalid for empty text", () => {
      const result = textProcessor.validateText("   ");
      expect(result.isValid).toBe(false);
      expect(result.errors).toContain("Text cannot be empty after trimming");
    });

    it("should return invalid for text exceeding max length", () => {
      const longText = "a".repeat(3000);
      const result = textProcessor.validateText(longText);
      expect(result.isValid).toBe(false);
      expect(result.errors[0]).toContain("exceeds maximum allowed");
    });
  });
});
