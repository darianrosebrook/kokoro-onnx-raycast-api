/**
 * Text Processing Module for Raycast Kokoro TTS
 *
 * This module handles all text preprocessing, segmentation, and validation
 * operations for TTS synthesis. It provides intelligent text segmentation
 * that maintains natural speech boundaries while respecting server limits.
 *
 * Features:
 * - Multi-level text segmentation (paragraphs, sentences, chunks)
 * - Advanced text preprocessing for natural speech
 * - Configurable preprocessing pipeline
 * - Text validation with detailed error reporting
 * - Performance-optimized algorithms
 *
 * @author @darianrosebrook
 * @version 1.0.0
 * @since 2025-01-20
 */

import { logger } from "../core/logger";
// import { ValidationUtils } from "../validation/validation";
import type {
  ITextProcessor,
  TextSegment,
  TextProcessingConfig,
  TTSProcessorConfig,
} from "../validation/tts-types";
import { TTS_CONSTANTS } from "../validation/tts-types";

/**
 * Text preprocessing pipeline processor
 */
interface TextPreprocessor {
  name: string;
  process(text: string): string;
  enabled: boolean;
  priority: number;
}

/**
 * Text segmentation statistics
 */
interface SegmentationStats {
  originalLength: number;
  segmentCount: number;
  averageSegmentLength: number;
  maxSegmentLength: number;
  processingTime: number;
  segmentationStrategy: string;
}

/**
 * Enhanced Text Processor with intelligent segmentation
 */
export class TextProcessor implements ITextProcessor {
  public readonly name = "TextProcessor";
  public readonly version = "1.0.0";

  private config: TextProcessingConfig;
  private preprocessors: TextPreprocessor[] = [];
  private initialized = false;
  private stats: SegmentationStats = {
    originalLength: 0,
    segmentCount: 0,
    averageSegmentLength: 0,
    maxSegmentLength: 0,
    processingTime: 0,
    segmentationStrategy: "none",
  };

  constructor(config: Partial<TextProcessingConfig> = {}) {
    this.config = {
      maxChunkSize: TTS_CONSTANTS.MAX_TEXT_LENGTH,
      preservePunctuation: true,
      enablePreprocessing: true,
      sentencePauses: false,
      maxSentenceLength: 100,
      ...config,
    };

    this.initializePreprocessors();
  }

  /**
   * Initialize the text processor with configuration
   */
  async initialize(config: Partial<TTSProcessorConfig>): Promise<void> {
    if (config.sentencePauses !== undefined) {
      this.config.sentencePauses = config.sentencePauses;
    }
    if (config.maxSentenceLength !== undefined) {
      this.config.maxSentenceLength = config.maxSentenceLength;
    }

    this.initialized = true;

    logger.info("Text processor initialized", {
      component: this.name,
      method: "initialize",
      config: this.config,
    });
  }

  /**
   * Clean up resources
   */
  async cleanup(): Promise<void> {
    this.preprocessors = [];
    this.initialized = false;

    logger.debug("Text processor cleaned up", {
      component: this.name,
      method: "cleanup",
    });
  }

  /**
   * Check if the processor is initialized
   */
  isInitialized(): boolean {
    return this.initialized;
  }

  /**
   * Initialize text preprocessing pipeline
   */
  private initializePreprocessors(): void {
    this.preprocessors = [
      {
        name: "normalize-whitespace",
        process: this.normalizeWhitespace,
        enabled: true,
        priority: 1,
      },
      {
        name: "expand-abbreviations",
        process: this.expandAbbreviations,
        enabled: this.config.enablePreprocessing,
        priority: 2,
      },
      {
        name: "process-numbers",
        process: this.processNumbers,
        enabled: this.config.enablePreprocessing,
        priority: 3,
      },
      {
        name: "handle-urls",
        process: this.handleUrls,
        enabled: this.config.enablePreprocessing,
        priority: 4,
      },
      {
        name: "fix-punctuation",
        process: this.fixPunctuation,
        enabled: this.config.preservePunctuation,
        priority: 5,
      },
    ];

    // Sort by priority
    this.preprocessors.sort((a, b) => a.priority - b.priority);
  }

  /**
   * Preprocess text for TTS compatibility
   */
  preprocessText(text: string): string {
    if (!text?.trim()) {
      return "";
    }

    logger.startTiming("text-preprocessing", {
      component: this.name,
      method: "preprocessText",
      originalLength: text.length,
    });

    let processedText = text;

    // Apply preprocessing pipeline
    for (const processor of this.preprocessors) {
      if (processor.enabled) {
        try {
          processedText = processor.process(processedText);

          logger.debug(`Applied preprocessor: ${processor.name}`, {
            component: this.name,
            method: "preprocessText",
            processor: processor.name,
            lengthBefore: text.length,
            lengthAfter: processedText.length,
          });
        } catch (error) {
          logger.warn(`Preprocessor failed: ${processor.name}`, {
            component: this.name,
            method: "preprocessText",
            processor: processor.name,
            error: error instanceof Error ? error.message : "Unknown error",
          });
        }
      }
    }

    // const processingTime = logger.endTiming(timerId, {
    //   processedLength: processedText.length,
    //   preprocessorsApplied: this.preprocessors.filter((p) => p.enabled).length,
    // });

    return processedText;
  }

