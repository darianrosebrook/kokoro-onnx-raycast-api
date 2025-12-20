#!/usr/bin/env node

/**
 * Audio Daemon - Native Audio Processing Engine
 *
 * This daemon provides persistent audio playback capabilities with native
 * CoreAudio integration, eliminating the need for external binaries like sox/ffplay.
 *
 * Features:
 * - WebSocket-based communication for real-time control
 * - Native CoreAudio integration via node-speaker
 * - Ring buffer management for smooth streaming
 * - Health monitoring and automatic recovery
 * - Format validation and audio processing
 *
 * @author @darianrosebrook
 * @version 2.0.0
 * @since 2025-07-17
 * @license MIT
 */

import WebSocket, { WebSocketServer } from "ws";
import http from "http";
import { spawn } from "child_process";
import { EventEmitter } from "events";

/**
 * Simple logger for the audio daemon
 */
class SimpleLogger {
  constructor() {
    this.isDebugMode = this.checkDebugMode();
  }

  checkDebugMode() {
    const hasDebugFlag = process.argv.includes("--debug") || process.argv.includes("-d");
    const hasAudioDebug = process.env.AUDIO_DEBUG === "true" || process.env.AUDIO_DEBUG === "1";

    // Be very restrictive - only enable debug mode when explicitly requested
    // Don't inherit broad debug flags from parent processes
    return hasDebugFlag || hasAudioDebug;
  }

  info(message, ...args) {
    const timestamp = new Date().toLocaleTimeString();
    console.log(`${timestamp} [INFO]: ${message}`, ...args);
  }

  warn(message, ...args) {
    const timestamp = new Date().toLocaleTimeString();
    console.warn(`${timestamp} [WARN]: ${message}`, ...args);
  }

  error(message, ...args) {
    const timestamp = new Date().toLocaleTimeString();
    console.error(`${timestamp} [ERROR]: ${message}`, ...args);
  }

  debug(message, ...args) {
    if (this.isDebugMode) {
      const timestamp = new Date().toLocaleTimeString();
      console.log(`${timestamp} [DEBUG]: ${message}`, ...args);
    }
  }

  consoleInfo(message, ...args) {
    console.log(message, ...args);
  }

  consoleWarn(message, ...args) {
    console.warn(message, ...args);
  }

  consoleError(message, ...args) {
    console.error(message, ...args);
  }
}

const logger = new SimpleLogger();

/**
 * Debug logging function
 */
function debugLog(message, ...args) {
  if (logger.isDebugMode) {
    console.warn(message, ...args);
  }
}

/**
 * Audio format configuration
 */
class AudioFormat {
  constructor(format, sampleRate, channels, bitDepth) {
    this.format = format;
    this.sampleRate = sampleRate;
    this.channels = channels;
    this.bitDepth = bitDepth;
    this.bytesPerSample = bitDepth / 8;
    this.bytesPerSecond = sampleRate * channels * this.bytesPerSample;

    // Validate format
    this.validate();
  }

  validate() {
    if (![8000, 16000, 22050, 24000, 32000, 44100, 48000].includes(this.sampleRate)) {
      console.warn(`[AUDIO-FORMAT] Unusual sample rate: ${this.sampleRate}Hz`);
    }
    if (![1, 2].includes(this.channels)) {
      throw new Error(`Unsupported channel count: ${this.channels}`);
    }
    if (![8, 16, 24, 32].includes(this.bitDepth)) {
      throw new Error(`Unsupported bit depth: ${this.bitDepth}`);
    }
  }

  getSoxEncoding() {
    switch (this.bitDepth) {
      case 8:
        return "unsigned-integer";
      case 16:
        return "signed-integer";
      case 24:
        return "signed-integer";
      case 32:
        return "floating-point";
      default:
        return "signed-integer";
    }
  }

  getFfplayFormat() {
    switch (this.bitDepth) {
      case 8:
        return "u8";
      case 16:
        return "s16le";
      case 24:
        return "s24le";
      case 32:
        return "f32le";
      default:
        return "s16le";
    }
  }
}

/**
 * Ring buffer for audio streaming
 */
class AudioRingBuffer {
  constructor(capacity) {
    this.capacity = capacity;
    this.buffer = Buffer.alloc(capacity);
    this.readIndex = 0;
    this.writeIndex = 0;
    this.size = 0;
    this.isFinished = false;
  }

  // Dynamically grow the ring buffer to accommodate additional bytes while preserving order
  _ensureCapacity(additionalBytes) {
    const required = this.size + additionalBytes;
    if (required <= this.capacity) return;

    // Grow capacity with headroom (1.5x) until it fits the required size
    let newCapacity = this.capacity;
    while (newCapacity < required) {
      newCapacity = Math.ceil(newCapacity * 1.5);
    }

    const newBuffer = Buffer.alloc(newCapacity);

    // Copy existing data in logical order (from readIndex, wrapping if needed)
    const firstPart = Math.min(this.size, this.capacity - this.readIndex);
    this.buffer.copy(newBuffer, 0, this.readIndex, this.readIndex + firstPart);
    if (firstPart < this.size) {
      this.buffer.copy(newBuffer, firstPart, 0, this.size - firstPart);
    }

    // Swap buffers and reset indices to linear layout
    this.buffer = newBuffer;
    this.capacity = newCapacity;
    this.readIndex = 0;
    this.writeIndex = this.size;

    debugLog(
      `Ring buffer grown to ${this.capacity} bytes (~${(this.capacity / (1024 * 1024)).toFixed(2)} MB)`
    );
  }

  write(data) {
    // Ensure capacity so we never drop audio for longer streams
    this._ensureCapacity(data.length);

    const available = this.capacity - this.size;
    available === 0 &&
      debugLog(`Buffer is full`, "color: #FFAAAA; background-color: #222222; font-weight: bold");
    debugLog(`Buffer size: ${this.size}, available: ${available}, capacity: ${this.capacity}`);

    const toWrite = Math.min(data.length, available);
    debugLog(`Writing to buffer:`, toWrite, "bytes", "capacity:", this.capacity);
    if (toWrite === 0) return 0;

    // Write data in one or two parts (if wrapping around)
    const firstPart = Math.min(toWrite, this.capacity - this.writeIndex);
    data.copy(this.buffer, this.writeIndex, 0, firstPart);

    if (firstPart < toWrite) {
      // Wrap around to beginning
      data.copy(this.buffer, 0, firstPart, toWrite);
    }

    this.writeIndex = (this.writeIndex + toWrite) % this.capacity;
    this.size += toWrite;

    return toWrite;
  }

  read(length) {
    const toRead = Math.min(length, this.size);
    if (toRead === 0) return Buffer.alloc(0);

    const result = Buffer.alloc(toRead);

    // Read data in one or two parts (if wrapping around)
    const firstPart = Math.min(toRead, this.capacity - this.readIndex);
    this.buffer.copy(result, 0, this.readIndex, this.readIndex + firstPart);

    if (firstPart < toRead) {
      // Wrap around to beginning
      this.buffer.copy(result, firstPart, 0, toRead - firstPart);
    }

    this.readIndex = (this.readIndex + toRead) % this.capacity;
    this.size -= toRead;

    return result;
  }

  get utilization() {
    return this.size / this.capacity;
  }

  get available() {
    return this.capacity - this.size;
  }

  clear() {
    this.readIndex = 0;
    this.writeIndex = 0;
    this.size = 0;
    this.isFinished = false;
  }

  markFinished() {
    this.isFinished = true;
  }
}

/**
 * Audio processor using native CoreAudio
 */
class AudioProcessor extends EventEmitter {
  constructor(format) {
    super();
    this.instanceId = this.constructor.name + "_" + Date.now();
    this.format = format;
    // Start with smaller buffer for better TTFA, will grow dynamically if needed
    this.ringBuffer = new AudioRingBuffer(this.format.bytesPerSecond * 2); // 2 seconds initial buffer
    this.audioProcess = null;
    this.isPlaying = false;
    this.isPaused = false;
    this.isStopped = false;
    this.isStopping = false;
    this.restartTimeout = null;
    this.restartAttempts = 0;
    this.MAX_RESTARTS = 5;
    this.lastRestartTime = 0;
    this._highUtilization = false; // Flow control state
    this._audioLoopActive = false; // Prevent re-entrancy
    this._audioLoopInterval = null; // Interval reference
    this.stats = {
      chunksReceived: 0,
      bytesProcessed: 0,
      audioPosition: 0,
      underruns: 0,
      bufferUtilization: 0,
      expectedDuration: 0,
      actualDuration: 0,
      playbackStartTime: 0,
      playbackEndTime: 0,
      // Enhanced timing metrics
      firstChunkTime: 0,
      lastChunkTime: 0,
      totalChunksReceived: 0,
      averageChunkSize: 0,
      processingOverhead: 0,
      timingAccuracy: 0,
    };
    this.lastHeartbeat = Date.now();
    this.isEndingStream = false; // New flag for ending stream
    this._completionEmitted = false; // Prevent double completion emission
    this._endStreamTimeout = null; // Timeout for forcing completion when end_stream is received

    // Duration-based process management
    this.totalAudioBytes = 0; // Total bytes of audio to be played
    this.audioDurationMs = 0; // Calculated duration in milliseconds
    this.processKeepAliveTimer = null; // Timer to keep process alive
    this.processStartTime = 0; // When the process started playing

    console.log(`[${this.instanceId}] Constructor called with format:`, this.format);
    console.log(`[${this.instanceId}] Instance ID:`, this.instanceId);
    console.log(
      `[${this.instanceId}] Buffer capacity: ${this.ringBuffer.capacity} bytes (${(this.ringBuffer.capacity / this.format.bytesPerSecond).toFixed(1)}s)`
    );
  }

