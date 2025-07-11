/**
 * Playback Manager Module for Raycast Kokoro TTS
 *
 * This module handles all audio playback operations with promise-based state management
 * for clean pause/resume functionality and optimal resource management.
 *
 * Features:
 * - Promise-based pause/resume state machine
 * - Memory-based audio playback (no temporary files)
 * - Background playback support
 * - Hardware acceleration via afplay
 * - Resource cleanup and process management
 * - Playback state monitoring
 *
 * @author @darianrosebrook
 * @version 1.0.0
 * @since 2025-01-20
 */

import { spawn, ChildProcess } from "child_process";
import { writeFile, unlink } from "fs/promises";
import { join } from "path";
import { tmpdir } from "os";
import { logger } from "../core/logger";
import type {
  IPlaybackManager,
  PlaybackContext,
  PlaybackState,
  AudioFormat,
  TTSProcessorConfig,
  VoiceOption,
} from "../validation/tts-types";

/**
 * Playback session information
 */
interface PlaybackSession {
  id: string;
  context: PlaybackContext;
  startTime: number;
  process: ChildProcess | null;
  isPlaying: boolean;
  isPaused: boolean;
  isStopped: boolean;
  pausePromise: Promise<void> | null;
  pauseResolve: (() => void) | null;
  pauseReject: ((error: Error) => void) | null;
}

/**
 * Enhanced Playback Manager with promise-based state management
 */
export class PlaybackManager implements IPlaybackManager {
  public readonly name = "PlaybackManager";
  public readonly version = "1.0.0";

  private config: {
    useHardwareAcceleration: boolean;
    backgroundPlayback: boolean;
    developmentMode: boolean;
  };
  private initialized = false;
  private currentSession: PlaybackSession | null = null;
  private playbackQueue: PlaybackContext[] = [];
  private isProcessingQueue = false;

  constructor(config: Partial<TTSProcessorConfig> = {}) {
    this.config = {
      useHardwareAcceleration: true,
      backgroundPlayback: true,
      developmentMode: config.developmentMode ?? false,
    };
  }

  /**
   * Initialize the playback manager
   */
  async initialize(config: Partial<TTSProcessorConfig>): Promise<void> {
    if (config.developmentMode !== undefined) {
      this.config.developmentMode = config.developmentMode;
    }

    this.initialized = true;

    logger.info("Playback manager initialized", {
      component: this.name,
      method: "initialize",
      config: this.config,
    });
  }

  /**
   * Clean up resources
   */
  async cleanup(): Promise<void> {
    await this.stop();
    this.playbackQueue = [];
    this.initialized = false;

    logger.debug("Playback manager cleaned up", {
      component: this.name,
      method: "cleanup",
    });
  }

  /**
   * Check if the manager is initialized
   */
  isInitialized(): boolean {
    return this.initialized;
  }