  /**
   * Segment text into optimal chunks for TTS processing
   */
  segmentText(text: string, maxLength: number = this.config.maxChunkSize): TextSegment[] {
    if (!text?.trim()) {
      return [];
    }

    logger.startTiming("text-segmentation", {
      component: this.name,
      method: "segmentText",
      originalLength: text.length,
      maxLength,
    });

    const segments = this.intelligentSegmentation(text, maxLength);

    // Update statistics
    this.stats = {
      originalLength: text.length,
      segmentCount: segments.length,
      averageSegmentLength:
        segments.reduce((sum, seg) => sum + seg.text.length, 0) / segments.length,
      maxSegmentLength: Math.max(...segments.map((seg) => seg.text.length)),
      processingTime: logger.endTiming("text-segmentation", {
        segmentCount: segments.length,
        averageLength: this.stats.averageSegmentLength,
      }),
      segmentationStrategy: this.determineSegmentationStrategy(text, maxLength),
    };

    logger.info("Text segmentation completed", {
      component: this.name,
      method: "segmentText",
      stats: this.stats,
    });

    return segments;
  }

  /**
   * Validate text for TTS processing
   */
  validateText(text: string): { isValid: boolean; errors: string[] } {
    const errors: string[] = [];

    if (!text || typeof text !== "string") {
      errors.push("Text must be a non-empty string");
      return { isValid: false, errors };
    }

    const trimmedText = text.trim();
    if (trimmedText.length === 0) {
      errors.push("Text cannot be empty after trimming");
      return { isValid: false, errors };
    }

    if (trimmedText.length > this.config.maxChunkSize) {
      errors.push(
        `Text length (${trimmedText.length}) exceeds maximum allowed (${this.config.maxChunkSize})`
      );
    }

    // Check for potentially problematic characters
    const problematicChars = trimmedText.match(/[^\w\s\p{P}\p{S}]/gu);
    if (problematicChars) {
      errors.push(
        `Text contains potentially problematic characters: ${problematicChars.join(", ")}`
      );
    }

    // Check for excessive repetition
    if (this.hasExcessiveRepetition(trimmedText)) {
      errors.push("Text contains excessive repetition that may cause synthesis issues");
    }

    const isValid = errors.length === 0;

    logger.debug("Text validation completed", {
      component: this.name,
      method: "validateText",
      textLength: trimmedText.length,
      isValid,
      errorCount: errors.length,
    });

    return { isValid, errors };
  }

  /**
   * Intelligent text segmentation with multiple strategies
   */
  private intelligentSegmentation(text: string, maxLength: number): TextSegment[] {
    // Strategy 1: Try paragraph-based segmentation
    const paragraphs = this.segmentByParagraphs(text);
    if (paragraphs.every((p) => p.length <= maxLength)) {
      return this.createSegments(paragraphs, "paragraph");
    }

    // Strategy 2: Try sentence-based segmentation
    const sentences = this.segmentBySentences(text);
    if (sentences.every((s) => s.length <= maxLength)) {
      return this.createSegments(sentences, "sentence");
    }

    // Strategy 3: Use chunk-based segmentation with boundary preservation
    const chunks = this.segmentByChunks(text, maxLength);
    return this.createSegments(chunks, "chunk");
  }

  /**
   * Segment text by paragraphs
   */
  private segmentByParagraphs(text: string): string[] {
    return text
      .split(/\n\s*\n/)
      .map((p) => p.trim())
      .filter((p) => p.length > 0);
  }