  /**
   * Start audio playback
   */
  async start() {
    // Guard: Don't reset if playback is active
    if (this.isPlaying) {
      console.log(`[${this.instanceId}] start() called but already playing - ignoring`);
      return;
    }

    // Guard: Don't reset if there's still audio data in the buffer
    // This prevents data loss when a new client reconnects during playback
    if (this.ringBuffer.size > 0 && !this.isStopped) {
      console.log(
        `[${this.instanceId}] start() called but buffer has ${this.ringBuffer.size} bytes - resuming instead of resetting`
      );
      // Resume the audio loop if it's not active
      if (!this._audioLoopActive && this.audioProcess && !this.audioProcess.killed) {
        console.log(`[${this.instanceId}] Restarting audio processing loop to drain buffer`);
        this.startRobustAudioLoop();
      }
      return;
    }

    console.log(`[${this.instanceId}] Starting new audio session - resetting state`);

    // Force stop any existing processing loop
    this._audioLoopActive = false;
    if (this._audioLoopInterval) {
      clearInterval(this._audioLoopInterval);
      this._audioLoopInterval = null;
    }

    // Complete session reset for new playback
    this.isStopping = false;
    this.isStopped = false;
    this.isPlaying = false; // Force reset playing state
    this.restartAttempts = 0;
    this.isEndingStream = false;
    this.afplayMode = false;

    // Only clear ring buffer if it's truly a new session (buffer is already empty or we're explicitly stopped)
    if (this.ringBuffer.size > 0) {
      console.log(
        `[${this.instanceId}] WARNING: Clearing ${this.ringBuffer.size} bytes from buffer - this should not happen`
      );
    }
    this.ringBuffer.clear();
    console.log(`[${this.instanceId}] Cleared ring buffer for new session`);

    // Reset audio process
    if (this.audioProcess) {
      try {
        this.audioProcess.kill("SIGTERM");
      } catch (e) {
        // Process might already be dead, RIP little buddy
      }
      this.audioProcess = null;
    }

    // Clear any timers
    if (this.processKeepAliveTimer) {
      clearTimeout(this.processKeepAliveTimer);
      this.processKeepAliveTimer = null;
    }
    if (this.restartTimeout) {
      clearTimeout(this.restartTimeout);
      this.restartTimeout = null;
    }
    if (this._endStreamTimeout) {
      clearTimeout(this._endStreamTimeout);
      this._endStreamTimeout = null;
    }

    // Cleanup afplay mode
    this.cleanupAfplayMode();

    // Reset ALL stats for new playback session
    this.stats.chunksReceived = 0;
    this.stats.bytesProcessed = 0;
    this.stats.audioPosition = 0;
    this.stats.underruns = 0;
    this.stats.bufferUtilization = 0;
    this.stats.playbackStartTime = 0;
    this.stats.playbackEndTime = 0;
    this.stats.actualDuration = 0;
    this.stats.expectedDuration = 0;
    this._completionEmitted = false; // Reset completion flag for new session
    this.stats.firstChunkTime = 0;
    this.stats.lastChunkTime = 0;
    this.stats.totalChunksReceived = 0;
    this.stats.averageChunkSize = 0;
    this.stats.processingOverhead = 0;
    this.stats.timingAccuracy = 0;

    // Reset audio byte tracking
    this.totalAudioBytes = 0;
    this.audioDurationMs = 0;

    debugLog(`Starting audio playback with format:`, this.format);

    // Use sox for native audio playback (fallback to ffplay if needed)
    const soxArgs = [
      "-V3", // Verbose logging to debug format issues
      "-t",
      "raw",
      "-e",
      this.format.getSoxEncoding(),
      "-b",
      this.format.bitDepth.toString(),
      "-c",
      this.format.channels.toString(),
      "-r",
      this.format.sampleRate.toString(),
      "-",
      "-d", // Output to default audio device
    ];

    try {
      // Try to find sox in common locations (like the test implementation)
      const soxCandidates = [
        "sox", // Try PATH first
        "/opt/homebrew/bin/sox", // Homebrew on Apple Silicon
        "/usr/local/bin/sox", // Homebrew on Intel
        "/usr/bin/sox", // System sox
      ];
      let soxPath = null;
      let lastError = null;

      for (const candidate of soxCandidates) {
        try {
          // Actually try to run sox (like the test implementation)
          const { execSync } = await import("child_process");
          execSync(`${candidate} --version`, {
            stdio: "ignore",
            env: {
              ...process.env,
              PATH: process.env.PATH || "",
            },
          });
          soxPath = candidate;
          debugLog(`Found sox at: ${soxPath}`);
          break;
        } catch (e) {
          // Continue to next candidate
          debugLog(`sox not found at: ${candidate}`);
          lastError = e;
        }
      }

      if (!soxPath) {
        debugLog(`Sox not found in any location, falling back to ffplay`);
        this.startWithFfplay();
        return;
      }
      debugLog(`Spawning sox at: ${soxPath}`);
      this.audioProcess = spawn(soxPath, soxArgs, {
        stdio: ["pipe", "ignore", "pipe"],
        detached: false,
        env: {
          ...process.env,
          PATH: process.env.PATH + ":/opt/homebrew/bin:/usr/local/bin:/usr/bin",
        },
      });

      // Configure sox stdin for better back-pressure handling
      if (this.audioProcess.stdin) {
        this.audioProcess.stdin.setDefaultEncoding("binary");
        // Increase the high water mark to reduce back-pressure frequency
        this.audioProcess.stdin._writableState.highWaterMark = 65536; // 64KB buffer

        // Handle stdin errors gracefully
        this.audioProcess.stdin.on("error", (error) => {
          if (error.code === "EPIPE") {
            console.log(`[${this.instanceId}] Sox stdin pipe closed - sox process terminated`);
            // Stop the audio processing loop to prevent further EPIPE errors
            this._audioLoopActive = false;
          } else {
            console.error(`[${this.instanceId}] Sox stdin error:`, error.message);
          }
        });
      }

      this.audioProcess.on("error", (error) => {
        console.error("Audio process error:", error.message);
        this.emit("error", error);
        this.isPlaying = false;
      });

      this.audioProcess.on("exit", (code, signal) => {
        console.log("Audio process exited:", code, signal);
        this.isPlaying = false;

        // Clear the keep-alive timer
        if (this.processKeepAliveTimer) {
          clearTimeout(this.processKeepAliveTimer);
          this.processKeepAliveTimer = null;
          console.log(`[${this.instanceId}] Cleared process keep-alive timer on exit`);
        }

        // Record playback end time and calculate actual duration
        this.stats.playbackEndTime = performance.now();
        this.stats.actualDuration = this.stats.playbackEndTime - this.stats.playbackStartTime;

        // Calculate timing accuracy and processing overhead
        this.stats.timingAccuracy =
          this.stats.actualDuration > 0
            ? (this.stats.expectedDuration / this.stats.actualDuration) * 100
            : 0;
        this.stats.processingOverhead = this.stats.actualDuration - this.stats.expectedDuration;

        console.log(`[${this.instanceId}] Playback timing:`, {
          startTime: this.stats.playbackStartTime.toFixed(2) + "ms",
          endTime: this.stats.playbackEndTime.toFixed(2) + "ms",
          actualDuration: this.stats.actualDuration.toFixed(2) + "ms",
          expectedDuration: this.stats.expectedDuration.toFixed(2) + "ms",
          difference: (this.stats.actualDuration - this.stats.expectedDuration).toFixed(2) + "ms",
          accuracy: this.stats.timingAccuracy.toFixed(1) + "%",
          processingOverhead: this.stats.processingOverhead.toFixed(2) + "ms",
          totalChunks: this.stats.totalChunksReceived,
          averageChunkSize: this.stats.averageChunkSize.toFixed(0) + " bytes",
        });

        // If process exited normally (code 0), check if we should restart to play remaining data
        if (code === 0) {
          // Check if there's significant audio data still in the buffer
          const remainingBytes = this.ringBuffer.size;
          const remainingMs = (remainingBytes / this.format.bytesPerSecond) * 1000;
          
          if (remainingBytes > 0 && remainingMs > 100) {
            // Significant audio data remains - sox exited prematurely
            console.log(
              `[${this.instanceId}] Sox exited but ${remainingBytes} bytes (${remainingMs.toFixed(0)}ms) remain in buffer - restarting to play remaining audio`
            );
            this.isPlaying = false;
            this.restartAudioProcess();
          } else {
            console.log("Audio playback completed successfully");
            // Clear any small remaining buffer data and reset state
            if (remainingBytes > 0) {
              console.log(
                `[${this.instanceId}] Clearing minimal remaining buffer data: ${remainingBytes} bytes`
              );
              this.ringBuffer.clear();
            }
            // Reset state for next playback
            this.isPlaying = false;
            this.isStopped = false;
            this.isStopping = false;
            this.restartAttempts = 0;
            
            // CRITICAL FIX: If we're ending stream, use _completePlaybackSession() to ensure
            // proper completion handling and avoid double emission
            if (this.isEndingStream) {
              console.log(
                `[${this.instanceId}] Process exited while ending stream - completing playback session`
              );
              this._completePlaybackSession();
            } else {
              // Normal completion - emit directly
              this.emit("completed");
            }
          }
        } else {
          console.log("Audio process exited with error, restarting...");
          this.restartAudioProcess();
        }
      });

      this.audioProcess.on("close", (code) => {
        console.log("Audio process closed:", code);
        this.isPlaying = false;

        // Record playback end time if not already recorded
        if (this.stats.playbackEndTime === 0) {
          this.stats.playbackEndTime = performance.now();
          this.stats.actualDuration = this.stats.playbackEndTime - this.stats.playbackStartTime;

          // Calculate timing accuracy and processing overhead
          this.stats.timingAccuracy =
            this.stats.actualDuration > 0
              ? (this.stats.expectedDuration / this.stats.actualDuration) * 100
              : 0;
          this.stats.processingOverhead = this.stats.actualDuration - this.stats.expectedDuration;

          console.log(`[${this.instanceId}] Playback timing (close):`, {
            startTime: this.stats.playbackStartTime.toFixed(2) + "ms",
            endTime: this.stats.playbackEndTime.toFixed(2) + "ms",
            actualDuration: this.stats.actualDuration.toFixed(2) + "ms",
            expectedDuration: this.stats.expectedDuration.toFixed(2) + "ms",
            difference: (this.stats.actualDuration - this.stats.expectedDuration).toFixed(2) + "ms",
            accuracy: this.stats.timingAccuracy.toFixed(1) + "%",
            processingOverhead: this.stats.processingOverhead.toFixed(2) + "ms",
            totalChunks: this.stats.totalChunksReceived,
            averageChunkSize: this.stats.averageChunkSize.toFixed(0) + " bytes",
          });
        }

        // Clear any remaining buffer data when process is closed
        if (this.ringBuffer.size > 0) {
          console.log(
            `[${this.instanceId}] Clearing buffer data after process close: ${this.ringBuffer.size} bytes`
          );
          this.ringBuffer.clear();
        }
      });

      // Handle stdin errors
      if (this.audioProcess.stdin) {
        this.audioProcess.stdin.on("error", (error) => {
          if (error.code === "EPIPE") {
            console.log("Audio process stdin pipe closed - sox process terminated");
            this.isPlaying = false;
            // Don't restart automatically during EPIPE - this is normal when audio completes
          } else {
            console.error("Audio process stdin error:", error.message);
            // For other errors, attempt restart
            this.restartAudioProcess();
          }
        });
      }

      this.isPlaying = true;
      this.waitForDataAndStart();
    } catch (error) {
      console.error("Failed to start sox, trying ffplay:", error.message);
      this.startWithFfplay();
    }
  }