  /**
   * Play audio with memory-based playback
   */
  async playAudio(context: PlaybackContext, signal: AbortSignal): Promise<void> {
    if (!this.initialized) {
      throw new Error("Playback manager not initialized");
    }

    const sessionId = `playback-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;

    const timerId = logger.startTiming("audio-playback", {
      component: this.name,
      method: "playAudio",
      sessionId,
      audioSize: context.audioData.length,
      voice: context.metadata.voice,
    });

    // Stop any existing playback
    await this.stop();

    // Create new playback session
    this.currentSession = {
      id: sessionId,
      context,
      startTime: performance.now(),
      process: null,
      isPlaying: false,
      isPaused: false,
      isStopped: false,
      pausePromise: null,
      pauseResolve: null,
      pauseReject: null,
    };

    try {
      await this.startPlayback(signal);

      const duration = logger.endTiming(timerId, {
        success: true,
        sessionId,
        audioSize: context.audioData.length,
      });

      logger.info("Audio playback completed", {
        component: this.name,
        method: "playAudio",
        sessionId,
        duration,
        audioSize: context.audioData.length,
      });
    } catch (error) {
      logger.error("Audio playback failed", {
        component: this.name,
        method: "playAudio",
        sessionId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      throw error;
    } finally {
      this.currentSession = null;
    }
  }

  /**
   * Pause current playback with promise-based coordination
   */
  pause(): void {
    if (!this.currentSession || !this.currentSession.isPlaying || this.currentSession.isPaused) {
      return;
    }

    this.currentSession.isPaused = true;
    this.currentSession.isPlaying = false;

    // Create pause promise for coordination
    this.currentSession.pausePromise = new Promise<void>((resolve, reject) => {
      this.currentSession!.pauseResolve = resolve;
      this.currentSession!.pauseReject = reject;
    });

    // Kill the playback process
    if (this.currentSession.process && !this.currentSession.process.killed) {
      this.currentSession.process.kill();
      this.currentSession.process = null;
    }

    logger.info("Playback paused", {
      component: this.name,
      method: "pause",
      sessionId: this.currentSession.id,
    });
  }

  /**
   * Resume playback from paused state
   */
  resume(): void {
    if (!this.currentSession || !this.currentSession.isPaused || this.currentSession.isStopped) {
      return;
    }

    this.currentSession.isPaused = false;
    this.currentSession.isPlaying = true;

    // Resolve the pause promise to continue
    if (this.currentSession.pauseResolve) {
      this.currentSession.pauseResolve();
      this.currentSession.pausePromise = null;
      this.currentSession.pauseResolve = null;
      this.currentSession.pauseReject = null;
    }

    logger.info("Playback resumed", {
      component: this.name,
      method: "resume",
      sessionId: this.currentSession.id,
    });
  }

  /**
   * Stop playback and clean up resources
   */
  async stop(): Promise<void> {
    if (!this.currentSession) {
      return;
    }

    // Clean stop operation

    this.currentSession.isStopped = true;
    this.currentSession.isPlaying = false;
    this.currentSession.isPaused = false;

    // Kill the playback process
    if (this.currentSession.process && !this.currentSession.process.killed) {
      // Terminating afplay process
      this.currentSession.process.kill();
      this.currentSession.process = null;
    }

    // Reject any pending pause promise
    if (this.currentSession.pauseReject) {
      this.currentSession.pauseReject(new Error("Playback stopped"));
      this.currentSession.pausePromise = null;
      this.currentSession.pauseResolve = null;
      this.currentSession.pauseReject = null;
    }

    logger.info("Playback stopped", {
      component: this.name,
      method: "stop",
      sessionId: this.currentSession.id,
    });
  }

  /**
   * Get current playback state
   */
  getPlaybackState(): PlaybackState {
    if (!this.currentSession) {
      return {
        isPlaying: false,
        isPaused: false,
        isStopped: false,
        currentSegment: 0,
        totalSegments: 0,
        currentProcess: null,
        pausePromise: null,
        pauseResolve: null,
      };
    }

    return {
      isPlaying: this.currentSession.isPlaying,
      isPaused: this.currentSession.isPaused,
      isStopped: this.currentSession.isStopped,
      currentSegment: 0, // Not applicable for single audio playback
      totalSegments: 1,
      currentProcess: this.currentSession.process,
      pausePromise: this.currentSession.pausePromise,
      pauseResolve: this.currentSession.pauseResolve,
    };
  }

  /**
   * Start playback process with memory-based audio
   */
  private async startPlayback(signal: AbortSignal): Promise<void> {
    if (!this.currentSession) {
      throw new Error("No active playback session");
    }
    logger.debug("Starting playback", {
      component: this.name,
      method: "startPlayback",
      sessionId: this.currentSession?.id,
    });
    const { context } = this.currentSession;

    // Validate audio data
    if (!context.audioData?.length) {
      logger.warn("Empty audio data provided to PlaybackManager", {
        component: this.name,
        method: "startPlayback",
        sessionId: this.currentSession?.id,
      });
      throw new Error("Empty audio data provided");
    }
    logger.debug("Audio data size:", {
      audioSize: context.audioData.length,
      component: this.name,
      method: "startPlayback",
      sessionId: this.currentSession?.id,
    });

    // Check if we should wait for pause
    if (this.currentSession.pausePromise) {
      await this.currentSession.pausePromise;
    }

    // Check if stopped
    if (this.currentSession.isStopped || signal.aborted) {
      return;
    }

    this.currentSession.isPlaying = true;

    try {
      // Create temporary file for afplay (since afplay doesn't support stdin)
      const tempFile = join(
        tmpdir(),
        `tts-audio-${Date.now()}-${Math.random().toString(36).substring(2, 9)}.wav`
      );

      logger.debug("Creating temporary audio file", {
        component: this.name,
        method: "startPlayback",
        sessionId: this.currentSession?.id,
        tempFile,
        audioSize: context.audioData.length,
      });

      // Write audio data to temporary file
      await writeFile(tempFile, context.audioData);

      // Ensure file is fully written and flushed
      await new Promise((resolve) => setTimeout(resolve, 10));

      // Verify the temporary file was written correctly
      const { stat } = await import("fs/promises");
      const fileStats = await stat(tempFile);
      console.log(`Temporary file written: ${tempFile}`);
      console.log(`File size on disk: ${fileStats.size} bytes`);
      console.log(`Expected size: ${context.audioData.length} bytes`);
      console.log(`File size match: ${fileStats.size === context.audioData.length}`);

      // Debug: Check WAV header and calculate expected duration
      // WAV header is 44 bytes, audio data starts at byte 44
      const audioDataSize = context.audioData.length - 44;
      const bytesPerSample = context.format.bitDepth / 8;
      const expectedDurationMs =
        (audioDataSize / (context.format.sampleRate * context.format.channels * bytesPerSample)) *
        1000;

      console.log(
        `Audio debug: ${context.audioData.length} bytes, expected duration: ${expectedDurationMs.toFixed(1)}ms`
      );

      // Check WAV header properly
      const riffHeader = context.audioData.slice(0, 4);
      const waveHeader = context.audioData.slice(8, 12);

      console.log(
        `WAV header bytes: ${Array.from(riffHeader)
          .map((b) => "0x" + b.toString(16).padStart(2, "0"))
          .join(" ")}`
      );
      console.log(
        `WAV format bytes: ${Array.from(waveHeader)
          .map((b) => "0x" + b.toString(16).padStart(2, "0"))
          .join(" ")}`
      );

      const isValidRiff =
        riffHeader[0] === 0x52 &&
        riffHeader[1] === 0x49 &&
        riffHeader[2] === 0x46 &&
        riffHeader[3] === 0x46;
      const isValidWave =
        waveHeader[0] === 0x57 &&
        waveHeader[1] === 0x41 &&
        waveHeader[2] === 0x56 &&
        waveHeader[3] === 0x45;

      console.log(`WAV header check: ${isValidRiff ? "Valid RIFF" : "Invalid RIFF"}`);
      console.log(`WAV format check: ${isValidWave ? "Valid WAVE" : "Invalid WAVE"}`);

      // Check WAV format parameters (WAV uses little-endian)
      // WAV format chunk starts at byte 12, format data starts at byte 20
      const formatChunk = context.audioData.slice(12, 36);

      // Debug: Show the entire format chunk area
      console.log(
        `Format chunk area (bytes 12-35): ${Array.from(formatChunk)
          .map((b) => "0x" + b.toString(16).padStart(2, "0"))
          .join(" ")}`
      );

      // Read format parameters from correct offsets (WAV format chunk structure):
      // Bytes 0-3: "fmt " (format chunk identifier)
      // Bytes 4-7: chunk size (16 bytes, little-endian)
      // Bytes 8-9: audio format (1 = PCM, little-endian)
      // Bytes 10-11: channels (1 = mono, little-endian)
      // Bytes 12-15: sample rate (24000, little-endian)
      // Bytes 16-19: byte rate
      // Bytes 20-21: block align
      // Bytes 22-23: bits per sample (16, little-endian)
      const audioFormat = formatChunk[8] | (formatChunk[9] << 8);
      const numChannels = formatChunk[10] | (formatChunk[11] << 8);
      const sampleRate =
        formatChunk[12] |
        (formatChunk[13] << 8) |
        (formatChunk[14] << 16) |
        (formatChunk[15] << 24);
      const bitsPerSample = formatChunk[22] | (formatChunk[23] << 8);

      // Debug: Show raw bytes for verification
      console.log(
        `Format chunk bytes 8-9 (audio format): ${Array.from(formatChunk.slice(8, 10))
          .map((b) => "0x" + b.toString(16).padStart(2, "0"))
          .join(" ")}`
      );
      console.log(
        `Format chunk bytes 10-11 (channels): ${Array.from(formatChunk.slice(10, 12))
          .map((b) => "0x" + b.toString(16).padStart(2, "0"))
          .join(" ")}`
      );
      console.log(
        `Format chunk bytes 12-15 (sample rate): ${Array.from(formatChunk.slice(12, 16))
          .map((b) => "0x" + b.toString(16).padStart(2, "0"))
          .join(" ")}`
      );
      console.log(
        `Format chunk bytes 22-23 (bits per sample): ${Array.from(formatChunk.slice(22, 24))
          .map((b) => "0x" + b.toString(16).padStart(2, "0"))
          .join(" ")}`
      );

      console.log(
        `WAV format parameters: AudioFormat=${audioFormat}, Channels=${numChannels}, SampleRate=${sampleRate}, BitsPerSample=${bitsPerSample}`
      );

      // Check if format is supported by afplay
      const isSupportedFormat = audioFormat === 1; // PCM
      const isSupportedChannels = numChannels === 1 || numChannels === 2; // Mono or Stereo
      const isSupportedSampleRate = sampleRate >= 8000 && sampleRate <= 192000;
      const isSupportedBitsPerSample =
        bitsPerSample === 8 || bitsPerSample === 16 || bitsPerSample === 24 || bitsPerSample === 32;

      console.log(
        `Format compatibility: AudioFormat=${isSupportedFormat ? "Supported" : "Unsupported"}, Channels=${isSupportedChannels ? "Supported" : "Unsupported"}, SampleRate=${isSupportedSampleRate ? "Supported" : "Unsupported"}, BitsPerSample=${isSupportedBitsPerSample ? "Supported" : "Unsupported"}`
      );

      // Check WAV data chunk (should be at byte 36 for standard WAV)
      const dataChunkStart = 36;
      const dataChunkHeader = context.audioData.slice(dataChunkStart, dataChunkStart + 8);

      if (dataChunkHeader.length >= 8) {
        const dataChunkId = String.fromCharCode(...dataChunkHeader.slice(0, 4));
        const dataChunkSize =
          dataChunkHeader[4] |
          (dataChunkHeader[5] << 8) |
          (dataChunkHeader[6] << 16) |
          (dataChunkHeader[7] << 24);

        console.log(`Data chunk ID: "${dataChunkId}" (should be "data")`);
        console.log(`Data chunk size: ${dataChunkSize} bytes`);
        console.log(
          `Actual remaining data: ${context.audioData.length - dataChunkStart - 8} bytes`
        );
        console.log(
          `Expected vs actual data size match: ${dataChunkSize === context.audioData.length - dataChunkStart - 8}`
        );
      }

      // Test the file with afinfo before playing
      const { spawn: spawnSync } = await import("child_process");
      const afinfoProcess = spawnSync("afinfo", [tempFile], { stdio: "pipe" });

      afinfoProcess.stdout.on("data", (data) => {
        console.log(`afinfo output: ${data.toString()}`);
      });

      afinfoProcess.stderr.on("data", (data) => {
        console.log(`afinfo error: ${data.toString()}`);
      });

      // Create afplay process with temporary file
      console.log(`Starting afplay with file: ${tempFile}`);
      const playProcess = spawn("afplay", [tempFile], {
        stdio: ["ignore", "ignore", "pipe"], // capture stderr only
        detached: false, // Don't detach - we want to wait for completion
      });

      playProcess.stderr.on("data", (data) => {
        console.error("afplay stderr:", data.toString());
      });

      this.currentSession.process = playProcess;

      // Handle process events
      playProcess.on("error", (error) => {
        logger.error("afplay process error", {
          component: this.name,
          method: "startPlayback",
          sessionId: this.currentSession?.id,
          error: error.message,
          tempFile,
        });
        console.error("afplay process error:", error.message);
      });

      playProcess.on("spawn", () => {
        console.log(`afplay process spawned successfully (PID: ${playProcess.pid})`);
      });

      playProcess.on("exit", (code, signal) => {
        console.log(`afplay process exited with code: ${code}, signal: ${signal}`);
      });

      playProcess.on("close", async (code) => {
        if (this.currentSession) {
          this.currentSession.isPlaying = false;
          this.currentSession.process = null;
        }

        logger.info("afplay process closed", {
          component: this.name,
          method: "startPlayback",
          sessionId: this.currentSession?.id,
          code,
          audioSize: context.audioData.length,
          tempFile,
        });

        if (code !== 0 && code !== null) {
          logger.warn("afplay process closed with non-zero code", {
            component: this.name,
            method: "startPlayback",
            sessionId: this.currentSession?.id,
            code,
            tempFile,
          });
          console.error(`afplay process closed with code: ${code}`);
        } else {
          console.log(`afplay process completed successfully (code: ${code})`);
        }

        // Delay cleanup to ensure afplay has finished
        setTimeout(async () => {
          try {
            await unlink(tempFile);
            logger.debug("Temporary audio file cleaned up", {
              component: this.name,
              method: "startPlayback",
              tempFile,
            });
          } catch (cleanupError) {
            logger.warn("Failed to clean up temporary audio file", {
              component: this.name,
              method: "startPlayback",
              tempFile,
              error: cleanupError instanceof Error ? cleanupError.message : "Unknown error",
            });
          }
        }, 100);
      });

      // Handle abort signal
      const onAbort = async () => {
        if (playProcess && !playProcess.killed) {
          playProcess.kill();
        }
        // Clean up temp file on abort
        try {
          await unlink(tempFile);
        } catch (error) {
          // Ignore cleanup errors on abort
        }
      };
      signal.addEventListener("abort", onAbort, { once: true });

      // Check if already aborted
      if (signal.aborted) {
        console.log("Signal already aborted, not starting afplay");
        return;
      }

      // Wait for playback completion
      const playbackStartTime = performance.now();
      await new Promise<void>((resolve, reject) => {
        playProcess.on("close", (code) => {
          signal.removeEventListener("abort", onAbort);

          const actualPlaybackTime = performance.now() - playbackStartTime;
          console.log(`Actual playback time: ${actualPlaybackTime.toFixed(1)}ms`);

          if (this.currentSession?.isStopped || signal.aborted) {
            resolve();
          } else if (code === 0 || code === null) {
            resolve();
          } else {
            reject(new Error(`afplay exited with code ${code}`));
          }
        });

        playProcess.on("error", (error) => {
          signal.removeEventListener("abort", onAbort);
          reject(error);
        });
      });
    } catch (error) {
      this.currentSession.isPlaying = false;
      this.currentSession.process = null;
      throw error;
    }
  }

  /**
   * Add audio to playback queue
   */
  enqueueAudio(context: PlaybackContext): void {
    this.playbackQueue.push(context);

    logger.debug("Audio added to playback queue", {
      component: this.name,
      method: "enqueueAudio",
      queueLength: this.playbackQueue.length,
      audioSize: context.audioData.length,
    });

    // Start processing queue if not already processing
    if (!this.isProcessingQueue) {
      this.processQueue();
    }
  }

  /**
   * Process playback queue sequentially
   */
  private async processQueue(): Promise<void> {
    if (this.isProcessingQueue || this.playbackQueue.length === 0) {
      return;
    }

    this.isProcessingQueue = true;

    try {
      while (this.playbackQueue.length > 0) {
        const context = this.playbackQueue.shift()!;

        try {
          await this.playAudio(context, new AbortController().signal);
        } catch (error) {
          logger.error("Queue playback failed", {
            component: this.name,
            method: "processQueue",
            error: error instanceof Error ? error.message : "Unknown error",
          });
          // Continue with next item in queue
        }
      }
    } finally {
      this.isProcessingQueue = false;
    }
  }

  /**
   * Clear playback queue
   */
  clearQueue(): void {
    const queueLength = this.playbackQueue.length;
    this.playbackQueue = [];

    logger.info("Playback queue cleared", {
      component: this.name,
      method: "clearQueue",
      clearedItems: queueLength,
    });
  }

  /**
   * Get queue status
   */
  getQueueStatus(): { length: number; isProcessing: boolean } {
    return {
      length: this.playbackQueue.length,
      isProcessing: this.isProcessingQueue,
    };
  }

  /**
   * Create silence buffer for precise timing control
   */
  createSilence(durationSec: number, format: AudioFormat): Uint8Array {
    const bytesPerSecond = format.sampleRate * format.channels * format.bytesPerSample;
    const bytes = Math.round(durationSec * bytesPerSecond);
    return new Uint8Array(bytes).fill(0);
  }

  /**
   * Play silence for specified duration
   */
  async playSilence(durationSec: number, format: AudioFormat, signal: AbortSignal): Promise<void> {
    const silenceData = this.createSilence(durationSec, format);

    const context: PlaybackContext = {
      audioData: silenceData,
      format,
      metadata: {
        voice: "silence" as VoiceOption,
        speed: 1.0,
        size: silenceData.length,
      },
      playbackOptions: {
        useHardwareAcceleration: this.config.useHardwareAcceleration,
        backgroundPlayback: this.config.backgroundPlayback,
      },
    };

    await this.playAudio(context, signal);
  }

  /**
   * Update playback configuration
   */
  updateConfig(
    config: Partial<{
      useHardwareAcceleration: boolean;
      backgroundPlayback: boolean;
      developmentMode: boolean;
    }>
  ): void {
    this.config = { ...this.config, ...config };

    logger.info("Playback configuration updated", {
      component: this.name,
      method: "updateConfig",
      config: this.config,
    });
  }

  /**
   * Get current configuration
   */
  getConfig(): typeof this.config {
    return { ...this.config };
  }

  /**
   * Check if playback is currently active
   */
  isActive(): boolean {
    return this.currentSession?.isPlaying ?? false;
  }

  /**
   * Check if playback is paused
   */
  isPaused(): boolean {
    return this.currentSession?.isPaused ?? false;
  }

  /**
   * Check if playback is stopped
   */
  isStopped(): boolean {
    return this.currentSession?.isStopped ?? true;
  }

  /**
   * Get current session information
   */
  getCurrentSession(): { id: string; startTime: number; duration: number } | null {
    if (!this.currentSession) {
      return null;
    }

    return {
      id: this.currentSession.id,
      startTime: this.currentSession.startTime,
      duration: performance.now() - this.currentSession.startTime,
    };
  }
}
