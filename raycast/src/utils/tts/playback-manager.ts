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
import { logger } from "../core/logger";
import type {
  IPlaybackManager,
  PlaybackContext,
  PlaybackState,
  AudioFormat,
  TTSProcessorConfig,
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

    const sessionId = `playback-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

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

    this.currentSession.isStopped = true;
    this.currentSession.isPlaying = false;
    this.currentSession.isPaused = false;

    // Kill the playback process
    if (this.currentSession.process && !this.currentSession.process.killed) {
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

    const { context } = this.currentSession;

    // Validate audio data
    if (!context.audioData?.length) {
      throw new Error("Empty audio data provided");
    }

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
      // Create afplay process with stdin piping
      const playProcess = spawn("afplay", ["-"], {
        stdio: ["pipe", "ignore", "ignore"],
        detached: this.config.backgroundPlayback,
      });

      this.currentSession.process = playProcess;

      // Handle process events
      playProcess.on("error", (error) => {
        logger.error("afplay process error", {
          component: this.name,
          method: "startPlayback",
          sessionId: this.currentSession?.id,
          error: error.message,
        });
      });

      playProcess.on("close", (code) => {
        if (this.currentSession) {
          this.currentSession.isPlaying = false;
          this.currentSession.process = null;
        }

        if (code !== 0 && code !== null) {
          logger.warn("afplay process closed with non-zero code", {
            component: this.name,
            method: "startPlayback",
            sessionId: this.currentSession?.id,
            code,
          });
        }
      });

      // Handle abort signal
      const onAbort = () => {
        if (playProcess && !playProcess.killed) {
          playProcess.kill();
        }
      };
      signal.addEventListener("abort", onAbort, { once: true });

      // Write audio data to stdin
      playProcess.stdin.write(context.audioData);
      playProcess.stdin.end();

      // Wait for playback completion
      await new Promise<void>((resolve, reject) => {
        playProcess.on("close", (code) => {
          signal.removeEventListener("abort", onAbort);

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
        voice: "silence" as any,
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