  waitForDataAndStart() {
    console.log(`[${this.instanceId}] waitForDataAndStart called`);
    // Use 50ms chunks to match the processing loop
    const chunkSize = this.format.bytesPerSecond * 0.05; // 50ms chunks
    // Buffer 250ms of audio before starting playback to prevent initial stuttering
    // This provides enough headroom for the first segment to generate sufficient audio
    // 250ms is still below the human perception threshold for "delay"
    const minBufferSize = chunkSize * 5; // Wait for 5 chunks (250ms) before starting
    const fallbackBufferSize = chunkSize * 2; // Start with at least 2 chunks after timeout
    const maxWaitTime = 2000; // 2 seconds max wait
    const startTime = performance.now();

    console.log(`[${this.instanceId}] Waiting for`, minBufferSize, "bytes to start playback");

    const checkBuffer = () => {
      // Don't exit early if isPlaying is false - it might be set to false temporarily
      // Only exit if we've been explicitly stopped
      if (this.isStopped) {
        console.log(`[${this.instanceId}] Stopped, stopping buffer check`);
        return;
      }

      const elapsed = performance.now() - startTime;
      const currentBufferSize = this.ringBuffer.size;
      const adaptiveThreshold = elapsed > maxWaitTime ? fallbackBufferSize : minBufferSize;

      debugLog(
        `[${this.instanceId}] Buffer check:`,
        currentBufferSize,
        "/",
        adaptiveThreshold,
        "bytes (elapsed:",
        elapsed,
        "ms, isPlaying:",
        this.isPlaying,
        ", isStopped:",
        this.isStopped,
        ")"
      );

      if (currentBufferSize >= adaptiveThreshold) {
        console.log(`[${this.instanceId}] Buffer threshold met, starting audio processing loop`);
        this.processAudioLoop();
      } else if (elapsed > maxWaitTime) {
        console.log(
          `[${this.instanceId}] Timeout reached, starting with low buffer (underrun recovery)`
        );
        this.stats.underruns++;
        this.processAudioLoop();
      } else {
        // Continue checking
        setTimeout(checkBuffer, 50);
      }
    };

    checkBuffer();
  }

  /**
   * Fallback to ffplay if sox fails
   */
  startWithFfplay() {
    const ffplayArgs = [
      "-f",
      this.format.getFfplayFormat(),
      "-ar",
      this.format.sampleRate.toString(),
      "-ac",
      this.format.channels.toString(),
      "-i",
      "pipe:0",
      "-nodisp",
      "-autoexit",
      "-hide_banner",
      "-loglevel",
      "error",
    ];

    try {
      this.audioProcess = spawn("ffplay", ffplayArgs, {
        stdio: ["pipe", "ignore", "pipe"],
        detached: false,
      });

      this.audioProcess.on("error", (error) => {
        console.error("Audio process error:", error.message);
        this.emit("error", error);
      });

      this.audioProcess.on("exit", (code, signal) => {
        console.log("Audio process exited:", code, signal);
        this.isPlaying = false;
        this.emit("exit", { code, signal });
      });

      this.isPlaying = true;
      // Mirror sox: wait for buffer before starting playback
      this.waitForDataAndStart();
    } catch (error) {
      console.error("ffplay failed, trying afplay:", error.message);
      this.startWithAfplay();
    }
  }

  /**
   * Final fallback to afplay (macOS native player) if sox and ffplay fail
   * Uses chunked temporary files for streaming-like playback
   */
  startWithAfplay() {
    try {
      const fs = require("fs");
      const os = require("os");
      const path = require("path");

      // Initialize afplay chunked streaming mode
      this.afplayMode = true;
      this.tempDir = path.join(os.tmpdir(), `audio-daemon-${this.instanceId}`);
      this.chunkCounter = 0;
      this.playbackQueue = [];
      this.currentlyPlaying = null;
      this.isPlaying = true;

      // Create temp directory
      if (!fs.existsSync(this.tempDir)) {
        fs.mkdirSync(this.tempDir, { recursive: true });
      }

      console.log(
        `[${this.instanceId}] Started afplay chunked mode using temp dir: ${this.tempDir}`
      );

      // Start the chunk processing loop
      this.processAfplayChunks();
    } catch (error) {
      console.error("All audio players (sox, ffplay, afplay) failed:", error.message);
      this.emit("error", new Error("No compatible audio player found"));
    }
  }

  /**
   * Process incoming audio data in afplay mode by creating temporary WAV files
   */
  processAfplayChunks() {
    const fs = require("fs");
    const path = require("path");

    let chunkBuffer = Buffer.alloc(0);
    const CHUNK_SIZE = this.format.sampleRate * 2; // 1 second of 16-bit mono audio

    const processChunk = () => {
      if (!this.afplayMode || !this.isPlaying) return;

      // Check if we have enough data for a chunk
      const available = this.ringBuffer.size;
      if (available >= CHUNK_SIZE || (available > 0 && this.ringBuffer.isFinished)) {
        const chunkSize = Math.min(available, CHUNK_SIZE);
        const audioData = Buffer.alloc(chunkSize);

        this.ringBuffer.read(audioData);

        // Create WAV file from PCM data
        const wavData = this.createWAVFromPCM(audioData);
        const chunkFile = path.join(this.tempDir, `chunk_${this.chunkCounter++}.wav`);

        fs.writeFileSync(chunkFile, wavData);
        this.playbackQueue.push(chunkFile);

        console.log(`[${this.instanceId}] Created audio chunk: ${chunkFile} (${chunkSize} bytes)`);

        // Start playback if not already playing
        if (!this.currentlyPlaying) {
          this.playNextChunk();
        }
      }

      // Continue processing - check every 25ms to match chunk size
      setTimeout(processChunk, 25); // Check every 25ms (was 50ms)
    };

    processChunk();
  }

  /**
   * Play the next chunk in the queue
   */
  playNextChunk() {
    if (!this.afplayMode || this.playbackQueue.length === 0) return;

    const nextFile = this.playbackQueue.shift();
    this.currentlyPlaying = nextFile;

    console.log(`[${this.instanceId}] Playing chunk: ${nextFile}`);

    const afplayProcess = spawn("afplay", [nextFile], {
      stdio: "ignore",
      detached: false,
    });

    afplayProcess.on("exit", (code) => {
      console.log(`[${this.instanceId}] Chunk finished: ${nextFile}`);

      // Clean up the temporary file
      try {
        require("fs").unlinkSync(nextFile);
      } catch (err) {
        console.warn(`[${this.instanceId}] Failed to clean up ${nextFile}:`, err.message);
      }

      this.currentlyPlaying = null;

      // Play next chunk or signal completion
      if (this.playbackQueue.length > 0) {
        this.playNextChunk();
      } else if (this.ringBuffer.isFinished && this.ringBuffer.size === 0) {
        this.isPlaying = false;
        this.cleanupAfplayMode();
        this.emit("completed");
      } else {
        // Wait for more chunks
        setTimeout(() => this.playNextChunk(), 100);
      }
    });

    afplayProcess.on("error", (error) => {
      console.error(`[${this.instanceId}] afplay error:`, error.message);
      this.currentlyPlaying = null;
      this.emit("error", error);
    });
  }

