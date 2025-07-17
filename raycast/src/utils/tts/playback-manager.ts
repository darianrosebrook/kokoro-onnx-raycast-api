/**
 * Playback Manager Controller - Raycast Extension Audio Control Layer
 *
 * This module provides a high-level interface for controlling audio playback through
 * the standalone audio daemon process. It serves as a controller that delegates
 * actual audio processing to the daemon, not an implementation of audio processing itself.
 *
 * ## Architecture Overview
 *
 * The PlaybackManager implements a controller pattern:
 *
 * 1. **Daemon Delegation**: All audio processing is delegated to the standalone audio daemon
 * 2. **State Management**: Manages playback state and session information for the extension
 * 3. **Queue Management**: Handles audio queue and streaming coordination
 * 4. **Error Handling**: Provides error recovery and user feedback
 *
 * ## Key Design Principles
 *
 * - **Separation of Concerns**: Controller only manages state and coordinates with daemon
 * - **Process Isolation**: Audio processing runs in separate daemon process
 * - **Clean Interface**: Simple API for Raycast extension to control audio
 * - **Resource Management**: Proper cleanup and session management
 *
 * @author @darianrosebrook
 * @version 1.0.0
 * @since 2025-07-17
 */

import { logger } from "../core/logger.js";
import type {
  PlaybackContext,
  PlaybackState,
  AudioFormat,
  IPlaybackManager,
  TTSProcessorConfig,
} from "../validation/tts-types.js";
import { AudioPlaybackDaemon } from "./streaming/audio-playback-daemon.js";

/**
 * Playback session information
 */
interface PlaybackSession {
  id: string;
  context: PlaybackContext;
  startTime: number;
  process: unknown | null; // Changed from ChildProcess to unknown as ChildProcess is removed
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
  private audioDaemon: AudioPlaybackDaemon;

  constructor(config: Partial<TTSProcessorConfig> = {}) {
    this.config = {
      useHardwareAcceleration: true,
      backgroundPlayback: true,
      developmentMode: config.developmentMode ?? false,
    };
    this.audioDaemon = new AudioPlaybackDaemon(config);
  }