  /**
   * Segment text by sentences
   */
  private segmentBySentences(text: string): string[] {
    // Enhanced sentence detection with better punctuation handling
    const sentences = text.match(/[^.!?]+[.!?]+["']?|[^.!?]+$/g) || [];
    return sentences.map((s: string) => s.trim()).filter((s: string) => s.length > 0);
  }

  /**
   * Segment text by chunks with boundary preservation
   */
  private segmentByChunks(text: string, maxLength: number): string[] {
    const chunks: string[] = [];
    let currentChunk = "";
    const words = text.split(/\s+/);

    for (const word of words) {
      const testChunk = currentChunk ? `${currentChunk} ${word}` : word;

      if (testChunk.length <= maxLength) {
        currentChunk = testChunk;
      } else {
        if (currentChunk) {
          chunks.push(currentChunk);
          currentChunk = word;
        } else {
          // Single word exceeds limit, force split
          chunks.push(word.substring(0, maxLength));
          currentChunk = word.substring(maxLength);
        }
      }
    }

    if (currentChunk) {
      chunks.push(currentChunk);
    }

    return chunks;
  }

  /**
   * Create text segments with metadata
   */
  private createSegments(
    textArray: string[],
    type: "paragraph" | "sentence" | "chunk"
  ): TextSegment[] {
    let offset = 0;

    return textArray.map((text, index) => {
      const segment: TextSegment = {
        text,
        index,
        startOffset: offset,
        endOffset: offset + text.length,
        type,
        processed: false,
      };

      offset += text.length;
      return segment;
    });
  }

  /**
   * Determine the segmentation strategy used
   */
  private determineSegmentationStrategy(text: string, maxLength: number): string {
    const paragraphs = this.segmentByParagraphs(text);
    if (paragraphs.every((p) => p.length <= maxLength)) {
      return "paragraph";
    }

    const sentences = this.segmentBySentences(text);
    if (sentences.every((s) => s.length <= maxLength)) {
      return "sentence";
    }

    return "chunk";
  }

  /**
   * Check for excessive repetition in text
   */
  private hasExcessiveRepetition(text: string): boolean {
    const words = text.toLowerCase().split(/\s+/);
    const totalWords = words.length;

    // Don't run this check on very short texts
    if (totalWords < 10) {
      return false;
    }

    const wordCounts = new Map<string, number>();

    for (const word of words) {
      wordCounts.set(word, (wordCounts.get(word) || 0) + 1);
    }

    // Check if any word appears more than 20% of the time
    for (const [word, count] of wordCounts) {
      if (word.length > 3 && count / totalWords > 0.2) {
        return true;
      }
    }

    return false;
  }

  /**
   * Normalize whitespace
   */
  private normalizeWhitespace = (text: string): string => {
    return text.replace(/[\r\n\s]+/g, " ").trim();
  };

  /**
   * Expand common abbreviations
   */
  private expandAbbreviations = (text: string): string => {
    const abbreviations = {
      "e.g.": "for example",
      "i.e.": "that is",
      "etc.": "etcetera",
      "vs.": "versus",
      "Mr.": "Mister",
      "Mrs.": "Missus",
      "Dr.": "Doctor",
      "Prof.": "Professor",
      "Inc.": "Incorporated",
      "Ltd.": "Limited",
      "Corp.": "Corporation",
      "Co.": "Company",
    };

    let processed = text;
    for (const [abbr, expansion] of Object.entries(abbreviations)) {
      const regex = new RegExp(`\\b${abbr.replace(/\./g, "\\.")}`, "gi");
      processed = processed.replace(regex, expansion);
    }

    return processed;
  };

  /**
   * Process numbers and units
   */
  private processNumbers = (text: string): string => {
    return (
      text
        // Add space between numbers and units
        .replace(/(\d+)(kg|cm|m|km|lb|oz|ft|in|USD|EUR|GBP|%)/g, "$1 $2")
        // Format dates
        .replace(/(\d{4})-(\d{2})-(\d{2})/g, "$1 $2 $3")
        // Format times
        .replace(/(\d{1,2}):(\d{2})(am|pm)/gi, "$1 $2 $3")
    );
  };

  /**
   * Handle URLs and email addresses
   */
  private handleUrls = (text: string): string => {
    return (
      text
        // Replace URLs with generic text
        .replace(/https?:\/\/[^\s]+/g, "web link")
        .replace(/www\.[^\s]+/g, "web link")
        // Replace email addresses
        .replace(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g, "email address")
    );
  };

  /**
   * Fix punctuation for better speech synthesis
   */
  private fixPunctuation = (text: string): string => {
    return (
      text
        // Ensure spaces after punctuation
        .replace(/([.!?])([A-Z])/g, "$1 $2")
        // Fix multiple punctuation marks
        .replace(/[.]{2,}/g, ".")
        .replace(/[!]{2,}/g, "!")
        .replace(/[?]{2,}/g, "?")
        // Remove excessive commas
        .replace(/,{2,}/g, ",")
    );
  };

  /**
   * Get current segmentation statistics
   */
  getStats(): SegmentationStats {
    return { ...this.stats };
  }

  /**
   * Update configuration
   */
  updateConfig(config: Partial<TextProcessingConfig>): void {
    this.config = { ...this.config, ...config };
    this.initializePreprocessors();

    logger.info("Text processor configuration updated", {
      component: this.name,
      method: "updateConfig",
      config: this.config,
    });
  }

  /**
   * Enable or disable specific preprocessors
   */
  configurePreprocessor(name: string, enabled: boolean): void {
    const processor = this.preprocessors.find((p) => p.name === name);
    if (processor) {
      processor.enabled = enabled;

      logger.debug(`Preprocessor ${name} ${enabled ? "enabled" : "disabled"}`, {
        component: this.name,
        method: "configurePreprocessor",
        processor: name,
        enabled,
      });
    }
  }

  /**
   * Get list of available preprocessors
   */
  getPreprocessors(): Array<{ name: string; enabled: boolean; priority: number }> {
    return this.preprocessors.map((p) => ({
      name: p.name,
      enabled: p.enabled,
      priority: p.priority,
    }));
  }
}