  /**
   * Create WAV file data from PCM buffer
   */
  createWAVFromPCM(pcmData) {
    const sampleRate = this.format.sampleRate;
    const channels = this.format.channels;
    const bitDepth = this.format.bitDepth;
    const byteRate = sampleRate * channels * (bitDepth / 8);
    const blockAlign = channels * (bitDepth / 8);
    const dataSize = pcmData.length;
    const fileSize = 36 + dataSize;

    const header = Buffer.alloc(44);
    let offset = 0;

    // RIFF header
    header.write("RIFF", offset);
    offset += 4;
    header.writeUInt32LE(fileSize, offset);
    offset += 4;
    header.write("WAVE", offset);
    offset += 4;

    // fmt chunk
    header.write("fmt ", offset);
    offset += 4;
    header.writeUInt32LE(16, offset);
    offset += 4; // chunk size
    header.writeUInt16LE(1, offset);
    offset += 2; // PCM format
    header.writeUInt16LE(channels, offset);
    offset += 2;
    header.writeUInt32LE(sampleRate, offset);
    offset += 4;
    header.writeUInt32LE(byteRate, offset);
    offset += 4;
    header.writeUInt16LE(blockAlign, offset);
    offset += 2;
    header.writeUInt16LE(bitDepth, offset);
    offset += 2;

    // data chunk
    header.write("data", offset);
    offset += 4;
    header.writeUInt32LE(dataSize, offset);

    return Buffer.concat([header, pcmData]);
  }

  /**
   * Clean up afplay temporary files and directory
   */
  cleanupAfplayMode() {
    if (!this.tempDir) return;

    try {
      const fs = require("fs");

      // Clean up any remaining files
      if (fs.existsSync(this.tempDir)) {
        const files = fs.readdirSync(this.tempDir);
        for (const file of files) {
          try {
            const path = require("path");
            fs.unlinkSync(path.join(this.tempDir, file));
          } catch (err) {
            console.warn(`[${this.instanceId}] Failed to clean up ${file}:`, err.message);
          }
        }
        fs.rmdirSync(this.tempDir);
      }

      console.log(`[${this.instanceId}] Cleaned up afplay temp directory`);
    } catch (error) {
      console.warn(`[${this.instanceId}] afplay cleanup error:`, error.message);
    }

    this.afplayMode = false;
    this.tempDir = null;
  }

  async restartAudioProcess() {
    if (this.restartTimeout) {
      clearTimeout(this.restartTimeout);
    }

    const now = performance.now();
    const timeSinceLastRestart = now - this.lastRestartTime;

    // Reset restart attempts if enough time has passed
    if (timeSinceLastRestart > 30000) {
      // 30 seconds
      this.restartAttempts = 0;
    }

    this.restartAttempts++;

    if (this.restartAttempts > this.MAX_RESTARTS) {
      console.error(
        `[${this.instanceId}] Too many restart attempts (${this.restartAttempts}/${this.MAX_RESTARTS}); giving up`
      );
      this.emit("error", new Error("Audio process restart limit exceeded"));
      return;
    }

    // Only restart if we're still supposed to be playing and haven't stopped intentionally
    if (this.isPlaying && !this.isStopped) {
      const backoffDelay = Math.min(500 * Math.pow(2, this.restartAttempts - 1), 5000); // Exponential backoff, max 5s
      console.log(
        `[${this.instanceId}] Restarting audio process (attempt ${this.restartAttempts}/${this.MAX_RESTARTS}) in ${backoffDelay}ms`
      );

      this.restartTimeout = setTimeout(() => {
        this.lastRestartTime = Date.now();
        this.stop();
        setTimeout(async () => {
          await this.start();
        }, 100);
      }, backoffDelay);
    } else {
      console.log(
        `[${this.instanceId}] Not restarting audio process - playback stopped or completed`
      );
    }
  }

  /**
   * COMPLETELY REWRITTEN: Robust audio processing loop for long TTS sessions
   *
   * Key improvements:
   * 1. No arbitrary timeouts - only stops when explicitly told to
   * 2. Handles buffer gaps between segments gracefully
   * 3. Continues processing until ALL audio is complete
   * 4. Better error handling and recovery
   */
  processAudioLoop() {
    if (this._audioLoopInterval) {
      clearInterval(this._audioLoopInterval);
      this._audioLoopInterval = null;
    }
    if (this._audioLoopActive) {
      // Prevent re-entrancy
      return;
    }
    this._audioLoopActive = true;
    console.log(`[${this.instanceId}]  NEW ROBUST AUDIO LOOP STARTED`);

    // Record playback start time
    if (this.stats.playbackStartTime === 0) {
      this.stats.playbackStartTime = performance.now();
      console.log(
        `[${this.instanceId}] Playback start time recorded: ${this.stats.playbackStartTime.toFixed(2)}ms`
      );
      this.startProcessKeepAlive();
    }

    if (!this.audioProcess) {
      console.log(`[${this.instanceId}]  No audio process available`);
      this._audioLoopActive = false;
      return;
    }

    // Use 50ms chunks for smoother playback - smaller chunks cause more overhead
    // and can lead to micro-stutters due to processing delays
    const chunkSize = this.format.bytesPerSecond * 0.05; // 50ms chunks
    console.log(`[${this.instanceId}] Processing with chunk size: ${chunkSize} bytes (50ms)`);

    // NEW: Robust state tracking
    let consecutiveEmptyBuffers = 0;
    let lastChunkReceived = Date.now();
    let totalChunksProcessed = 0;
    let isWaitingForMoreData = false;

    // NEW: No arbitrary timeouts - only stop when explicitly told
    // Adjusted for 50ms chunks: 100 * 50ms = 5 seconds
    const MAX_CONSECUTIVE_EMPTY_BUFFERS = 100; // Allow up to 5 seconds of empty buffers (100 * 50ms)
    const MAX_WAIT_TIME_MS = 60000; // Wait up to 1 minute for new data before giving up

    const processChunk = () => {
      // NEW: Only stop if explicitly told to stop
      if (this.isStopped) {
        console.log(`[${this.instanceId}]  Explicitly stopped - ending audio loop`);
        this._audioLoopActive = false;
        return;
      }

      // NEW: Check if we should end stream (only when explicitly requested)
      // CRITICAL: Also check if audio process has finished playing
      if (this.isEndingStream && this.ringBuffer.size === 0) {
        // Buffer is drained - close stdin to signal end of data to sox
        if (this.audioProcess && 
            this.audioProcess.stdin && 
            !this.audioProcess.stdin.destroyed) {
          console.log(`[${this.instanceId}] Buffer drained, closing stdin to finish playback`);
          try {
            this.audioProcess.stdin.end();
          } catch (e) {
            console.log(`[${this.instanceId}] stdin.end() error (expected if already closed):`, e.message);
          }
        }
        
        // Check if audio process is still running
        const processStillRunning =
          this.audioProcess &&
          !this.audioProcess.killed &&
          this.audioProcess.exitCode === null;

        if (!processStillRunning) {
          // Process has finished - complete immediately
          console.log(
            `[${this.instanceId}]  End stream requested, buffer empty, and process finished - completing naturally`
          );
          this._completePlaybackSession();
          return;
        } else {
          // Buffer is empty but process is still running - wait for it to finish
          // The process exit handler will call _completePlaybackSession() when it exits
          console.log(
            `[${this.instanceId}]  End stream requested and buffer empty, but audio process still running - waiting for process to finish`
          );
          // Continue the loop to check again
        }
      }

      // NEW: Check if audio process is still alive
      if (!this.audioProcess || this.audioProcess.killed || this.audioProcess.exitCode !== null) {
        console.log(`[${this.instanceId}]  Audio process died, attempting recovery...`);
        if (this.ringBuffer.size > 0) {
          console.log(
            `[${this.instanceId}] Buffer has ${this.ringBuffer.size} bytes remaining, restarting process...`
          );
          this.restartAudioProcess();
          // Continue processing after restart
          setTimeout(processChunk, 100);
          return;
        } else {
          console.log(`[${this.instanceId}] Buffer empty and process dead, ending loop`);
          this._audioLoopActive = false;
          return;
        }
      }

      const available = this.ringBuffer.size;
      const utilization = available / this.ringBuffer.capacity;

      if (available >= chunkSize) {
        // NEW: Reset empty buffer counter when we have data
        consecutiveEmptyBuffers = 0;
        isWaitingForMoreData = false;

        // CRITICAL FIX: Check if process finished while ending stream
        if (this.isEndingStream) {
          const processFinished = !this.audioProcess || 
                                  this.audioProcess.killed || 
                                  this.audioProcess.exitCode !== null;
          
          if (processFinished) {
            // Process finished while ending stream - complete even if buffer has data
            // (buffer might have data that was buffered but not yet consumed)
            console.log(
              `[${this.instanceId}]  End stream requested, process finished, buffer has ${this.ringBuffer.size} bytes remaining - completing naturally`
            );
            this._completePlaybackSession();
            return;
          }
        }

        const chunk = this.ringBuffer.read(chunkSize);
        lastChunkReceived = Date.now();
        totalChunksProcessed++;

        // Process the chunk
        if (this.audioProcess && !this.audioProcess.killed && this.audioProcess.exitCode === null) {
          const writeResult = this.audioProcess.stdin.write(chunk, (err) => {
            if (err) {
              if (err.code === "EPIPE") {
                console.log(`[${this.instanceId}] Sox stdin pipe closed - sox process terminated`);
              } else {
                console.error(`[${this.instanceId}] stdin.write error:`, err);
              }
            }
          });

          if (!writeResult) {
            // Back-pressure detected - wait for drain
            this.audioProcess.stdin.once("drain", () => {
              setTimeout(processChunk, 10);
            });
            return;
          }
        }

        // Update statistics
        this.stats.bytesProcessed += chunk.length;
        this.stats.audioPosition += chunk.length;

        // CRITICAL FIX: Periodically check if process finished while ending stream
        // This handles cases where stdin.end() was called but process hasn't exited yet
        if (this.isEndingStream && totalChunksProcessed % 10 === 0) {
          const processFinished = !this.audioProcess || 
                                  this.audioProcess.killed || 
                                  this.audioProcess.exitCode !== null;
          
          if (processFinished) {
            // Process finished - check if we should complete
            const bufferLow = this.ringBuffer.size === 0 || this.ringBuffer.utilization < 0.01;
            if (bufferLow) {
              console.log(
                `[${this.instanceId}]  Process finished while ending stream, buffer low (${this.ringBuffer.size} bytes) - completing naturally`
              );
              this._completePlaybackSession();
              return;
            }
          }
        }

        // Use minimal delay for continuous playback - the key to avoiding stutters
        // is to keep the sox stdin fed as fast as possible. Sox has its own internal
        // buffering so we don't need to throttle on our side.
        const nextDelay = 1; // Minimal delay - let back-pressure handle flow control

        // Continue processing
        setTimeout(processChunk, nextDelay);
      } else {
        // Buffer empty or low - this is normal between segments
        consecutiveEmptyBuffers++;

        // CRITICAL FIX: If we're ending stream and buffer is empty/low AND process finished, complete
        if (this.isEndingStream) {
          const processFinished = !this.audioProcess || 
                                  this.audioProcess.killed || 
                                  this.audioProcess.exitCode !== null;
          
          // If buffer is empty or very low (< 1% utilization) and process finished, complete
          const bufferLow = this.ringBuffer.size === 0 || this.ringBuffer.utilization < 0.01;
          
          if (bufferLow && processFinished) {
            console.log(
              `[${this.instanceId}]  End stream requested, buffer empty/low (${this.ringBuffer.size} bytes, ${(this.ringBuffer.utilization * 100).toFixed(1)}%), and process finished - completing naturally`
            );
            this._completePlaybackSession();
            return;
          } else if (bufferLow && !processFinished) {
            // Buffer empty/low but process still running - log and continue waiting
            if (consecutiveEmptyBuffers % 10 === 0) {
              console.log(
                `[${this.instanceId}]  End stream requested, buffer empty/low (${this.ringBuffer.size} bytes), but audio process still running - waiting for process to finish`
              );
            }
          }
        }

        if (!isWaitingForMoreData) {
          console.log(
            `[${this.instanceId}] ⏳ Buffer empty (${consecutiveEmptyBuffers}/${MAX_CONSECUTIVE_EMPTY_BUFFERS}) - waiting for more data...`
          );
          isWaitingForMoreData = true;
        }

        // NEW: Only give up if we've waited too long with no data
        if (consecutiveEmptyBuffers > MAX_CONSECUTIVE_EMPTY_BUFFERS) {
          const timeSinceLastChunk = Date.now() - lastChunkReceived;
          if (timeSinceLastChunk > MAX_WAIT_TIME_MS) {
            console.log(
              `[${this.instanceId}]  No new data for ${timeSinceLastChunk}ms - ending audio loop`
            );
            this._audioLoopActive = false;
            return;
          }
        }

        // Continue waiting for more data with short fixed delay
        // Avoid exponential backoff as it can cause noticeable stuttering
        // when new data arrives after the delay has grown
        const waitDelay = 10; // Fixed 10ms - fast enough to catch new data without busy-waiting
        setTimeout(processChunk, waitDelay);
      }
    };

    // Start the robust processing loop
    processChunk();
  }

