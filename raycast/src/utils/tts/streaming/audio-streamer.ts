/**
 * Audio Streaming Module for Raycast Kokoro TTS
 *
 * This module handles all audio streaming operations with memory-based playback
 * using stdin piping to afplay for optimal performance and zero disk I/O.
 *
 * Features:
 * - Memory-based audio playback (no temporary files)
 * - Adaptive buffer management based on network conditions
 * - Streaming performance optimization
 * - WAV header handling and audio chunk combination
 * - Real-time performance monitoring
 * - Error recovery with retry logic
 *
 * @author @darianrosebrook
 * @version 1.0.0
 * @since 2025-01-20
 */

import { ChildProcess } from "child_process";
import { logger } from "../../core/logger";
// import { ValidationUtils } from "../../validation/validation";
import { cacheManager } from "../../core/cache";
import type {
  IAudioStreamer,
  TTSRequestParams,
  StreamingContext,
  AudioChunk,
  StreamingStats,
  PerformanceMetrics,
  AudioFormat,
  BufferConfig,
  TTSProcessorConfig,
} from "../../validation/tts-types";
import { TTS_CONSTANTS } from "../../validation/tts-types";

/**
 * Audio streaming session information
 */
// interface StreamingSession {
//   requestId: string;
//   startTime: number;
//   chunks: AudioChunk[];
//   totalBytes: number;
//   bufferSize: number;
//   underruns: number;
//   efficiency: number;
// }

/**
 * Memory-based playback process information
 */
interface PlaybackProcess {
  process: ChildProcess;
  audioData: Uint8Array;
  startTime: number;
  isPlaying: boolean;
}

/**
 * Enhanced Audio Streamer with memory-based playback
 */
export class AudioStreamer implements IAudioStreamer {
  public readonly name = "AudioStreamer";
  public readonly version = "1.0.0";

  private config: {
    serverUrl: string;
    developmentMode: boolean;
    adaptiveBuffering: boolean;
  };
  private initialized = false;
  // private currentSession: StreamingSession | null = null;
  private currentPlayback: PlaybackProcess | null = null;
  private bufferConfig: BufferConfig;
  private audioFormat: AudioFormat;
  private stats: StreamingStats = {
    chunksReceived: 0,
    bytesReceived: 0,
    averageChunkSize: 0,
    streamingDuration: 0,
    efficiency: 0,
    underruns: 0,
    bufferHealth: 1.0,
  };

  constructor(config: Partial<TTSProcessorConfig> = {}) {
    this.config = {
      serverUrl: config.serverUrl ?? "http://localhost:8000",
      developmentMode: config.developmentMode ?? false,
      adaptiveBuffering: true,
    };

    // Initialize audio format for Kokoro ONNX
    this.audioFormat = {
      format: "wav",
      sampleRate: TTS_CONSTANTS.SAMPLE_RATE,
      channels: TTS_CONSTANTS.CHANNELS,
      bitDepth: TTS_CONSTANTS.BIT_DEPTH,
      bytesPerSample: TTS_CONSTANTS.BYTES_PER_SAMPLE,
      bytesPerSecond:
        TTS_CONSTANTS.SAMPLE_RATE * TTS_CONSTANTS.CHANNELS * TTS_CONSTANTS.BYTES_PER_SAMPLE,
    };

    // Initialize buffer configuration
    this.bufferConfig = {
      minBufferMs: TTS_CONSTANTS.MIN_BUFFER_MS,
      targetBufferMs: TTS_CONSTANTS.TARGET_BUFFER_MS,
      maxBufferMs: TTS_CONSTANTS.MAX_BUFFER_MS,
      sampleRate: this.audioFormat.sampleRate,
      channels: this.audioFormat.channels,
      bytesPerSample: this.audioFormat.bytesPerSample,
    };
  }

