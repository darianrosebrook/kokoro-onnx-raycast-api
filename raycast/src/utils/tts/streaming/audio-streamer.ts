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
 * @since 2025-07-17
 */

import { ChildProcess } from "child_process";
// import { ValidationUtils } from "../../validation/validation.js";
import { cacheManager } from "../../core/cache.js";
import { AdaptiveBufferManager } from "./adaptive-buffer-manager.js";
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
} from "../../validation/tts-types.js";
import { TTS_CONSTANTS } from "../../validation/tts-types.js";
import { logger } from "../../core/logger.js";

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
  private instanceID: string;
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
  private adaptiveBufferManager: AdaptiveBufferManager;
  private stats: StreamingStats = {
    chunksReceived: 0,
    bytesReceived: 0,
    averageChunkSize: 0,
    streamingDuration: 0,
    efficiency: 0,
    underruns: 0,
    bufferHealth: 1.0,
    totalAudioDuration: 0, // Add missing property for Phase 1 optimization
  };

  constructor(config: Partial<TTSProcessorConfig> = {}) {
    this.instanceID = `AudioStreamer_${Math.random().toString(36).substring(7)}`;
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
      targetBufferMs: TTS_CONSTANTS.TARGET_BUFFER_MS,
      bufferSize: TTS_CONSTANTS.DEFAULT_BUFFER_SIZE,
      chunkSize: 2400,
      deliveryRate: 40,
      minBufferChunks: 4,
      maxLatency: 100,
      targetUtilization: 0.7,
      minBufferMs: TTS_CONSTANTS.MIN_BUFFER_MS,
      maxBufferMs: TTS_CONSTANTS.MAX_BUFFER_MS,
    };

    // Initialize adaptive buffer manager with buffer config
    this.adaptiveBufferManager = new AdaptiveBufferManager({
      targetBufferMs: TTS_CONSTANTS.TARGET_BUFFER_MS,
      bufferSize: TTS_CONSTANTS.DEFAULT_BUFFER_SIZE,
      chunkSize: 2400,
      deliveryRate: 40,
      minBufferChunks: 4,
      maxLatency: 100,
      targetUtilization: 0.7,
      minBufferMs: TTS_CONSTANTS.MIN_BUFFER_MS,
      maxBufferMs: TTS_CONSTANTS.MAX_BUFFER_MS,
    });
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

    // Initialize adaptive buffer manager with buffer config
    await this.adaptiveBufferManager.initialize({
      targetBufferMs: TTS_CONSTANTS.TARGET_BUFFER_MS,
      bufferSize: TTS_CONSTANTS.DEFAULT_BUFFER_SIZE,
      chunkSize: 2400,
      deliveryRate: 40,
      minBufferChunks: 4,
      maxLatency: 100,
      targetUtilization: 0.7,
      minBufferMs: TTS_CONSTANTS.MIN_BUFFER_MS,
      maxBufferMs: TTS_CONSTANTS.MAX_BUFFER_MS,
    });

    this.initialized = true;

    console.log("Audio streamer initialized", {
      component: this.name,
      method: "initialize",
      config: this.config,
      audioFormat: this.audioFormat,
      bufferConfig: this.bufferConfig,
      instanceID: this.instanceID,
    });
  }

  /**
   * Clean up resources
   */
  async cleanup(): Promise<void> {
    await this.stopCurrentPlayback();
    // this.currentSession = null;
    this.initialized = false;

    console.warn("Audio streamer cleaned up", {
      component: this.name,
      method: "cleanup",
      instanceID: this.instanceID,
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
    console.log(`[${this.instanceID}] streamAudio() called with request:`, request);
    try {
      // Check cache first
      const cachedAudio = this.checkCache(request);
      if (cachedAudio) {
        console.log(`[${this.instanceID}] Using cached audio data`);
        // Return cached data as a single chunk
        onChunk({
          data: new Uint8Array(cachedAudio),
          index: 0,
          timestamp: Date.now(),
        });
        return;
      }

      // If not in cache, stream from server
      await this.streamFromServerWithImmediatePlayback(request, context, (chunk) => {
        // console.log(
        //   `[${this.instanceID}] onChunk callback invoked with chunk:`,
        //   "too verbose for debugging"
        // );
        onChunk(chunk);
      });
      console.log(`[${this.instanceID}] streamFromServerWithImmediatePlayback completed`);
    } catch (err) {
      console.error(`[${this.instanceID}] Error in streamAudio:`, err);
      throw err;
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
   * PHASE 1 OPTIMIZATION: Stream from server with immediate playback
   * This implements the critical streaming fix to eliminate 17s latency
   */
  private async streamFromServerWithImmediatePlayback(
    request: TTSRequestParams,
    context: StreamingContext,
    onChunk: (chunk: AudioChunk) => void
  ): Promise<void> {
    console.log(`[${this.instanceID}] streamFromServerWithImmediatePlayback() called`);
    console.log(` [${this.instanceID}] === SERVER STREAMING START ===`);
    console.log(` [${this.instanceID}]  DEBUGGING: Starting streamFromServerWithImmediatePlayback`);

    // PHASE 1 OPTIMIZATION: Use PCM format for streaming to avoid WAV header + raw audio mixing
    const streamingRequest = {
      ...request,
      stream: true,
      format: "pcm", // Use PCM for streaming, WAV for caching
    };

    console.log(` [${this.instanceID}]  Preparing server request:`, {
      url: `${this.config.serverUrl}/v1/audio/speech`,
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "audio/pcm",
      },
      body: {
        ...streamingRequest,
        text:
          streamingRequest.text.substring(0, 100) +
          (streamingRequest.text.length > 100 ? "..." : ""),
      },
    });

    console.log(
      ` [${this.instanceID}]  DEBUGGING: Request:`,
      JSON.stringify(streamingRequest, null, 2)
    );

    const url = `${this.config.serverUrl}/v1/audio/speech`;
    const requestStartTime = performance.now();

    console.log(` [${this.instanceID}]  Sending request to server...`);
    console.log(` [${this.instanceID}]  Request start time:`, requestStartTime);

    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "audio/pcm" },
      body: JSON.stringify(streamingRequest),
      signal: context.abortController.signal,
    });

    const responseTime = performance.now() - requestStartTime;
    console.log(` [${this.instanceID}]  Server response received:`, {
      responseTime: responseTime.toFixed(2) + "ms",
      status: response.status,
      statusText: response.statusText,
      ok: response.ok,
    });

    console.log(` [${this.instanceID}]  DEBUGGING: Response status:`, response.status);
    if (response.headers) {
      const headers = [...response.headers.entries()];
      console.log(` [${this.instanceID}]  DEBUGGING: Response headers:`, headers);
      console.log(` [${this.instanceID}]  Response headers:`, Object.fromEntries(headers));
    } else {
      console.log(` [${this.instanceID}]  DEBUGGING: Response headers: undefined`);
    }

    if (!response || !response.ok) {
      const status = response?.status || 500;
      const statusText = response?.statusText || "Unknown error";
      console.error(` [${this.instanceID}]  DEBUGGING: Response failed:`, status, statusText);
      console.error(` [${this.instanceID}]  Server request failed:`, {
        status,
        statusText,
        url,
        requestTime: responseTime.toFixed(2) + "ms",
      });
      throw new Error(`TTS request failed: ${status} ${statusText}`);
    }

    if (!response.body) {
      console.error(` [${this.instanceID}]  DEBUGGING: No response body - streaming not supported`);
      console.error(` [${this.instanceID}]  No response body available`);
      throw new Error("Streaming not supported by this environment");
    }

    console.log(` [${this.instanceID}] ✅ Server response valid, starting chunk processing`);

    const reader = response.body.getReader();
    const chunks: Uint8Array[] = [];
    let chunkIndex = 0;
    let firstChunk = true;
    const startTime = Date.now();
    let totalBytesReceived = 0;

    console.log(` [${this.instanceID}]  DEBUGGING: Starting to read PCM chunks...`);
    console.log(` [${this.instanceID}]  Starting chunk processing...`);
    console.log(` [${this.instanceID}]  Chunk processing start time:`, startTime);

    // PHASE 1 OPTIMIZATION: Stream PCM data directly to afplay
    while (true) {
      const readStartTime = performance.now();
      const { done, value } = await reader.read();
      const _readTime = performance.now() - readStartTime;

      if (done) {
        console.log(` [${this.instanceID}]  DEBUGGING: Stream reading completed`);
        console.log(` [${this.instanceID}] ✅ Stream reading completed`);
        break;
      }

      if (value) {
        chunkIndex++;
        totalBytesReceived += value.length;
        const _elapsedTime = Date.now() - startTime;

        // console.log(` [${this.instanceID}]  Received chunk:`, {
        //   chunkIndex,
        //   size: value.length,
        //   totalBytes: totalBytesReceived,
        //   elapsedTime: elapsedTime + "ms",
        //   readTime: readTime.toFixed(2) + "ms",
        // });

        // console.log(
        //   ` [${this.instanceID}]  DEBUGGING: Received PCM chunk ${chunkIndex}: ${value.length} bytes`
        // );

        // Debug first chunk specifically
        if (firstChunk) {
          console.log(` [${this.instanceID}]  DEBUGGING: First PCM chunk details:`);
          console.log(` [${this.instanceID}]    Size:`, value.length);
          console.log(
            ` [${this.instanceID}]    First 8 bytes:`,
            Array.from(value.slice(0, 8))
              .map((b) => `0x${b.toString(16).padStart(2, "0")}`)
              .join(" ")
          );

          // Check if this is actually PCM data (should NOT have RIFF header)
          const hasRiff =
            value.length >= 4 &&
            value[0] === 0x52 &&
            value[1] === 0x49 &&
            value[2] === 0x46 &&
            value[3] === 0x46;
          console.log(` [${this.instanceID}]    Has RIFF header (should be false):`, hasRiff);
          console.log(` [${this.instanceID}]  First chunk analysis:`, {
            size: value.length,
            hasRiffHeader: hasRiff,
            firstBytes: Array.from(value.slice(0, 8))
              .map((b) => `0x${b.toString(16).padStart(2, "0")}`)
              .join(" "),
          });
        }

        chunks.push(value);

        // PHASE 1 OPTIMIZATION: Send PCM chunks directly to afplay
        const currentTime = Date.now();
        const elapsedTimeMs = currentTime - startTime;
        const chunkDuration = this.calculateChunkDuration(value.length);

        // console.log(` [${this.instanceID}]  Sending chunk to processor:`, {
        //   chunkIndex,
        //   size: value.length,
        //   duration: chunkDuration.toFixed(2) + "ms",
        //   elapsedTime: elapsedTimeMs + "ms",
        // });

        // Send PCM chunk directly
        onChunk({
          data: value,
          index: chunkIndex - 1, // Convert to 0-based index
          timestamp: currentTime,
          duration: chunkDuration,
        });

        // Log TTFA for first chunk
        if (firstChunk) {
          console.log(` [${this.instanceID}]  Time to First Audio (TTFA):`, elapsedTimeMs + "ms");
          console.log("PHASE 1 OPTIMIZATION: First PCM chunk sent to afplay", {
            component: this.name,
            method: "streamFromServerWithImmediatePlayback",
            requestId: context.requestId,
            ttfa: `${elapsedTimeMs}ms`,
            chunkSize: value.length,
            targetTTFA: "800ms",
          });
          firstChunk = false;
        }

        // Log progress every 5th chunk
        if (chunkIndex % 5 === 0) {
          const avgChunkSize = totalBytesReceived / chunkIndex;
          const avgChunkTime = elapsedTimeMs / chunkIndex;

          console.log(` [${this.instanceID}]  Progress report:`, {
            chunkIndex,
            avgChunkSize: avgChunkSize.toFixed(0) + " bytes",
            avgChunkTime: avgChunkTime.toFixed(2) + "ms",
            totalBytes: totalBytesReceived,
            elapsedTime: elapsedTimeMs + "ms",
          });

          console.warn("PCM chunk progress", {
            component: this.name,
            method: "streamFromServerWithImmediatePlayback",
            requestId: context.requestId,
            chunkIndex,
            chunkSize: value.length,
            elapsedTime: `${elapsedTimeMs}ms`,
          });
        }
      }
    }

    const processingEndTime = Date.now();
    const totalProcessingTime = processingEndTime - startTime;

    console.log(` [${this.instanceID}]  All chunks received:`, {
      totalChunks: chunkIndex,
      totalBytes: totalBytesReceived,
      totalTime: totalProcessingTime + "ms",
      avgChunkSize:
        chunkIndex > 0 ? (totalBytesReceived / chunkIndex).toFixed(0) + " bytes" : "N/A",
      avgChunkTime: chunkIndex > 0 ? (totalProcessingTime / chunkIndex).toFixed(2) + "ms" : "N/A",
    });

    // PHASE 1 OPTIMIZATION: Create WAV file for caching (but not for streaming)
    console.log(` [${this.instanceID}]  Creating WAV file for caching...`);
    const wavCreationStart = performance.now();
    const combinedAudio = this.createWAVFromPCMChunks(chunks);
    const wavCreationTime = performance.now() - wavCreationStart;

    console.log(` [${this.instanceID}]  WAV file created:`, {
      pcmChunks: chunks.length,
      pcmBytes: totalBytesReceived,
      wavBytes: combinedAudio.length,
      creationTime: wavCreationTime.toFixed(2) + "ms",
    });

    // Cache the complete WAV audio for future requests
    if (combinedAudio.length > 0) {
      console.log(` [${this.instanceID}]  Caching WAV audio for future requests`);
      cacheManager.cacheTTSResponse(request, combinedAudio.buffer);
    } else {
      console.warn(` [${this.instanceID}] ⚠️ No audio data to cache`);
    }

    // Update streaming stats
    this.stats.chunksReceived = chunkIndex;
    this.stats.bytesReceived = combinedAudio.length;
    this.stats.averageChunkSize = combinedAudio.length / chunkIndex;
    this.stats.streamingDuration = totalProcessingTime;
    this.stats.efficiency = this.calculateStreamingEfficiency(this.stats.streamingDuration);

    console.log(` [${this.instanceID}]  Final streaming statistics:`, {
      chunksReceived: this.stats.chunksReceived,
      bytesReceived: this.stats.bytesReceived,
      averageChunkSize: this.stats.averageChunkSize.toFixed(0) + " bytes",
      streamingDuration: this.stats.streamingDuration + "ms",
      efficiency: (this.stats.efficiency * 100).toFixed(1) + "%",
    });

    console.log("PHASE 1 OPTIMIZATION: PCM streaming completed", {
      component: this.name,
      method: "streamFromServerWithImmediatePlayback",
      requestId: context.requestId,
      totalChunks: chunkIndex,
      totalSize: combinedAudio.length,
      streamingDuration: `${this.stats.streamingDuration}ms`,
      efficiency: `${(this.stats.efficiency * 100).toFixed(1)}%`,
    });

    console.log(` [${this.instanceID}] === SERVER STREAMING END ===`);
    console.log(`[${this.instanceID}] streamFromServerWithImmediatePlayback() finished`);
  }

  /**
   * Calculate chunk duration for streaming optimization
   */
  private calculateChunkDuration(chunkSize: number): number {
    // Convert bytes to duration based on audio format
    const bytesPerSecond =
      this.audioFormat.sampleRate * this.audioFormat.channels * this.audioFormat.bytesPerSample;
    return (chunkSize / bytesPerSecond) * 1000; // Duration in milliseconds
  }

  /**
   * Calculate streaming efficiency for Phase 1 optimization
   */
  private calculateStreamingEfficiency(streamingDuration: number): number {
    // Calculate expected time for real-time streaming
    const expectedTime = this.stats.totalAudioDuration || streamingDuration;
    return Math.min(1.0, expectedTime / streamingDuration);
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
    console.log(` [${this.instanceID}]  First chunk size: ${firstChunk.length} bytes`);
    console.log(
      ` [${this.instanceID}]  First chunk first 4 bytes: ${Array.from(firstChunk.slice(0, 4))
        .map((b) => "0x" + b.toString(16).padStart(2, "0"))
        .join(" ")}`
    );
    console.log(
      ` [${this.instanceID}]  First chunk first 8 bytes as string: "${firstChunk.slice(0, 8).toString()}"`
    );

    // Verify first chunk has WAV header
    const hasWavHeader =
      firstChunk.length >= 4 &&
      firstChunk[0] === 0x52 && // 'R'
      firstChunk[1] === 0x49 && // 'I'
      firstChunk[2] === 0x46 && // 'F'
      firstChunk[3] === 0x46; // 'F'

    console.log(` [${this.instanceID}]  WAV header detected: ${hasWavHeader}`);

    if (!hasWavHeader) {
      console.warn("First chunk missing WAV header, using simple concatenation", {
        component: this.name,
        method: "combineAudioChunks",
      });
      console.log(` [${this.instanceID}]  Using simple concatenation due to missing WAV header`);
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
      ` [${this.instanceID}]  Updated header first 12 bytes: ${Array.from(
        updatedHeader.slice(0, 12)
      )
        .map((b) => "0x" + b.toString(16).padStart(2, "0"))
        .join(" ")}`
    );
    console.log(
      ` [${this.instanceID}]  Updated header as string: "${updatedHeader.slice(0, 12).toString()}"`
    );

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

    console.warn("Combined audio chunks", {
      component: this.name,
      method: "combineAudioChunks",
      chunkCount: chunks.length,
      totalSize: combinedAudio.length,
      audioDuration: (totalAudioSize / this.audioFormat.bytesPerSecond).toFixed(2) + "s",
    });

    return combinedAudio;
  }

  /**
   * Create a proper WAV file from PCM chunks for caching
   */
  private createWAVFromPCMChunks(chunks: Uint8Array[]): Uint8Array {
    if (chunks.length === 0) return new Uint8Array(0);

    // Combine all PCM chunks
    const totalPCMSize = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
    const combinedPCM = new Uint8Array(totalPCMSize);
    let offset = 0;

    for (const chunk of chunks) {
      combinedPCM.set(chunk, offset);
      offset += chunk.length;
    }

    // Create WAV header for the combined PCM data
    const WAV_HEADER_SIZE = 44;
    const wavFile = new Uint8Array(WAV_HEADER_SIZE + totalPCMSize);

    // RIFF header
    const header = new DataView(wavFile.buffer);
    header.setUint32(0, 0x46464952, true); // "RIFF"
    header.setUint32(4, WAV_HEADER_SIZE + totalPCMSize - 8, true); // File size - 8
    header.setUint32(8, 0x45564157, true); // "WAVE"

    // Format chunk
    header.setUint32(12, 0x20746d66, true); // "fmt "
    header.setUint32(16, 16, true); // Format chunk size
    header.setUint16(20, 1, true); // PCM format
    header.setUint16(22, this.audioFormat.channels, true); // Channels
    header.setUint32(24, this.audioFormat.sampleRate, true); // Sample rate
    header.setUint32(
      28,
      this.audioFormat.sampleRate * this.audioFormat.channels * this.audioFormat.bytesPerSample,
      true
    ); // Byte rate
    header.setUint16(32, this.audioFormat.channels * this.audioFormat.bytesPerSample, true); // Block align
    header.setUint16(34, this.audioFormat.bitDepth, true); // Bits per sample

    // Data chunk
    header.setUint32(36, 0x61746164, true); // "data"
    header.setUint32(40, totalPCMSize, true); // Data size

    // Copy PCM data
    wavFile.set(combinedPCM, WAV_HEADER_SIZE);

    console.warn("Created WAV file from PCM chunks", {
      component: this.name,
      method: "createWAVFromPCMChunks",
      pcmChunks: chunks.length,
      pcmSize: totalPCMSize,
      wavSize: wavFile.length,
      audioDuration: (totalPCMSize / this.audioFormat.bytesPerSecond).toFixed(2) + "s",
    });

    return wavFile;
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
   * Adjust buffer based on performance metrics using adaptive buffer manager
   */
  adjustBuffer(metrics: PerformanceMetrics): number {
    if (!this.config.adaptiveBuffering) {
      return this.bufferConfig.targetBufferMs;
    }

    // Use adaptive buffer manager to get optimal settings
    const optimalConfig = this.adaptiveBufferManager.getOptimalConfig(metrics);

    if (optimalConfig) {
      const oldBufferSize = this.bufferConfig.targetBufferMs;
      const newBufferSize = optimalConfig.targetBufferMs;

      if (newBufferSize !== oldBufferSize) {
        this.bufferConfig = { ...this.bufferConfig, ...optimalConfig };

        console.log("Buffer adjusted using adaptive manager", {
          component: this.name,
          method: "adjustBuffer",
          oldBufferSize,
          newBufferSize,
          optimalConfig,
        });
      }

      return newBufferSize;
    }

    // Fallback to manual adjustment if adaptive manager doesn't have optimal config
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

      console.log("Buffer adjusted using fallback method", {
        component: this.name,
        method: "adjustBuffer",
        oldBufferSize,
        newBufferSize,
        reason: "fallback-adjustment",
      });
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

    console.log("Buffer configuration updated", {
      component: this.name,
      method: "updateBufferConfig",
      config: this.bufferConfig,
    });
  }
}