  /**
   * Helper method to complete playback session with proper timing calculation
   */
  _completePlaybackSession() {
    console.log(`[${this.instanceId}] _completePlaybackSession() called`, {
      _completionEmitted: this._completionEmitted,
      isEndingStream: this.isEndingStream,
      bufferSize: this.ringBuffer.size,
      processExitCode: this.audioProcess?.exitCode,
      processKilled: this.audioProcess?.killed,
    });

    // CRITICAL FIX: Prevent double completion - check if already completed
    if (this._completionEmitted) {
      console.log(
        `[${this.instanceId}]  Completion already emitted - skipping duplicate completion`
      );
      return;
    }

    if (this.stats.playbackStartTime > 0 && this.stats.playbackEndTime === 0) {
      this.stats.playbackEndTime = performance.now();
      this.stats.actualDuration = this.stats.playbackEndTime - this.stats.playbackStartTime;

      console.log(`[${this.instanceId}]  Playback session completed:`, {
        startTime: this.stats.playbackStartTime.toFixed(2) + "ms",
        endTime: this.stats.playbackEndTime.toFixed(2) + "ms",
        actualDuration: this.stats.actualDuration.toFixed(2) + "ms",
        expectedDuration: this.stats.expectedDuration.toFixed(2) + "ms",
        difference: (this.stats.actualDuration - this.stats.expectedDuration).toFixed(2) + "ms",
        totalBytesProcessed: this.stats.bytesProcessed,
        totalChunks: this.stats.totalChunksReceived,
      });
    }

    // Mark as completed to prevent double emission
    this._completionEmitted = true;

    // Emit completed event
    console.log(`[${this.instanceId}] Emitting 'completed' event`, {
      listenerCount: this.listenerCount("completed"),
      timestamp: Date.now(),
    });
    this.emit("completed");
    console.log(`[${this.instanceId}] 'completed' event emitted successfully`);

    // Clear completion timeout if it exists
    if (this._endStreamTimeout) {
      clearTimeout(this._endStreamTimeout);
      this._endStreamTimeout = null;
    }

    // Reset flags
    this.isEndingStream = false;
    this.ringBuffer.clear();
    this._audioLoopActive = false;
    // Note: _completionEmitted is reset in start() for new sessions
  }

  // Memory usage logging
  startMemoryLogging() {
    if (this._memoryLogInterval) return;
    this._memoryLogInterval = setInterval(() => {
      const mem = process.memoryUsage();
      console.log(`[${this.instanceId}] Memory usage:`, (mem.rss / 1024 / 1024).toFixed(1), "MB");
    }, 5000);
  }

  // Note: Current implementation uses sox/ffplay with afplay fallback for reliable cross-platform audio
  // Note: Client backpressure signaling is implemented via handleFlowControl() method

  /**
   * Calculate expected duration based on audio format and data size
   * Improved timing calculation with better accuracy
   */
  calculateExpectedDuration(totalBytes) {
    // Duration = (bytes) / (bytes per second)
    const durationSeconds = totalBytes / this.format.bytesPerSecond;
    const durationMs = durationSeconds * 1000;

    // Add small buffer for processing overhead (typically 10-50ms)
    const processingBuffer = Math.min(durationMs * 0.01, 50); // 1% or 50ms max
    const adjustedDurationMs = durationMs + processingBuffer;

    debugLog(`[${this.instanceId}] Duration calculation:`, {
      totalBytes,
      bytesPerSecond: this.format.bytesPerSecond,
      durationSeconds: durationSeconds.toFixed(3),
      durationMs: durationMs.toFixed(1),
      processingBuffer: processingBuffer.toFixed(1),
      adjustedDurationMs: adjustedDurationMs.toFixed(1),
    });

    return adjustedDurationMs;
  }

  /**
   * Set the total audio duration based on bytes received
   */
  setAudioDuration(totalBytes) {
    this.totalAudioBytes = totalBytes;
    this.audioDurationMs = this.calculateExpectedDuration(totalBytes);

    debugLog(`[${this.instanceId}] Audio duration set:`, {
      totalBytes: this.totalAudioBytes,
      durationMs: this.audioDurationMs.toFixed(1),
      expectedDuration: (this.audioDurationMs / 1000).toFixed(3) + "s",
    });
  }

  /**
   * Start the keep-alive timer for the audio process
   */
  startProcessKeepAlive() {
    if (this.processKeepAliveTimer) {
      clearTimeout(this.processKeepAliveTimer);
    }

    if (this.audioDurationMs <= 0) {
      console.log(`[${this.instanceId}] No audio duration set, skipping keep-alive timer`);
      return;
    }

    this.processStartTime = performance.now();

    // FIXED: Use a much longer keep-alive duration to accommodate TTS generation time
    // The previous logic was too aggressive and cut off audio during long TTS generation
    // TTS generation can take 10+ seconds, so we need a generous buffer
    const keepAliveDuration = Math.max(
      this.audioDurationMs * 5, // 5x audio duration as minimum
      30000 // At least 30 seconds for TTS generation
    );

    console.log(
      `[${this.instanceId}] Starting process keep-alive timer for ${keepAliveDuration.toFixed(1)}ms (TTS generation buffer: ${(keepAliveDuration - this.audioDurationMs).toFixed(1)}ms)`
    );

    this.processKeepAliveTimer = setTimeout(() => {
      console.log(
        `[${this.instanceId}] Keep-alive timer expired, checking if process should be terminated`
      );
      this.checkProcessTermination();
    }, keepAliveDuration);
  }