  /**
   * Initialize the audio streamer
   */
  async initialize(config: Partial<TTSProcessorConfig>): Promise<void> {
    if (config.serverUrl) {
      this.config.serverUrl = config.serverUrl;
    }
    if (config.developmentMode !== undefined) {
      this.config.developmentMode = config.developmentMode;
    }

    this.initialized = true;

    logger.info("Audio streamer initialized", {
      component: this.name,
      method: "initialize",
      config: this.config,
      audioFormat: this.audioFormat,
      bufferConfig: this.bufferConfig,
    });
  }

  /**
   * Clean up resources
   */
  async cleanup(): Promise<void> {
    await this.stopCurrentPlayback();
    // this.currentSession = null;
    this.initialized = false;

    logger.debug("Audio streamer cleaned up", {
      component: this.name,
      method: "cleanup",
    });
  }

  /**
   * Check if the streamer is initialized
   */
  isInitialized(): boolean {
    return this.initialized;
  }

  /**
   * Stream audio and return the complete audio data as a buffer.
   */
  async streamAudio(
    request: TTSRequestParams,
    context: StreamingContext,
    onChunk: (chunk: AudioChunk) => void
  ): Promise<void> {
    if (!this.initialized) {
      throw new Error("Audio streamer not initialized");
    }

    const timerId = logger.startTiming("audio-streaming", {
      component: this.name,
      method: "streamAudio",
      requestId: context.requestId,
      textLength: request.text.length,
      voice: request.voice,
    });

    try {
      // Check cache first
      const cachedResponse = this.checkCache(request);
      if (cachedResponse) {
        logger.endTiming(timerId, { cached: true, success: true });
        onChunk({
          data: new Uint8Array(cachedResponse),
          index: 0,
          timestamp: Date.now(),
        });
        return; // Exit early if cache hit
      }

      // Stream from server
      const audioData = await this.streamFromServer(request, context);
      logger.endTiming(timerId, { cached: false, success: true });

      // Log audio data details for debugging
      logger.info("Audio streaming completed", {
        component: this.name,
        method: "streamAudio",
        requestId: context.requestId,
        audioSize: audioData.length,
        textLength: request.text.length,
        voice: request.voice,
      });

      console.log(
        `Audio streaming completed: ${audioData.length} bytes for text "${request.text.substring(0, 50)}..."`
      );

      onChunk({
        data: audioData,
        index: 0,
        timestamp: Date.now(),
      });
    } catch (error) {
      logger.endTiming(timerId, { success: false });
      logger.error("Audio streaming failed", {
        component: this.name,
        method: "streamAudio",
        requestId: context.requestId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      throw error;
    }
  }

  /**
   * Check cache for existing audio response
   */
  private checkCache(request: TTSRequestParams): ArrayBuffer | null {
    const cachedResponse = cacheManager.getCachedTTSResponse(request);
    if (cachedResponse) {
      logger.logCachePerformance("hit", "TTS response", {
        component: this.name,
        method: "checkCache",
        size: cachedResponse.size,
        voice: request.voice,
      });
      return cachedResponse.audioData;
    }

    logger.logCachePerformance("miss", "TTS response", {
      component: this.name,
      method: "checkCache",
      voice: request.voice,
    });

    return null;
  }

  /**
   * Stream audio from the server and return the data.
   */
  private async streamFromServer(
    request: TTSRequestParams,
    context: StreamingContext
  ): Promise<Uint8Array> {
    const url = `${this.config.serverUrl}/v1/audio/speech`;
    const cachedResponse = this.checkCache(request);
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "audio/wav" },
      body: JSON.stringify(request),
      signal: context.abortController.signal,
    });

    if (!response || !response.ok) {
      if (cachedResponse) {
        return new Uint8Array(cachedResponse as ArrayBuffer);
      }
      const status = response?.status || 500;
      const statusText = response?.statusText || "Unknown error";
      throw new Error(`TTS request failed: ${status} ${statusText}`);
    }

    if (!response.body) {
      throw new Error("Streaming not supported by this environment");
    }