  /**
   * Initialize the playback manager
   */
  async initialize(config: Partial<TTSProcessorConfig>): Promise<void> {
    if (config.developmentMode !== undefined) {
      this.config.developmentMode = config.developmentMode;
    }
    await this.audioDaemon.initialize();
    this.initialized = true;

    logger.consoleInfo("Playback manager initialized", {
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
  async playAudio(context: PlaybackContext, _signal: AbortSignal): Promise<void> {
    logger.consoleInfo(" [PLAYBACK-MANAGER] === PLAY AUDIO START ===");
    logger.consoleInfo(" [PLAYBACK-MANAGER] Audio playback request:", {
      audioSize: context.audioData.length,
      voice: context.metadata.voice,
      speed: context.metadata.speed,
      format: context.format,
    });

    if (!this.initialized) {
      logger.consoleInfo(" [PLAYBACK-MANAGER]  Playback manager not initialized");
      throw new Error("Playback manager not initialized");
    }

    const sessionId = `playback-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
    logger.consoleInfo(" [PLAYBACK-MANAGER]  Created session:", sessionId);

    const timerId = logger.startTiming("audio-playback", {
      component: this.name,
      method: "playAudio",
      sessionId,
      audioSize: context.audioData.length,
      voice: context.metadata.voice,
    });

    // Stop any existing playback
    logger.consoleInfo(" [PLAYBACK-MANAGER]  Stopping any existing playback");
    await this.stop();

    // Create new playback session
    logger.consoleInfo(" [PLAYBACK-MANAGER]  Creating new playback session");
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
      // Send audio data to daemon in one chunk, then end stream
      logger.consoleInfo(" [PLAYBACK-MANAGER]  Sending audio data to daemon");
      logger.consoleInfo(
        " [PLAYBACK-MANAGER]  Audio data size:",
        context.audioData.length,
        "bytes"
      );

      try {
        await this.audioDaemon.writeChunk(context.audioData);
        logger.consoleInfo(" [PLAYBACK-MANAGER] ✅ Audio chunk sent to daemon");

        await this.audioDaemon.endStream();
        logger.consoleInfo(" [PLAYBACK-MANAGER] ✅ Audio stream ended");
      } catch (error) {
        logger.error("Audio daemon playback failed", {
          component: this.name,
          method: "playAudio",
          error: error instanceof Error ? error.message : "Unknown error",
        });
        throw error;
      }

      const duration = logger.endTiming(timerId, {
        success: true,
        sessionId,
        audioSize: context.audioData.length,
      });

      logger.consoleInfo(" [PLAYBACK-MANAGER]  Audio playback completed:", {
        sessionId,
        duration: `${duration}ms`,
        audioSize: context.audioData.length,
      });

      logger.consoleInfo("Audio playback completed", {
        component: this.name,
        method: "playAudio",
        sessionId,
        duration: `${duration}ms`,
        audioSize: context.audioData.length,
      });
    } catch (error) {
      logger.consoleError("Audio playback failed", {
        component: this.name,
        method: "playAudio",
        sessionId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      throw error;
    }
  }

  /**
   * Start streaming playback and return control interface
   */
  async startStreamingPlayback(signal: AbortSignal): Promise<any> {
    logger.consoleInfo("[PLAYBACK-MANAGER] startStreamingPlayback() called");
    if (!this.initialized) {
      throw new Error("Playback manager not initialized");
    }

    logger.consoleInfo("Starting streaming playback", {
      component: this.name,
      method: "startStreamingPlayback",
    });

    // Stop any existing playback
    await this.stop();

    // Start playback in the daemon
    await this.audioDaemon.startPlayback();

    const playback = {
      writeChunk: async (chunk: Uint8Array) => {
        await this.audioDaemon.writeChunk(chunk);
      },
      endStream: async () => {
        await this.audioDaemon.endStream();
      },
      onProcessEnd: (normalTermination: boolean) => {
        logger.consoleInfo("Streaming playback ended", {
          component: this.name,
          method: "startStreamingPlayback",
          normalTermination,
        });
      },
    };
    logger.consoleInfo("[PLAYBACK-MANAGER] Streaming playback started");
    return playback;
  }

  /**
   * Pause playback
   */
  pause(): void {
    if (!this.currentSession || this.currentSession.isStopped) {
      logger.warn("Cannot pause - no active session", {
        component: this.name,
        method: "pause",
      });
      return;
    }

    if (this.currentSession.isPaused) {
      logger.debug("Playback already paused", {
        component: this.name,
        method: "pause",
        sessionId: this.currentSession.id,
      });
      return;
    }

    logger.consoleInfo("Pausing playback", {
      component: this.name,
      method: "pause",
      sessionId: this.currentSession.id,
    });

    this.currentSession.isPaused = true;
    this.currentSession.isPlaying = false;

    // Pause the audio daemon
    this.audioDaemon.pause().catch((error) => {
      logger.error("Failed to pause audio daemon", {
        component: this.name,
        method: "pause",
        error: error instanceof Error ? error.message : "Unknown error",
      });
    });

    logger.consoleInfo("Playback paused", {
      component: this.name,
      method: "pause",
      sessionId: this.currentSession.id,
    });
  }

  /**
   * Resume playback
   */
  resume(): void {
    if (!this.currentSession || this.currentSession.isStopped) {
      logger.warn("Cannot resume - no active session", {
        component: this.name,
        method: "resume",
      });
      return;
    }

    if (!this.currentSession.isPaused) {
      logger.debug("Playback not paused", {
        component: this.name,
        method: "resume",
        sessionId: this.currentSession.id,
      });
      return;
    }

    logger.consoleInfo("Resuming playback", {
      component: this.name,
      method: "resume",
      sessionId: this.currentSession.id,
    });

    this.currentSession.isPlaying = true;
    this.currentSession.isPaused = false;

    // Resume the audio daemon
    this.audioDaemon.resume().catch((error) => {
      logger.error("Failed to resume audio daemon", {
        component: this.name,
        method: "resume",
        error: error instanceof Error ? error.message : "Unknown error",
      });
    });

    logger.consoleInfo("Playback resumed", {
      component: this.name,
      method: "resume",
      sessionId: this.currentSession.id,
    });
  }

  /**
   * Stop playback
   */
  async stop(): Promise<void> {
    logger.consoleInfo("Stopping playback", {
      component: this.name,
      method: "stop",
      sessionId: this.currentSession?.id,
    });

    // Stop the audio daemon
    await this.audioDaemon.stop();

    if (this.currentSession) {
      this.currentSession.isPlaying = false;
      this.currentSession.isPaused = false;
      this.currentSession.isStopped = true;
    }

    logger.consoleInfo("Playback stopped", {
      component: this.name,
      method: "stop",
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
        isStopped: true,
        currentSegment: 0,
        totalSegments: 0,
        currentProcess: null,
        pausePromise: null,
        pauseResolve: null,
      };
    }

    // const currentSegment = this.currentSession.isStopped
    //   ? 0
    //   : (performance.now() - this.currentSession.startTime) / 1000;

    return {
      isPlaying: this.currentSession.isPlaying,
      isPaused: this.currentSession.isPaused,
      isStopped: this.currentSession.isStopped,
      currentSegment: 0,
      totalSegments: 0,
      currentProcess: null,
      pausePromise: null,
      pauseResolve: null,
    };
  }

  /**
   * Enqueue audio for playback
   */
  enqueueAudio(context: PlaybackContext): void {
    this.playbackQueue.push(context);
    logger.debug("Audio enqueued", {
      component: this.name,
      method: "enqueueAudio",
      queueLength: this.playbackQueue.length,
      audioSize: context.audioData.length,
    });

    if (!this.isProcessingQueue) {
      this.processQueue().catch((error) => {
        logger.error("Queue processing failed", {
          component: this.name,
          method: "enqueueAudio",
          error: error instanceof Error ? error.message : "Unknown error",
        });
      });
    }
  }

  /**
   * Process the audio queue
   */
  private async processQueue(): Promise<void> {
    if (this.isProcessingQueue || this.playbackQueue.length === 0) {
      return;
    }

    this.isProcessingQueue = true;

    while (this.playbackQueue.length > 0) {
      const context = this.playbackQueue.shift()!;
      try {
        await this.playAudio(context, new AbortController().signal);
      } catch (error) {
        logger.error("Failed to play queued audio", {
          component: this.name,
          method: "processQueue",
          error: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }

    this.isProcessingQueue = false;
  }

  /**
   * Clear the audio queue
   */
  clearQueue(): void {
    this.playbackQueue = [];
    this.isProcessingQueue = false;

    logger.consoleInfo("Audio queue cleared", {
      component: this.name,
      method: "clearQueue",
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
   * Create silence audio data
   */
  createSilence(durationSec: number, format: AudioFormat): Uint8Array {
    const samples = Math.floor(durationSec * format.sampleRate * format.channels);
    return new Uint8Array(samples * format.bytesPerSample);
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
        voice: "am_adam",
        speed: 1.0,
        duration: durationSec,
        size: silenceData.length,
      },
      playbackOptions: {
        volume: 1.0,
        useHardwareAcceleration: this.config.useHardwareAcceleration,
        backgroundPlayback: this.config.backgroundPlayback,
      },
    };

    await this.playAudio(context, signal);
  }

  /**
   * Update configuration
   */
  updateConfig(
    config: Partial<{
      useHardwareAcceleration: boolean;
      backgroundPlayback: boolean;
      developmentMode: boolean;
    }>
  ): void {
    this.config = { ...this.config, ...config };

    logger.consoleInfo("Playback manager configuration updated", {
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
   * Check if playback is active
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

    const duration = this.currentSession.isStopped
      ? 0
      : (performance.now() - this.currentSession.startTime) / 1000;

    return {
      id: this.currentSession.id,
      startTime: this.currentSession.startTime,
      duration,
    };
  }

  /**
   * Get the current port being used by the daemon
   */
  getDaemonPort(): number | null {
    try {
      return this.audioDaemon.getCurrentPort();
    } catch (error) {
      logger.warn("Failed to get daemon port", {
        component: this.name,
        method: "getDaemonPort",
        error: error instanceof Error ? error.message : "Unknown error",
      });
      return null;
    }
  }
}