  /**
   * Check if the process should be terminated based on duration
   */
  checkProcessTermination() {
    if (!this.audioProcess || this.audioProcess.killed || this.audioProcess.exitCode !== null) {
      console.log(`[${this.instanceId}] Process already terminated, no action needed`);
      return;
    }

    const elapsedTime = performance.now() - this.processStartTime;
    const expectedEndTime = this.audioDurationMs;
    const idleSinceLastChunk =
      this.stats.lastChunkTime > 0 ? performance.now() - this.stats.lastChunkTime : 0;
    const IDLE_GRACE_MS = 8000; // Allow idle gaps between segments without killing the process

    console.log(`[${this.instanceId}] Process termination check:`, {
      elapsedTime: elapsedTime.toFixed(1) + "ms",
      expectedEndTime: expectedEndTime.toFixed(1) + "ms",
      remainingBuffer: this.ringBuffer.size + " bytes",
      idleSinceLastChunk: idleSinceLastChunk.toFixed(1) + "ms",
      isEndingStream: this.isEndingStream,
    });

    // Revised termination policy:
    // 1) Prefer explicit end_stream signal to terminate
    // 2) Otherwise, only terminate after a generous idle grace window with empty buffer
    // 3) Keep legacy hard cap at 3x expected duration, but still require idle grace

    const bufferEmpty = this.ringBuffer.size === 0;

    if (this.isEndingStream && elapsedTime >= expectedEndTime && bufferEmpty) {
      console.log(
        `[${this.instanceId}] Terminating after end_stream and expected duration (buffer empty)`
      );
      this.terminateProcessGracefully();
    } else if (
      elapsedTime >= expectedEndTime * 3 &&
      idleSinceLastChunk > IDLE_GRACE_MS &&
      bufferEmpty
    ) {
      console.log(
        `[${this.instanceId}] Force terminating after prolonged idle beyond 3x expected duration`
      );
      this.terminateProcessGracefully();
    } else if (idleSinceLastChunk <= IDLE_GRACE_MS || !bufferEmpty) {
      console.log(
        `[${this.instanceId}] Process should continue running (awaiting next segment or buffered audio present)`
      );
    } else {
      console.log(
        `[${this.instanceId}] Idle grace exceeded but below 3x duration; keeping process alive until end_stream`
      );
    }
  }

  /**
   * Terminate the audio process gracefully
   */
  terminateProcessGracefully() {
    if (!this.audioProcess || this.audioProcess.killed || this.audioProcess.exitCode !== null) {
      return;
    }

    console.log(`[${this.instanceId}] Gracefully terminating audio process`);

    // Close stdin to signal end of input
    if (this.audioProcess.stdin) {
      this.audioProcess.stdin.end();
    }

    // Give the process a moment to finish, then force kill if needed
    setTimeout(() => {
      if (this.audioProcess && !this.audioProcess.killed && this.audioProcess.exitCode === null) {
        console.log(`[${this.instanceId}] Force killing audio process`);
        this.audioProcess.kill("SIGTERM");
      }
    }, 1000);
  }

  /**
   * Write audio chunk to buffer
   * Enhanced with better timing tracking and accuracy measurement
   */
  async writeChunk(chunk) {
    // Dump PCM chunk to file for manual testing
    const fs = await import("fs");
    fs.appendFileSync("/tmp/test.raw", chunk);

    const chunkTime = performance.now();
    const written = this.ringBuffer.write(chunk);

    // Track timing metrics
    if (this.stats.firstChunkTime === 0) {
      this.stats.firstChunkTime = chunkTime;

      // Auto-start playback when first chunk arrives
      if (!this.isPlaying) {
        console.log(`[${this.instanceId}]  Auto-starting playback on first chunk`);
        await this.start();
      }
    }
    this.stats.lastChunkTime = chunkTime;
    this.stats.totalChunksReceived++;
    this.stats.chunksReceived++;

    // Calculate average chunk size
    this.stats.averageChunkSize = this.stats.bytesProcessed / this.stats.totalChunksReceived;

    debugLog(
      `[${this.instanceId}] writeChunk: wrote ${written} bytes, buffer size: ${this.ringBuffer.size}, chunk #${this.stats.totalChunksReceived}`
    );

    // Update expected duration based on total bytes received
    this.stats.bytesProcessed += written;
    this.stats.expectedDuration = this.calculateExpectedDuration(this.stats.bytesProcessed);

    // Track total audio bytes and set duration for process management
    this.totalAudioBytes += written;
    this.setAudioDuration(this.totalAudioBytes);

    this.emit("chunkReceived", {
      bufferUtilization: this.ringBuffer.utilization,
      audioPosition: this.stats.audioPosition,
      expectedDuration: this.stats.expectedDuration,
      timingMetrics: {
        firstChunkTime: this.stats.firstChunkTime,
        lastChunkTime: this.stats.lastChunkTime,
        totalChunksReceived: this.stats.totalChunksReceived,
        averageChunkSize: this.stats.averageChunkSize,
      },
    });
    return written;
  }

  /**
   * Pause playback
   */
  pause() {
    if (!this.isPaused) {
      this.isPaused = true;
      console.log(`[${this.instanceId}] Flow control: PAUSED playback`);
    }
  }

  /**
   * Resume playback
   */
  resume() {
    if (this.isPaused) {
      this.isPaused = false;
      console.log(`[${this.instanceId}] Flow control: RESUMED playback`);
    }
  }

  /**
   * Stop playback
   */
  stop() {
    this.isPlaying = false;
    this.isPaused = false;
    this.isStopped = true;
    this.isStopping = true; // Set flag to indicate stopping

    // Clear the keep-alive timer
    if (this.processKeepAliveTimer) {
      clearTimeout(this.processKeepAliveTimer);
      this.processKeepAliveTimer = null;
      console.log(`[${this.instanceId}] Cleared process keep-alive timer`);
    }

    if (this.audioProcess && !this.audioProcess.killed) {
      this.audioProcess.kill("SIGTERM");
    }

    // Don't clear the buffer immediately - let the processing loop drain it
    // this.ringBuffer.clear();
    this.emit("stopped");
  }

  /**
   * Get current status
   */
  getStatus() {
    return {
      isPlaying: this.isPlaying,
      isPaused: this.isPaused,
      bufferUtilization: this.ringBuffer.utilization,
      stats: this.stats,
      lastHeartbeat: this.lastHeartbeat,
      timing: {
        expectedDuration: this.stats.expectedDuration,
        actualDuration: this.stats.actualDuration,
        playbackStartTime: this.stats.playbackStartTime,
        playbackEndTime: this.stats.playbackEndTime,
        accuracy: this.stats.timingAccuracy.toFixed(1) + "%",
        processingOverhead: this.stats.processingOverhead.toFixed(2) + "ms",
        totalChunks: this.stats.totalChunksReceived,
        averageChunkSize: this.stats.averageChunkSize.toFixed(0) + " bytes",
        firstChunkTime: this.stats.firstChunkTime,
        lastChunkTime: this.stats.lastChunkTime,
      },
    };
  }

  /**
   * Get detailed timing analysis
   */
  getTimingAnalysis() {
    const analysis = {
      basic: {
        expectedDuration: this.stats.expectedDuration,
        actualDuration: this.stats.actualDuration,
        accuracy: this.stats.timingAccuracy,
        processingOverhead: this.stats.processingOverhead,
      },
      chunkAnalysis: {
        totalChunks: this.stats.totalChunksReceived,
        averageChunkSize: this.stats.averageChunkSize,
        firstChunkTime: this.stats.firstChunkTime,
        lastChunkTime: this.stats.lastChunkTime,
        chunkDeliveryTime: this.stats.lastChunkTime - this.stats.firstChunkTime,
      },
      playbackAnalysis: {
        playbackStartTime: this.stats.playbackStartTime,
        playbackEndTime: this.stats.playbackEndTime,
        playbackDuration: this.stats.actualDuration,
        bufferUtilization: this.ringBuffer.utilization,
        underruns: this.stats.underruns,
      },
      performance: {
        bytesPerSecond: this.format.bytesPerSecond,
        totalBytesProcessed: this.stats.bytesProcessed,
        bufferCapacity: this.ringBuffer.capacity,
        bufferSize: this.ringBuffer.size,
      },
    };

    // Calculate additional metrics
    if (analysis.chunkAnalysis.totalChunks > 0) {
      analysis.chunkAnalysis.averageChunkDeliveryTime =
        analysis.chunkAnalysis.chunkDeliveryTime / analysis.chunkAnalysis.totalChunks;
    }

    if (analysis.basic.actualDuration > 0) {
      analysis.performance.effectiveBytesPerSecond =
        analysis.performance.totalBytesProcessed / (analysis.basic.actualDuration / 1000);
    }

    return analysis;
  }
}

/**
 * Audio Daemon Server with instance ID
 */
class AudioDaemon extends EventEmitter {
  constructor(port = 8081) {
    super();
    this.instanceId = this.constructor.name + "_" + Date.now();
    this.port = port;
    this.server = null;
    this.wss = null;
    this.audioProcessor = null;
    this.clients = new Set();
    this.heartbeatInterval = null;
    this.lastHeartbeatLog = 0;

    // Parse command line arguments
    this.parseArgs();
  }