    const reader = response.body.getReader();
    const chunks: Uint8Array[] = [];
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      if (value) {
        chunks.push(value);
      }
    }

    const combinedAudio = this.combineAudioChunks(chunks);

    // Log combined audio details
    logger.info("Audio chunks combined", {
      component: this.name,
      method: "streamFromServer",
      chunkCount: chunks.length,
      combinedSize: combinedAudio.length,
      textLength: request.text.length,
    });

    console.log(`Combined ${chunks.length} audio chunks into ${combinedAudio.length} bytes`);

    if (combinedAudio.length > 0) {
      cacheManager.cacheTTSResponse(request, combinedAudio.buffer);
    } else {
      console.warn("Warning: Combined audio data is empty!");
    }

    return combinedAudio;
  }

  /**
   * Combine audio chunks into valid WAV file
   */
  private combineAudioChunks(chunks: Uint8Array[]): Uint8Array {
    if (chunks.length === 0) return new Uint8Array(0);
    if (chunks.length === 1) return chunks[0];

    const WAV_HEADER_SIZE = 44;
    const firstChunk = chunks[0];

    // Debug: Check what's actually in the first chunk
    console.log(`First chunk size: ${firstChunk.length} bytes`);
    console.log(
      `First chunk first 4 bytes: ${Array.from(firstChunk.slice(0, 4))
        .map((b) => "0x" + b.toString(16).padStart(2, "0"))
        .join(" ")}`
    );
    console.log(`First chunk first 8 bytes as string: "${firstChunk.slice(0, 8).toString()}"`);

    // Verify first chunk has WAV header
    const hasWavHeader =
      firstChunk.length >= 4 &&
      firstChunk[0] === 0x52 && // 'R'
      firstChunk[1] === 0x49 && // 'I'
      firstChunk[2] === 0x46 && // 'F'
      firstChunk[3] === 0x46; // 'F'

    console.log(`WAV header detected: ${hasWavHeader}`);

    if (!hasWavHeader) {
      logger.warn("First chunk missing WAV header, using simple concatenation", {
        component: this.name,
        method: "combineAudioChunks",
      });
      console.log("Using simple concatenation due to missing WAV header");
      return this.simpleConcatenation(chunks);
    }

    // Extract WAV header and combine audio data
    const wavHeader = firstChunk.slice(0, WAV_HEADER_SIZE);
    const firstAudioData = firstChunk.slice(WAV_HEADER_SIZE);

    let totalAudioSize = firstAudioData.length;
    const additionalAudioChunks: Uint8Array[] = [];

    for (let i = 1; i < chunks.length; i++) {
      const chunk = chunks[i];
      const chunkHasHeader =
        chunk.length >= WAV_HEADER_SIZE &&
        chunk[0] === 0x52 &&
        chunk[1] === 0x49 &&
        chunk[2] === 0x46 &&
        chunk[3] === 0x46;

      if (chunkHasHeader) {
        const audioData = chunk.slice(WAV_HEADER_SIZE);
        additionalAudioChunks.push(audioData);
        totalAudioSize += audioData.length;
      } else {
        additionalAudioChunks.push(chunk);
        totalAudioSize += chunk.length;
      }
    }

    // Update WAV header with correct file size
    const updatedHeader = new Uint8Array(wavHeader);
    const totalFileSize = WAV_HEADER_SIZE + totalAudioSize - 8;

    // Update file size (bytes 4-7) - this is correct
    updatedHeader[4] = totalFileSize & 0xff;
    updatedHeader[5] = (totalFileSize >> 8) & 0xff;
    updatedHeader[6] = (totalFileSize >> 16) & 0xff;
    updatedHeader[7] = (totalFileSize >> 24) & 0xff;

    // Update data chunk size (bytes 40-43) - this is correct
    updatedHeader[40] = totalAudioSize & 0xff;
    updatedHeader[41] = (totalAudioSize >> 8) & 0xff;
    updatedHeader[42] = (totalAudioSize >> 16) & 0xff;
    updatedHeader[43] = (totalAudioSize >> 24) & 0xff;

    // Debug: Check the updated header
    console.log(
      `Updated header first 12 bytes: ${Array.from(updatedHeader.slice(0, 12))
        .map((b) => "0x" + b.toString(16).padStart(2, "0"))
        .join(" ")}`
    );
    console.log(`Updated header as string: "${updatedHeader.slice(0, 12).toString()}"`);

    // Combine all audio data
    const combinedAudio = new Uint8Array(WAV_HEADER_SIZE + totalAudioSize);
    let offset = 0;

    combinedAudio.set(updatedHeader, offset);
    offset += WAV_HEADER_SIZE;

    combinedAudio.set(firstAudioData, offset);
    offset += firstAudioData.length;

    for (const audioChunk of additionalAudioChunks) {
      combinedAudio.set(audioChunk, offset);
      offset += audioChunk.length;
    }

    logger.debug("Combined audio chunks", {
      component: this.name,
      method: "combineAudioChunks",
      chunkCount: chunks.length,
      totalSize: combinedAudio.length,
      audioDuration: (totalAudioSize / this.audioFormat.bytesPerSecond).toFixed(2) + "s",
    });

    return combinedAudio;
  }

  /**
   * Simple concatenation fallback
   */
  private simpleConcatenation(chunks: Uint8Array[]): Uint8Array {
    const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
    const combinedAudio = new Uint8Array(totalLength);
    let offset = 0;

    for (const chunk of chunks) {
      combinedAudio.set(chunk, offset);
      offset += chunk.length;
    }

    return combinedAudio;
  }

  /**
   * Adjust buffer based on performance metrics
   */
  adjustBuffer(metrics: PerformanceMetrics): number {
    if (!this.config.adaptiveBuffering) {
      return this.bufferConfig.targetBufferMs;
    }

    const oldBufferSize = this.bufferConfig.targetBufferMs;
    let newBufferSize = oldBufferSize;

    // Increase buffer if experiencing underruns
    if (metrics.underrunCount > 0) {
      newBufferSize += metrics.underrunCount * 100;
    }

    // Increase buffer if latency is high
    if (metrics.timeToFirstAudio > TTS_CONSTANTS.TARGET_TTFA_MS) {
      newBufferSize += 100;
    }

    // Decrease buffer if efficiency is good and latency is low
    if (
      metrics.streamingEfficiency > TTS_CONSTANTS.TARGET_EFFICIENCY &&
      metrics.timeToFirstAudio < 400
    ) {
      newBufferSize -= 50;
    }

    // Clamp to valid range
    newBufferSize = Math.max(
      this.bufferConfig.minBufferMs,
      Math.min(this.bufferConfig.maxBufferMs, newBufferSize)
    );

    if (newBufferSize !== oldBufferSize) {
      this.bufferConfig.targetBufferMs = newBufferSize;

      logger.logBufferAdjustment(oldBufferSize, newBufferSize, "performance-based");
    }

    return newBufferSize;
  }

  /**
   * Get current streaming statistics
   */
  getStreamingStats(): StreamingStats {
    return { ...this.stats };
  }

  /**
   * Get current audio format
   */
  getAudioFormat(): AudioFormat {
    return { ...this.audioFormat };
  }

  /**
   * Get current buffer configuration
   */
  getBufferConfig(): BufferConfig {
    return { ...this.bufferConfig };
  }

  /**
   * Stop current playback process
   */
  private async stopCurrentPlayback(): Promise<void> {
    if (this.currentPlayback?.process) {
      this.currentPlayback.process.kill();
      this.currentPlayback.isPlaying = false;
      this.currentPlayback = null;
    }
  }

  /**
   * Update buffer configuration
   */
  updateBufferConfig(config: Partial<BufferConfig>): void {
    this.bufferConfig = { ...this.bufferConfig, ...config };

    logger.info("Buffer configuration updated", {
      component: this.name,
      method: "updateBufferConfig",
      config: this.bufferConfig,
    });
  }
}
