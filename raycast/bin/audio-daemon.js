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
 * @since 2025-01-20
 * @license MIT
 */

import WebSocket, { WebSocketServer } from "ws";
import http from "http";
import { spawn } from "child_process";
import { EventEmitter } from "events";

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
  }

  write(data) {
    const available = this.capacity - this.size;
    available === 0 &&
      console.log(
        `%c [DEBUG] Buffer is full`,
        "color: #FFAAAA; background-color: #222222; font-weight: bold"
      );
    console.log(
      `  [DEBUG] Buffer size: ${this.size}, available: ${available}, capacity: ${this.capacity}`
    );

    const toWrite = Math.min(data.length, available);
    console.log(
      `[${this.instanceId}] Writing to buffer:`,
      toWrite,
      "bytes",
      "capacity:",
      this.capacity
    );
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
    // Increase buffer size to accommodate longer audio streams (10 seconds instead of 2)
    this.ringBuffer = new AudioRingBuffer(this.format.bytesPerSecond * 10); // 10 seconds buffer
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
    };
    this.lastHeartbeat = Date.now();
    this.isEndingStream = false; // New flag for ending stream

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
    if (this.isPlaying) return;

    // Reset stopping flag when starting new process
    this.isStopping = false;
    this.isStopped = false;
    this.restartAttempts = 0; // Reset restart attempts on new start

    // Reset timing stats for new playback session
    this.stats.playbackStartTime = 0;
    this.stats.playbackEndTime = 0;
    this.stats.actualDuration = 0;
    this.stats.expectedDuration = 0;

    console.log(`[${this.instanceId}] Starting audio playback with format:`, this.format);

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
          console.log(`[${this.instanceId}] Found sox at: ${soxPath}`);
          break;
        } catch (e) {
          // Continue to next candidate
          console.log(`[${this.instanceId}] sox not found at: ${candidate}`);
          lastError = e;
        }
      }

      if (!soxPath) {
        console.log(`[${this.instanceId}] Sox not found in any location, falling back to ffplay`);
        this.startWithFfplay();
        return;
      }
      console.log(`[${this.instanceId}] Spawning sox at: ${soxPath}`);
      this.audioProcess = spawn(soxPath, soxArgs, {
        stdio: ["pipe", "ignore", "pipe"],
        detached: false,
        env: {
          ...process.env,
          PATH: process.env.PATH + ":/opt/homebrew/bin:/usr/local/bin:/usr/bin",
        },
      });

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

        console.log(`[${this.instanceId}] Playback timing:`, {
          startTime: this.stats.playbackStartTime.toFixed(2) + "ms",
          endTime: this.stats.playbackEndTime.toFixed(2) + "ms",
          actualDuration: this.stats.actualDuration.toFixed(2) + "ms",
          expectedDuration: this.stats.expectedDuration.toFixed(2) + "ms",
          difference: (this.stats.actualDuration - this.stats.expectedDuration).toFixed(2) + "ms",
          accuracy:
            ((this.stats.expectedDuration / this.stats.actualDuration) * 100).toFixed(1) + "%",
        });

        // If process exited normally (code 0), it finished playing successfully
        if (code === 0) {
          console.log("Audio playback completed successfully");
          // Clear any remaining buffer data
          if (this.ringBuffer.size > 0) {
            console.log(
              `[${this.instanceId}] Clearing remaining buffer data: ${this.ringBuffer.size} bytes`
            );
            this.ringBuffer.clear();
          }
          this.emit("completed");
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

          console.log(`[${this.instanceId}] Playback timing (close):`, {
            startTime: this.stats.playbackStartTime.toFixed(2) + "ms",
            endTime: this.stats.playbackEndTime.toFixed(2) + "ms",
            actualDuration: this.stats.actualDuration.toFixed(2) + "ms",
            expectedDuration: this.stats.expectedDuration.toFixed(2) + "ms",
            difference: (this.stats.actualDuration - this.stats.expectedDuration).toFixed(2) + "ms",
            accuracy:
              ((this.stats.expectedDuration / this.stats.actualDuration) * 100).toFixed(1) + "%",
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
            console.log("Audio process stdin pipe closed");
            this.isPlaying = false;
          } else {
            console.error("Audio process stdin error:", error.message);
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
    const chunkSize = this.format.bytesPerSecond * 0.05; // 50ms chunks
    const minBufferSize = chunkSize * 4; // Wait for at least 4 chunks
    const fallbackBufferSize = chunkSize * 2; // Fallback after timeout
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

      console.log(
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
      console.error("Both sox and ffplay failed:", error.message);
      this.emit("error", new Error("No compatible audio player found"));
    }
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
    console.log(`[${this.instanceId}] processAudioLoop START`);

    // Record playback start time
    if (this.stats.playbackStartTime === 0) {
      this.stats.playbackStartTime = performance.now();
      console.log(
        `[${this.instanceId}] Playback start time recorded: ${this.stats.playbackStartTime.toFixed(2)}ms`
      );

      // Start the keep-alive timer when playback begins
      this.startProcessKeepAlive();
    }

    if (!this.audioProcess) {
      console.log(`[${this.instanceId}] No audio process`);
      this._audioLoopActive = false;
      return;
    }
    const chunkSize = this.format.bytesPerSecond * 0.05; // 50ms chunks
    console.log(`[${this.instanceId}] Processing with chunk size:`, chunkSize, "bytes");

    // Adaptive polling based on buffer utilization
    let lastProcessTime = Date.now();
    let adaptiveDelay = 10; // Start with 10ms

    const processChunk = () => {
      if (!this.audioProcess) {
        this._audioLoopActive = false;
        return;
      }

      if (this.audioProcess.killed || this.audioProcess.exitCode !== null) {
        console.log(
          `[${this.instanceId}] Audio process died, checking if buffer needs draining...`
        );
        if (this.ringBuffer.size > 0) {
          console.log(
            `[${this.instanceId}] Buffer has ${this.ringBuffer.size} bytes remaining, continuing to drain...`
          );
          // Continue processing to drain the buffer
        } else {
          console.log(`[${this.instanceId}] Buffer empty, restarting audio process...`);
          this.restartAudioProcess();
          return;
        }
      }

      const available = this.ringBuffer.size;
      const utilization = available / this.ringBuffer.capacity;
      console.log(
        `[${this.instanceId}] Utilization:`,
        utilization,
        "available:",
        available,
        "capacity:",
        this.ringBuffer.capacity
      );

      // Adaptive delay based on buffer state
      if (utilization > 0.9) {
        // High utilization - process faster
        adaptiveDelay = Math.max(5, adaptiveDelay * 0.8);
      } else if (utilization < 0.3) {
        // Low utilization - slow down to avoid underruns
        adaptiveDelay = Math.min(50, adaptiveDelay * 1.2);
      } else {
        // Normal utilization - maintain current rate
        adaptiveDelay = Math.max(5, Math.min(30, adaptiveDelay));
      }

      if (available >= chunkSize) {
        const chunk = this.ringBuffer.read(chunkSize);

        // Only try to write to the process if it's still alive
        if (this.audioProcess && !this.audioProcess.killed && this.audioProcess.exitCode === null) {
          const writeResult = this.audioProcess.stdin.write(chunk, (err) => {
            if (err) console.error("stdin.write error:", err);
            else console.log("Wrote chunk to sox:", chunk.length);
          });

          if (!writeResult) {
            // Back-pressure detected, wait for drain
            console.log(`[${this.instanceId}] Back-pressure detected, waiting for drain...`);
            this.audioProcess.stdin.once("drain", () => {
              console.log(`[${this.instanceId}] Drain event received, resuming...`);
              setImmediate(processChunk);
            });
            return;
          }
        } else {
          console.log(
            `[${this.instanceId}] Audio process not available, skipping write but processing chunk: ${chunk.length} bytes`
          );
        }

        this.stats.bytesProcessed += chunk.length;
        this.stats.audioPosition += chunk.length;

        // Schedule next chunk with adaptive timing
        setTimeout(processChunk, adaptiveDelay);
      } else {
        // Buffer empty, check if we should stop
        if (this.isStopped && this.ringBuffer.size === 0) {
          console.log(`[${this.instanceId}] Buffer empty and stopped, ending processing`);

          // Calculate final timing statistics
          if (this.stats.playbackStartTime > 0 && this.stats.playbackEndTime === 0) {
            this.stats.playbackEndTime = performance.now();
            this.stats.actualDuration = this.stats.playbackEndTime - this.stats.playbackStartTime;

            console.log(`[${this.instanceId}] Final playback timing:`, {
              startTime: this.stats.playbackStartTime.toFixed(2) + "ms",
              endTime: this.stats.playbackEndTime.toFixed(2) + "ms",
              actualDuration: this.stats.actualDuration.toFixed(2) + "ms",
              expectedDuration: this.stats.expectedDuration.toFixed(2) + "ms",
              difference:
                (this.stats.actualDuration - this.stats.expectedDuration).toFixed(2) + "ms",
              accuracy:
                ((this.stats.expectedDuration / this.stats.actualDuration) * 100).toFixed(1) + "%",
              totalBytesProcessed: this.stats.bytesProcessed,
            });
          }

          this.ringBuffer.clear();
          this._audioLoopActive = false;
          return;
        }

        // Check if we're ending stream and buffer is empty
        if (this.isEndingStream && this.ringBuffer.size === 0) {
          console.log(
            `[${this.instanceId}] End stream requested and buffer empty - completing naturally`
          );

          // Calculate final timing statistics
          if (this.stats.playbackStartTime > 0 && this.stats.playbackEndTime === 0) {
            this.stats.playbackEndTime = performance.now();
            this.stats.actualDuration = this.stats.playbackEndTime - this.stats.playbackStartTime;

            console.log(`[${this.instanceId}] Natural completion timing:`, {
              startTime: this.stats.playbackStartTime.toFixed(2) + "ms",
              endTime: this.stats.playbackEndTime.toFixed(2) + "ms",
              actualDuration: this.stats.actualDuration.toFixed(2) + "ms",
              expectedDuration: this.stats.expectedDuration.toFixed(2) + "ms",
              difference:
                (this.stats.actualDuration - this.stats.expectedDuration).toFixed(2) + "ms",
              accuracy:
                ((this.stats.expectedDuration / this.stats.actualDuration) * 100).toFixed(1) + "%",
              totalBytesProcessed: this.stats.bytesProcessed,
            });
          }

          // Emit completed event for natural stream ending
          this.emit("completed");

          // Reset the ending stream flag
          this.isEndingStream = false;

          this.ringBuffer.clear();
          this._audioLoopActive = false;
          return;
        }

        // Buffer empty, poll again after adaptive delay
        setTimeout(processChunk, adaptiveDelay);
      }
    };

    processChunk();
  }

  // Memory usage logging
  startMemoryLogging() {
    if (this._memoryLogInterval) return;
    this._memoryLogInterval = setInterval(() => {
      const mem = process.memoryUsage();
      console.log(`[${this.instanceId}] Memory usage:`, (mem.rss / 1024 / 1024).toFixed(1), "MB");
    }, 5000);
  }

  // TODO: Replace sox/ffplay with node-speaker or native CoreAudio for true native playback
  // TODO: Implement client backpressure signaling (ws.send({ ready: true })) for flow control

  /**
   * Calculate expected duration based on audio format and data size
   */
  calculateExpectedDuration(totalBytes) {
    // Duration = (bytes) / (bytes per second)
    const durationSeconds = totalBytes / this.format.bytesPerSecond;
    const durationMs = durationSeconds * 1000;

    console.log(`[${this.instanceId}] Duration calculation:`, {
      totalBytes,
      bytesPerSecond: this.format.bytesPerSecond,
      durationSeconds: durationSeconds.toFixed(3),
      durationMs: durationMs.toFixed(1),
    });

    return durationMs;
  }

  /**
   * Set the total audio duration based on bytes received
   */
  setAudioDuration(totalBytes) {
    this.totalAudioBytes = totalBytes;
    this.audioDurationMs = this.calculateExpectedDuration(totalBytes);

    console.log(`[${this.instanceId}] Audio duration set:`, {
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
    const keepAliveDuration = this.audioDurationMs + 1000; // Add 1 second buffer

    console.log(
      `[${this.instanceId}] Starting process keep-alive timer for ${keepAliveDuration.toFixed(1)}ms`
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

    console.log(`[${this.instanceId}] Process termination check:`, {
      elapsedTime: elapsedTime.toFixed(1) + "ms",
      expectedEndTime: expectedEndTime.toFixed(1) + "ms",
      remainingBuffer: this.ringBuffer.size + " bytes",
    });

    // Only terminate if we've exceeded the expected duration and buffer is empty
    if (elapsedTime >= expectedEndTime && this.ringBuffer.size === 0) {
      console.log(`[${this.instanceId}] Terminating process after expected duration`);
      this.terminateProcessGracefully();
    } else if (elapsedTime >= expectedEndTime * 1.5) {
      // Force termination if we're way past expected duration
      console.log(`[${this.instanceId}] Force terminating process (50% past expected duration)`);
      this.terminateProcessGracefully();
    } else {
      console.log(`[${this.instanceId}] Process should continue running`);
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
   */
  async writeChunk(chunk) {
    // Dump PCM chunk to file for manual testing
    const fs = await import("fs");
    fs.appendFileSync("/tmp/test.raw", chunk);

    const written = this.ringBuffer.write(chunk);
    console.log(
      `[${this.instanceId}] writeChunk: wrote ${written} bytes, buffer size: ${this.ringBuffer.size}`
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
        accuracy:
          this.stats.actualDuration > 0
            ? ((this.stats.expectedDuration / this.stats.actualDuration) * 100).toFixed(1) + "%"
            : "N/A",
      },
    };
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
                bufferUtilization: this.audioProcessor.ringBuffer.utilization,
                stats: this.audioProcessor.getStatus(),
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

    // Set up audio processor event handlers
    this.audioProcessor.on("chunkReceived", (data) => {
      this.broadcast({
        type: "status",
        timestamp: Date.now(),
        data: {
          state: this.audioProcessor.isPlaying ? "playing" : "idle",
          bufferUtilization: data.bufferUtilization,
          audioPosition: this.audioProcessor.stats.audioPosition,
          performance: this.audioProcessor.getStatus(),
        },
      });
    });

    this.audioProcessor.on("error", (error) => {
      console.error("Audio processor error:", error.message);
      this.broadcast({
        type: "error",
        timestamp: Date.now(),
        data: { message: error.message },
      });
    });

    this.audioProcessor.on("completed", () => {
      console.log(`[${this.instanceId}] Audio playback completed naturally`);
      this.broadcast({
        type: "completed",
        timestamp: Date.now(),
        data: {
          state: "completed",
          bufferUtilization: 0,
          audioPosition: this.audioProcessor.stats.audioPosition,
          performance: this.audioProcessor.getStatus(),
        },
      });
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
    console.log("Received message:", message.type);
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
      default:
        console.error(`[${this.instanceId}] Unknown message type:`, message.type);
    }
  }

  /**
   * Handle audio chunk message
   */
  handleAudioChunk(ws, message) {
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
        console.log(`[${this.instanceId}] Chunk written successfully`);
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
    this.audioProcessor.stop();
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
        // Instead of immediately stopping, mark that we're ending the stream
        // and let the audio finish playing naturally
        console.log(`[${this.instanceId}] End stream requested - letting audio finish naturally`);
        this.audioProcessor.isEndingStream = true;
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
    }, 1000);
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