  /**
   * Parse command line arguments
   */
  parseArgs() {
    const args = process.argv.slice(2);
    this.config = {
      port: 8081,
      format: "pcm",
      sampleRate: 24000,
      channels: 1,
      bitDepth: 16,
    };

    for (let i = 0; i < args.length; i += 2) {
      const key = args[i];
      const value = args[i + 1];

      switch (key) {
        case "--port":
          this.config.port = parseInt(value);
          break;
        case "--format":
          this.config.format = value;
          break;
        case "--sample-rate":
          this.config.sampleRate = parseInt(value);
          break;
        case "--channels":
          this.config.channels = parseInt(value);
          break;
        case "--bit-depth":
          this.config.bitDepth = parseInt(value);
          break;
      }
    }
  }

  /**
   * Start the daemon
   */
  start() {
    console.log(`[${this.instanceId}] Starting Audio Daemon on port:`, this.config.port);
    console.log(`[${this.instanceId}] Audio format:`, this.config);

    // Create HTTP server with health endpoint
    this.server = http.createServer((req, res) => {
      if (req.url === "/health") {
        // Health check endpoint
        const health = {
          status: "healthy",
          timestamp: Date.now(),
          uptime: process.uptime(),
          version: "2.0.0",
          audioProcessor: this.audioProcessor
            ? {
                isPlaying: this.audioProcessor.isPlaying,
                isPaused: this.audioProcessor.isPaused,
                bufferUtilization: this.audioProcessor.ringBuffer?.utilization || 0,
                ringBuffer: this.audioProcessor.ringBuffer
                  ? {
                      size: this.audioProcessor.ringBuffer.size,
                      capacity: this.audioProcessor.ringBuffer.capacity,
                      utilization: this.audioProcessor.ringBuffer.utilization,
                      isFinished: this.audioProcessor.ringBuffer.isFinished,
                    }
                  : null,
                audioContext: this.audioProcessor.audioContext ? true : false,
                stats: this.audioProcessor.stats,
                performance: this.audioProcessor.getStatus(),
                timingAnalysis: this.audioProcessor.getTimingAnalysis(),
              }
            : null,
          clients: this.clients.size,
        };

        res.writeHead(200, {
          "Content-Type": "application/json",
          "X-Daemon-Version": "2.0.0",
        });
        res.end(JSON.stringify(health, null, 2));
      } else {
        // Default response
        res.writeHead(200, { "Content-Type": "text/plain" });
        res.end("Audio Daemon Running\n");
      }
    });

    // Create WebSocket server
    this.wss = new WebSocketServer({ server: this.server });

    // Initialize audio processor
    const format = new AudioFormat(
      this.config.format,
      this.config.sampleRate,
      this.config.channels,
      this.config.bitDepth
    );

    this.audioProcessor = new AudioProcessor(format);

    // Set up WebSocket event handlers
    this.wss.on("connection", (ws) => {
      console.log("Client connected");
      this.clients.add(ws);

      // Send initial status
      ws.send(
        JSON.stringify({
          type: "status",
          timestamp: Date.now(),
          data: {
            state: "idle",
            bufferUtilization: 0,
            audioPosition: 0,
            performance: this.audioProcessor.getStatus(),
          },
        })
      );

      // Handle incoming messages
      ws.on("message", (message) => {
        // console.log(
        //   `[${this.instanceId}] Raw message received:`,
        //   message.toString().substring(0, 200)
        // );
        try {
          const data = JSON.parse(message);
          // console.log(`[${this.instanceId}] Parsed message type:`, data.type);
          this.handleMessage(ws, data);
        } catch (error) {
          console.error(`[${this.instanceId}] Failed to parse message:`, error.message);
        }
      });

      // Handle client disconnect
      ws.on("close", () => {
        console.log("Client disconnected");
        this.clients.delete(ws);
      });

      ws.on("error", (error) => {
        console.error("WebSocket error:", error.message);
        this.clients.delete(ws);
      });
    });

    // Set up audio processor event handlers with throttled status updates
    let lastStatusUpdate = 0;
    const STATUS_UPDATE_INTERVAL = 2000; // Only send status updates every 2 seconds

    this.audioProcessor.on("chunkReceived", (data) => {
      const now = Date.now();
      if (now - lastStatusUpdate >= STATUS_UPDATE_INTERVAL) {
        this.broadcast({
          type: "status",
          timestamp: now,
          data: {
            state: this.audioProcessor.isPlaying ? "playing" : "idle",
            bufferUtilization: data.bufferUtilization,
            audioPosition: this.audioProcessor.stats.audioPosition,
            performance: this.audioProcessor.getStatus(),
          },
        });
        lastStatusUpdate = now;
      }
    });

    this.audioProcessor.on("error", (error) => {
      console.error("Audio processor error:", error.message);
      this.broadcast({
        type: "error",
        timestamp: Date.now(),
        data: { message: error.message },
      });
    });

    // CRITICAL FIX: Forward AudioProcessor "completed" event to WebSocket clients
    this.audioProcessor.on("completed", () => {
      console.log(`[${this.instanceId}] Audio processing completed - broadcasting to clients`, {
        clientCount: this.clients?.size || 0,
        timestamp: Date.now(),
      });
      const completedMessage = {
        type: "completed",
        timestamp: Date.now(),
        data: {
          state: "completed",
          bufferUtilization: 0,
          audioPosition: this.audioProcessor.stats.audioPosition,
          performance: this.audioProcessor.getStatus(),
        },
      };
      console.log(`[${this.instanceId}] Broadcasting completed message:`, JSON.stringify(completedMessage).substring(0, 200));
      this.broadcast(completedMessage);
      console.log(`[${this.instanceId}] Completed message broadcasted to ${this.clients?.size || 0} clients`);
    });

    // Start heartbeat
    this.startHeartbeat();

    // Start server
    this.server.listen(this.config.port, () => {
      console.log(`Audio Daemon listening on port ${this.config.port}`);
      this.emit("started");
    });
  }

  /**
   * Handle incoming WebSocket messages
   */
  handleMessage(ws, message) {
    // Debounce heartbeat logging to reduce spam
    if (message.type === "heartbeat") {
      const now = Date.now();
      if (!this.lastHeartbeatLog || now - this.lastHeartbeatLog > 30000) {
        console.log("Received message: heartbeat (debounced - logging every 30s)");
        this.lastHeartbeatLog = now;
      }
    } else {
      console.log("Received message:", message.type);
    }
    switch (message.type) {
      case "start":
        this.handleStart(ws, message);
        break;
      case "stop":
        this.handleStop(ws, message);
        break;
      case "pause":
        this.handlePause(ws, message);
        break;
      case "resume":
        this.handleResume(ws, message);
        break;
      case "audio_chunk":
        this.handleAudioChunk(ws, message);
        break;
      case "status":
        this.handleStatus(ws, message);
        break;
      case "flow_control":
        this.handleFlowControl(ws, message);
        break;
      case "end_stream":
        this.handleEndStream();
        break;
      case "control":
        this.handleControl(message.data);
        break;
      case "heartbeat":
        this.handleHeartbeat(ws);
        break;
      case "timing_analysis":
        this.handleTimingAnalysis(ws);
        break;
      default:
        console.error(`[${this.instanceId}] Unknown message type:`, message.type);
    }
  }

  /**
   * Handle audio chunk message
   */
  handleAudioChunk(_ws, message) {
    // console.log(`[${this.instanceId}] Received audio_chunk message`);

    if (!this.audioProcessor) {
      console.error(`[${this.instanceId}] Audio processor not initialized`);
      return;
    }

    let chunkData = message.data.chunk;

    // Accept base64 string
    if (typeof chunkData === "string") {
      chunkData = Buffer.from(chunkData, "base64");
    } else if (chunkData instanceof Buffer) {
      // already a Buffer
    } else if (chunkData && chunkData.type === "Buffer" && Array.isArray(chunkData.data)) {
      chunkData = Buffer.from(chunkData.data);
    } else if (typeof chunkData === "object" && chunkData !== null) {
      // Accept plain object with numeric keys
      const keys = Object.keys(chunkData);
      const numeric = keys.every((k) => /^\d+$/.test(k));
      if (numeric) {
        chunkData = Buffer.from(Object.values(chunkData));
        // console.log(
        //   `[${this.instanceId}] Converted numeric-key object chunk to Buffer:`,
        //   chunkData.length,
        //   "bytes"
        // );
      } else {
        console.error(`[${this.instanceId}] Unrecognized object format:`, chunkData);
        return;
      }
    } else {
      console.error(`[${this.instanceId}] Invalid chunk data format:`, typeof chunkData);
      return;
    }

    try {
      // console.log(
      //   `[${this.instanceId}] Writing chunk to audio processor:`,
      //   chunkData.length,
      //   "bytes"
      // );
      if (this.audioProcessor && typeof this.audioProcessor.writeChunk === "function") {
        this.audioProcessor.writeChunk(chunkData);
        debugLog(`[${this.instanceId}] Chunk written successfully`);
      } else {
        console.log(
          `[${this.instanceId}] Audio processor not initialized, emitting audioChunk event`
        );
        this.emit("audioChunk", chunkData);
      }
    } catch (error) {
      console.error(`[${this.instanceId}] Error writing chunk:`, error);
    }
  }

  /**
   * Handle end stream message
   */
  handleEndStream() {
    if (!this.audioProcessor) return;

    console.log("End stream received, stopping audio processor");

    // Mark ring buffer as finished for afplay mode
    if (this.audioProcessor.afplayMode) {
      this.audioProcessor.ringBuffer.markFinished();
      console.log(`[${this.instanceId}] Marked ring buffer as finished for afplay mode`);
    } else {
      this.audioProcessor.stop();
    }
  }

  /**
   * Handle control message
   */
  async handleControl(data) {
    if (!this.audioProcessor) return;

    switch (data.action) {
      case "play":
        await this.audioProcessor.start();
        break;

      case "pause":
        this.audioProcessor.pause();
        break;

      case "resume":
        this.audioProcessor.resume();
        break;

      case "stop":
        this.audioProcessor.stop();
        break;

      case "end_stream":
        // Mark that we're ending the stream - the audio loop will close stdin
        // once the buffer is fully drained to sox
        console.log(`[${this.instanceId}] End stream requested - audio loop will drain buffer first`, {
          bufferSize: this.audioProcessor.ringBuffer.size,
          processExitCode: this.audioProcessor.audioProcess?.exitCode,
          processKilled: this.audioProcessor.audioProcess?.killed,
          isPlaying: this.audioProcessor.isPlaying,
          expectedDuration: this.audioProcessor.audioDurationMs,
        });
        this.audioProcessor.isEndingStream = true;
        
        // NOTE: Do NOT close stdin here - let the audio loop drain the buffer first
        // The audio loop will close stdin when buffer is empty (see processChunk)
        
        // CRITICAL FIX: Set up timeout-based completion check
        // If process doesn't exit naturally within expected duration + buffer, complete anyway
        // Use audioDurationMs if available, otherwise fall back to stats.expectedDuration
        const expectedDuration = this.audioProcessor.audioDurationMs || 
                                 this.audioProcessor.stats.expectedDuration || 
                                 0;
        const bufferDuration = this.audioProcessor.ringBuffer.size > 0
          ? (this.audioProcessor.ringBuffer.size / this.audioProcessor.format.bytesPerSecond) * 1000
          : 0;
        
        // Use a more aggressive timeout: expected duration + buffer + 1s safety margin
        // This ensures we complete before the client timeout (which is typically 2x duration + 10s)
        const completionTimeout = Math.max(
          expectedDuration + bufferDuration + 1000, // Expected duration + buffer + 1s safety margin
          Math.min(expectedDuration * 1.5 + 2000, 12000) // Cap at 12s to ensure we beat client timeout
        );
        
        console.log(`[${this.instanceId}] Setting completion timeout: ${completionTimeout.toFixed(0)}ms (expected: ${expectedDuration.toFixed(0)}ms, buffer: ${bufferDuration.toFixed(0)}ms, audioDurationMs: ${this.audioProcessor.audioDurationMs?.toFixed(0) || 'N/A'}, statsExpected: ${this.audioProcessor.stats.expectedDuration?.toFixed(0) || 'N/A'})`);
        
        // Clear any existing timeout
        if (this.audioProcessor._endStreamTimeout) {
          clearTimeout(this.audioProcessor._endStreamTimeout);
          console.log(`[${this.instanceId}] Cleared existing end stream timeout`);
        }
        
        // Set timeout to force completion if process doesn't exit naturally
        this.audioProcessor._endStreamTimeout = setTimeout(() => {
          console.log(`[${this.instanceId}] Completion timeout callback fired`, {
            isEndingStream: this.audioProcessor.isEndingStream,
            completionEmitted: this.audioProcessor._completionEmitted,
            bufferSize: this.audioProcessor.ringBuffer.size,
            processExitCode: this.audioProcessor.audioProcess?.exitCode,
          });
          if (this.audioProcessor.isEndingStream && !this.audioProcessor._completionEmitted) {
            console.log(
              `[${this.instanceId}] Completion timeout reached (${completionTimeout.toFixed(0)}ms) - forcing completion (process may still be running)`
            );
            this.audioProcessor._completePlaybackSession();
          } else {
            console.log(
              `[${this.instanceId}] Completion timeout reached but conditions not met - isEndingStream: ${this.audioProcessor.isEndingStream}, completionEmitted: ${this.audioProcessor._completionEmitted}`
            );
          }
        }, completionTimeout);
        
        console.log(`[${this.instanceId}] Completion timeout scheduled for ${completionTimeout.toFixed(0)}ms from now`);
        
        // CRITICAL FIX: Check buffer AND process state immediately
        const bufferEmpty = this.audioProcessor.ringBuffer.size === 0;
        const processFinished = !this.audioProcessor.audioProcess || 
                                this.audioProcessor.audioProcess.killed || 
                                this.audioProcessor.audioProcess.exitCode !== null;
        
        if (bufferEmpty && processFinished) {
          // Buffer empty AND process finished - complete immediately
          console.log(
            `[${this.instanceId}] Buffer empty and process finished when end_stream received - completing immediately`
          );
          if (this.audioProcessor._endStreamTimeout) {
            clearTimeout(this.audioProcessor._endStreamTimeout);
            this.audioProcessor._endStreamTimeout = null;
          }
          this.audioProcessor._completePlaybackSession();
        } else if (bufferEmpty && !processFinished) {
          // Buffer empty but process still running - wait for process exit
          console.log(
            `[${this.instanceId}] Buffer empty but process still running when end_stream received - will complete when process exits or timeout`
          );
          // Process exit handler will call _completePlaybackSession()
        } else {
          // Buffer not empty - wait for buffer to empty and process to finish
          console.log(
            `[${this.instanceId}] Buffer has ${this.audioProcessor.ringBuffer.size} bytes - will complete when empty and process finishes, or timeout in ${completionTimeout.toFixed(0)}ms`
          );
          // Process loop will check and complete when buffer empties or process finishes
        }
        break;

      case "configure":
        console.log("Configuration received:", data.params);
        break;

      default:
        console.warn("Unknown control action:", data.action);
    }

    // Broadcast status update
    this.broadcast({
      type: "status",
      timestamp: Date.now(),
      data: {
        state: this.audioProcessor.isPlaying ? "playing" : "idle",
        bufferUtilization: this.audioProcessor.ringBuffer.utilization,
        audioPosition: this.audioProcessor.stats.audioPosition,
        performance: this.audioProcessor.getStatus(),
      },
    });
  }

  /**
   * Handle heartbeat message
   */
  handleHeartbeat(ws) {
    this.audioProcessor.lastHeartbeat = Date.now();

    ws.send(
      JSON.stringify({
        type: "heartbeat",
        timestamp: Date.now(),
        data: { status: "ok" },
      })
    );
  }

  /**
   * Handle timing analysis request
   */
  handleTimingAnalysis(ws) {
    if (!this.audioProcessor) {
      ws.send(
        JSON.stringify({
          type: "error",
          timestamp: Date.now(),
          data: { message: "Audio processor not available" },
        })
      );
      return;
    }

    const analysis = this.audioProcessor.getTimingAnalysis();

    ws.send(
      JSON.stringify({
        type: "timing_analysis",
        timestamp: Date.now(),
        data: analysis,
      })
    );
  }

  /**
   * Handle flow control message
   */
  async handleFlowControl(_ws, message) {
    if (!this.audioProcessor) return;

    const data = message.data;
    const newPauseState = data.pause;
    const currentUtilization = this.audioProcessor.ringBuffer.utilization;

    console.log(
      `[${this.instanceId}] Received flow_control message: pause=${newPauseState}, currentUtilization=${(currentUtilization * 100).toFixed(1)}%`
    );

    if (newPauseState !== this.audioProcessor.isPaused) {
      if (newPauseState) {
        console.log(`[${this.instanceId}] Pausing audio playback due to flow control.`);
        this.audioProcessor.pause();
      } else {
        console.log(`[${this.instanceId}] Resuming audio playback due to flow control.`);
        this.audioProcessor.resume();
      }
    }
  }

  /**
   * Broadcast message to all clients
   */
  broadcast(message) {
    const messageStr = JSON.stringify(message);
    this.clients.forEach((client) => {
      if (client.readyState === WebSocket.OPEN) {
        client.send(messageStr);
      }
    });
  }

  /**
   * Start heartbeat monitoring
   */
  startHeartbeat() {
    this.heartbeatInterval = setInterval(() => {
      this.broadcast({
        type: "heartbeat",
        timestamp: Date.now(),
        data: { status: "ok" },
      });
    }, 10000); // Reduced from 1000ms to 10000ms (10 seconds) to reduce log noise
  }

  /**
   * Stop the daemon
   */
  stop() {
    console.log("Stopping Audio Daemon");

    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
    }

    if (this.audioProcessor) {
      this.audioProcessor.stop();
    }

    if (this.wss) {
      this.wss.close();
    }

    if (this.server) {
      this.server.close();
    }

    this.emit("stopped");
  }
}

// Handle process signals
process.on("SIGINT", () => {
  console.log("Received SIGINT, shutting down...");
  if (global.daemon) {
    global.daemon.stop();
  }
  process.exit(0);
});

process.on("SIGTERM", () => {
  console.log("Received SIGTERM, shutting down...");
  if (global.daemon) {
    global.daemon.stop();
  }
  process.exit(0);
});

// Start the daemon
if (import.meta.url === `file://${process.argv[1]}` || import.meta.url === process.argv[1]) {
  const daemon = new AudioDaemon();
  global.daemon = daemon;

  daemon.on("started", () => {
    console.log("Audio Daemon started successfully");
  });

  daemon.on("stopped", () => {
    console.log("Audio Daemon stopped");
    process.exit(0);
  });

  daemon.start();
}

export { AudioDaemon, AudioProcessor, AudioFormat, AudioRingBuffer };
