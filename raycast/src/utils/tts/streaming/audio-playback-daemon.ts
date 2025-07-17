/**
 * Audio Playback Daemon Controller - Raycast Extension Client
 *
 * This module implements the controller for the audio daemon process. It handles:
 * - Spawning and managing the daemon process
 * - WebSocket communication with the daemon
 * - Error handling and reconnection logic
 * - State management for the extension
 *
 * ## Architecture Overview
 *
 * The AudioPlaybackDaemon controller implements a client-server architecture:
 *
 * 1. **Process Management**: Spawns and manages the standalone audio daemon process
 * 2. **WebSocket Client**: Communicates with the daemon via WebSocket for real-time control
 * 3. **State Management**: Tracks connection status, playback state, and performance metrics
 * 4. **Error Handling**: Implements robust error recovery and reconnection logic
 *
 * ## Key Benefits
 *
 * - **Separation of Concerns**: Controller only manages the daemon, doesn't implement audio processing
 * - **Process Isolation**: Audio processing runs in separate process for stability
 * - **Real-time Communication**: WebSocket enables immediate control and status updates
 * - **Robust Error Handling**: Automatic reconnection and error recovery
 *
 * @author @darianrosebrook
 * @version 2.0.0
 * @since 2025-07-17
 * @license MIT
 */

import { EventEmitter } from "events";
import { spawn, ChildProcess } from "child_process";
import { join, dirname } from "path";
import { existsSync, statSync } from "fs";
import { fileURLToPath } from "url";
import { logger } from "../../core/logger.js";
import { TTS_CONSTANTS } from "../../validation/tts-types.js";
import type {
  AudioFormat,
  StreamingStats,
  TTSProcessorConfig,
} from "../../validation/tts-types.js";

// Safe fallback for import.meta.url in Raycast environment
let __filename: string;
let __dirname: string;

try {
  if (import.meta?.url) {
    __filename = fileURLToPath(import.meta.url);
    __dirname = dirname(__filename);
  } else {
    // Fallback for environments where import.meta.url is not available
    __filename = process.cwd();
    __dirname = process.cwd();
  }
} catch (error) {
  // Fallback for environments where fileURLToPath fails
  __filename = process.cwd();
  __dirname = process.cwd();
}

// Import WebSocket for client connection
let WebSocket: any;

async function loadWebSocket() {
  try {
    const wsModule = await import("ws");
    WebSocket = wsModule.default;
  } catch (error) {
    console.warn("WebSocket library not available, audio daemon communication will be limited");
  }
}

function findKokoroProjectRoot(startDir: string): string | null {
  logger.consoleDebug("Starting project root search from:", startDir);
  let currentDir = startDir;
  for (let i = 0; i < 10; i++) {
    // Limit to 10 parent levels
    const markerPath = join(currentDir, ".kokoro-root");
    logger.consoleDebug(`Level ${i}: Checking ${markerPath}`);
    try {
      if (existsSync(markerPath) && statSync(markerPath).isFile()) {
        logger.consoleDebug("Found .kokoro-root marker at:", currentDir);
        return currentDir;
      }
    } catch (error) {
      logger.consoleDebug(`Error checking ${markerPath}:`, error);
    }
    const parentDir = dirname(currentDir);
    if (parentDir === currentDir) {
      logger.consoleDebug("Reached filesystem root, stopping search");
      break; // Reached filesystem root
    }
    currentDir = parentDir;
  }
  logger.consoleDebug("No .kokoro-root marker found in any parent directory");
  return null;
}

/**
 * Audio daemon process information
 */
interface AudioDaemonProcess {
  process: ChildProcess;
  port: number;
  isConnected: boolean;
  lastHeartbeat: number;
  healthStatus: "healthy" | "degraded" | "unhealthy";
}

/**
 * WebSocket message types for daemon communication
 */
interface DaemonMessage {
  type: "audio_chunk" | "control" | "status" | "heartbeat" | "error" | "completed";
  id?: string;
  timestamp: number;
  data?: unknown;
}

/**
 * Audio chunk message for sending audio data to daemon
 */
interface AudioChunkMessage {
  type: "audio_chunk";
  timestamp: number;
  data: {
    chunk: Uint8Array;
    format: AudioFormat;
    sequence: number;
  };
}

/**
 * Control message for daemon control
 */
interface ControlMessage {
  type: "control";
  timestamp: number;
  data: {
    action: "play" | "pause" | "stop" | "resume" | "configure" | "end_stream";
    params?: any;
  };
}

/**
 * Audio Playback Daemon Controller
 *
 * This class manages the audio daemon process and provides a clean interface
 * for the Raycast extension to control audio playback without implementing
 * the actual audio processing logic.
 */
export class AudioPlaybackDaemon extends EventEmitter {
  public readonly name = "AudioPlaybackDaemon";
  public readonly version = "2.0.0";
  private instanceId: string;
  private config: {
    daemonPath: string;
    daemonScriptPath: string;
    port: number;
    bufferSize: number;
    heartbeatInterval: number;
    healthCheckTimeout: number;
    developmentMode: boolean;
  };

  private daemonProcess: AudioDaemonProcess | null = null;
  private ws: any = null; // WebSocket client connection
  private isConnected: boolean = false;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 5;
  private reconnectDelay: number = 1000;

  // Performance tracking
  private stats: StreamingStats = {
    chunksReceived: 0,
    bytesReceived: 0,
    averageChunkSize: 0,
    streamingDuration: 0,
    efficiency: 0,
    underruns: 0,
    bufferHealth: 1.0,
    totalAudioDuration: 0,
  };

  // State management
  private isPlaying: boolean = false;
  private isPaused: boolean = false;
  private currentAudioFormat: AudioFormat;
  private sequenceNumber: number = 0;

  constructor(config: Partial<TTSProcessorConfig> = {}) {
    super();
    this.instanceId = this.constructor.name + "_" + Date.now();
    logger.consoleDebug(`[${this.instanceId}] Constructor called`);
    logger.consoleDebug(`[${this.instanceId}] Config provided:`, config);

    // Robust path resolution for daemon script (ES module compatible)
    // Priority: config > environment variable > auto-detected project root > absolute paths > relative paths
    const configDaemonPath = config.daemonScriptPath;
    const envDaemonPath = process.env.KOKORO_AUDIO_DAEMON_PATH;

    // Detect if we're running in Raycast extension environment
    // Check multiple indicators of Raycast extension environment
    const cwd = process.cwd();
    const isRaycastExtension =
      cwd.includes("raycast/extensions") ||
      cwd.includes(".config/raycast") ||
      cwd === "/" || // Raycast sometimes runs from root
      process.env.RAYCAST_EXTENSION_PATH !== undefined; // Raycast environment variable

    logger.consoleInfo(`[${this.instanceId}] Extension CWD:`, process.cwd());
    logger.consoleInfo(`[${this.instanceId}] Is Raycast extension:`, isRaycastExtension);

    // Auto-detect project root by walking up parent directories for .kokoro-root
    let projectRoot = process.cwd();
    let autoDetectedRoot: string | null = null;
    if (isRaycastExtension) {
      // If running from root, try to find the actual extension directory first
      let searchStartDir = process.cwd();
      if (cwd === "/") {
        logger.consoleInfo(
          `[${this.instanceId}] Running from root, trying to find extension directory...`
        );
        // Try common Raycast extension locations
        const possibleExtensionDirs = [
          process.env.RAYCAST_EXTENSION_PATH,
          process.env.HOME + "/.config/raycast/extensions/raycast-kokoro-tts",
          process.env.HOME + "/.config/raycast/extensions",
          "/Users/darianrosebrook/.config/raycast/extensions/raycast-kokoro-tts",
        ].filter(Boolean);

        for (const extDir of possibleExtensionDirs) {
          if (extDir && existsSync(extDir)) {
            logger.consoleInfo(`[${this.instanceId}] Found extension directory:`, extDir);
            searchStartDir = extDir;
            break;
          }
        }
      }

      autoDetectedRoot = findKokoroProjectRoot(searchStartDir);
      if (autoDetectedRoot) {
        projectRoot = autoDetectedRoot;
        logger.consoleInfo("Auto-detected Kokoro project root via .kokoro-root marker", {
          component: this.name,
          method: "constructor",
          autoDetectedRoot,
        });
      } else {
        logger.consoleInfo(`[${this.instanceId}] Auto-detection failed, trying fallback paths...`);
        // Fallback to previous guessing logic
        const possibleProjectRoots = [
          "/Users/darianrosebrook/Desktop/Projects/kokoro-onnx",
          process.env.KOKORO_PROJECT_ROOT,
          process.env.HOME + "/Desktop/Projects/kokoro-onnx",
          process.env.HOME + "/Projects/kokoro-onnx",
        ].filter(Boolean);
        logger.consoleInfo(`[${this.instanceId}] Fallback project roots:`, possibleProjectRoots);
        for (const root of possibleProjectRoots) {
          const daemonPath = join(root, "raycast/bin/audio-daemon.js");
          logger.consoleInfo(`[${this.instanceId}] Checking fallback path: ${daemonPath}`);
          if (root && existsSync(daemonPath)) {
            projectRoot = root;
            logger.consoleInfo(`[${this.instanceId}] Found daemon in fallback path:`, root);
            break;
          }
        }
      }
    }

    const possiblePaths = [
      // Configuration path (highest priority)
      ...(configDaemonPath ? [configDaemonPath] : []),
      // Environment variable path (second priority)
      ...(envDaemonPath ? [envDaemonPath] : []),
      // Auto-detected project root (third priority)
      ...(autoDetectedRoot
        ? [
            join(autoDetectedRoot, "raycast/bin/audio-daemon.js"),
            join(autoDetectedRoot, "bin/audio-daemon.js"),
          ]
        : []),
      // Absolute paths for Raycast extension environment
      ...(isRaycastExtension && !autoDetectedRoot
        ? [
            join(projectRoot, "raycast/bin/audio-daemon.js"),
            join(projectRoot, "bin/audio-daemon.js"),
          ]
        : []),
      // Local extension directory paths
      join(process.cwd(), "audio-daemon.js"), // Local copy in extension directory
      // Relative paths (fallback)
      join(process.cwd(), "bin/audio-daemon.js"), // Relative to working directory
      join(process.cwd(), "raycast/bin/audio-daemon.js"), // Raycast subdirectory
      join(__dirname, "../../../bin/audio-daemon.js"), // Relative to current file location
      join(__dirname, "../../bin/audio-daemon.js"), // Alternative relative path
    ];

    logger.consoleInfo("Starting daemon script path resolution", {
      component: this.name,
      method: "constructor",
      workingDirectory: process.cwd(),
      isRaycastExtension,
      projectRoot,
      autoDetectedRoot,
      possiblePaths,
    });

    logger.consoleDebug("Checking possible daemon paths:");
    possiblePaths.forEach((path, index) => {
      logger.consoleDebug(`  ${index + 1}. ${path}`);
    });

    let daemonScriptPath = "";
    for (const path of possiblePaths) {
      try {
        if (existsSync(path)) {
          daemonScriptPath = path;
          logger.consoleInfo(`[${this.instanceId}] Found daemon script at:`, daemonScriptPath);
          logger.consoleInfo("Found daemon script", {
            component: this.name,
            method: "constructor",
            path: daemonScriptPath,
          });
          break;
        } else {
          logger.consoleInfo(`[${this.instanceId}] Path not found: ${path}`);
        }
      } catch (error) {
        logger.consoleInfo(`[${this.instanceId}] Error checking path ${path}:`, error);
        logger.warn("Error checking daemon path", {
          component: this.name,
          method: "constructor",
          path,
          error: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }

    if (!daemonScriptPath) {
      // Try to create a local copy of the daemon script in the extension directory
      const localDaemonPath = join(process.cwd(), "audio-daemon.js");

      try {
        // Check if we can find the daemon script in any of the project roots
        const projectRoots = [
          "/Users/darianrosebrook/Desktop/Projects/kokoro-onnx",
          process.env.KOKORO_PROJECT_ROOT,
          process.env.HOME + "/Desktop/Projects/kokoro-onnx",
          process.env.HOME + "/Projects/kokoro-onnx",
        ].filter(Boolean);

        for (const root of projectRoots) {
          const sourcePath = join(root, "raycast/bin/audio-daemon.js");
          if (existsSync(sourcePath)) {
            // Copy the daemon script to the extension directory
            const fs = require("fs");
            fs.copyFileSync(sourcePath, localDaemonPath);
            daemonScriptPath = localDaemonPath;
            logger.consoleInfo("Copied daemon script to extension directory", {
              component: this.name,
              method: "constructor",
              sourcePath,
              localDaemonPath,
            });
            break;
          }
        }
      } catch (copyError) {
        logger.warn("Failed to copy daemon script", {
          component: this.name,
          method: "constructor",
          error: copyError instanceof Error ? copyError.message : "Unknown error",
        });
      }

      if (!daemonScriptPath) {
        const error = new Error("Audio daemon script not found in any expected location");
        logger.error("Daemon script not found", {
          component: this.name,
          method: "constructor",
          possiblePaths,
          error: error.message,
        });
        throw error;
      }
    }

    // Robust Node.js executable detection
    let nodeExecutable = "";
    const nodePath = process.execPath;

    logger.consoleInfo("Detecting Node.js executable", {
      component: this.name,
      method: "constructor",
      processExecPath: nodePath,
    });

    if (nodePath && typeof nodePath === "string" && existsSync(nodePath)) {
      nodeExecutable = nodePath;
      logger.consoleInfo("Using process.execPath for Node.js", {
        component: this.name,
        method: "constructor",
        nodeExecutable,
      });
    } else {
      // Fallback to common Node.js locations
      const commonPaths = [
        "/usr/local/bin/node",
        "/opt/homebrew/bin/node",
        "/usr/bin/node",
        "node", // Try PATH
      ];

      for (const path of commonPaths) {
        try {
          if (existsSync(path)) {
            nodeExecutable = path;
            logger.consoleInfo("Found Node.js in common location", {
              component: this.name,
              method: "constructor",
              nodeExecutable,
            });
            break;
          }
        } catch (error) {
          logger.warn("Error checking Node.js path", {
            component: this.name,
            method: "constructor",
            path,
            error: error instanceof Error ? error.message : "Unknown error",
          });
        }
      }
    }

    if (!nodeExecutable) {
      const error = new Error(
        "Node.js executable not found. Please ensure Node.js is installed and available."
      );
      logger.error("Node.js executable not found", {
        component: this.name,
        method: "constructor",
        error: error.message,
      });
      throw error;
    }

    this.config = {
      daemonPath: nodeExecutable,
      daemonScriptPath,
      port: config.daemonPort ?? 8081,
      bufferSize: config.bufferSize ?? TTS_CONSTANTS.DEFAULT_BUFFER_SIZE,
      heartbeatInterval: 5000,
      healthCheckTimeout: 10000,
      developmentMode: config.developmentMode ?? false,
    };

    this.currentAudioFormat = {
      format: "wav",
      sampleRate: 24000,
      channels: 1,
      bitDepth: 16,
      bytesPerSample: 2,
      bytesPerSecond: 48000,
    };

    logger.consoleInfo("AudioPlaybackDaemon controller initialized", {
      component: this.name,
      method: "constructor",
      config: {
        daemonPath: this.config.daemonPath,
        daemonScriptPath: this.config.daemonScriptPath,
        port: this.config.port,
        bufferSize: this.config.bufferSize,
        developmentMode: this.config.developmentMode,
      },
    });
  }

  /**
   * Initialize the daemon controller
   */
  async initialize(): Promise<void> {
    logger.consoleInfo("Initializing audio daemon controller", {
      component: this.name,
      method: "initialize",
    });

    // Load WebSocket library
    await loadWebSocket();

    try {
      await this.startDaemon();
      await this.waitForConnection();
      await this.configureAudio();

      logger.consoleInfo("Audio daemon controller initialized successfully", {
        component: this.name,
        method: "initialize",
        port: this.config.port,
      });
    } catch (error) {
      // Check if it's a port conflict error
      const errorMessage = error instanceof Error ? error.message : "Unknown error";
      if (errorMessage.includes("EADDRINUSE") || errorMessage.includes("address already in use")) {
        logger.warn("Port conflict detected during initialization, attempting to resolve", {
          component: this.name,
          method: "initialize",
          error: errorMessage,
        });

        try {
          await this.handlePortConflict();
          logger.consoleInfo("Successfully resolved port conflict during initialization", {
            component: this.name,
            method: "initialize",
            port: this.config.port,
          });
        } catch (retryError) {
          logger.error("Failed to resolve port conflict during initialization", {
            component: this.name,
            method: "initialize",
            originalError: errorMessage,
            retryError: retryError instanceof Error ? retryError.message : "Unknown error",
          });
          throw retryError;
        }
      } else {
        logger.error("Failed to initialize audio daemon controller", {
          component: this.name,
          method: "initialize",
          error: errorMessage,
        });
        throw error;
      }
    }
  }

  /**
   * Clean up any existing daemon processes that might be using our ports
   */
  private async cleanupExistingDaemons(): Promise<void> {
    logger.consoleInfo("Checking for existing daemon processes", {
      component: this.name,
      method: "cleanupExistingDaemons",
    });

    try {
      // Check for processes using our target port range
      const { exec } = await import("child_process");
      const { promisify } = await import("util");
      const execAsync = promisify(exec);

      // Check for Node.js processes that might be our daemon
      const result = await execAsync("ps aux | grep 'audio-daemon.js' | grep -v grep");

      if (result.stdout.trim()) {
        logger.warn("Found existing daemon processes", {
          component: this.name,
          method: "cleanupExistingDaemons",
          processes: result.stdout.trim(),
        });

        // Kill any existing daemon processes
        await execAsync("pkill -f 'audio-daemon.js'");

        logger.consoleInfo("Cleaned up existing daemon processes", {
          component: this.name,
          method: "cleanupExistingDaemons",
        });

        // Wait a moment for processes to terminate
        await new Promise((resolve) => setTimeout(resolve, 2000));
      }
    } catch (error) {
      // Ignore errors - this is just cleanup
      logger.debug("Cleanup check failed (this is normal)", {
        component: this.name,
        method: "cleanupExistingDaemons",
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }

  /**
   * Handle port conflict by finding a new available port and restarting
   */
  private async handlePortConflict(): Promise<void> {
    logger.consoleInfo("Handling port conflict", {
      component: this.name,
      method: "handlePortConflict",
      currentPort: this.config.port,
    });

    try {
      // Find a new available port
      const newPort = await this.findAvailablePort(this.config.port + 1);

      logger.consoleInfo("Found new available port", {
        component: this.name,
        method: "handlePortConflict",
        oldPort: this.config.port,
        newPort,
      });

      // Update config with new port
      this.config.port = newPort;

      // Clean up the failed process
      this.daemonProcess = null;
      this.isConnected = false;

      // Wait a moment before retrying
      await new Promise((resolve) => setTimeout(resolve, 1000));

      // Retry starting the daemon with the new port
      await this.startDaemon();
      await this.waitForConnection();
      await this.configureAudio();

      logger.consoleInfo("Successfully restarted daemon with new port", {
        component: this.name,
        method: "handlePortConflict",
        port: this.config.port,
      });
    } catch (error) {
      logger.error("Failed to handle port conflict", {
        component: this.name,
        method: "handlePortConflict",
        error: error instanceof Error ? error.message : "Unknown error",
      });
      throw error;
    }
  }

  /**
   * Find an available port starting from the given port
   */
  private async findAvailablePort(startPort: number): Promise<number> {
    const maxAttempts = 10;
    let currentPort = startPort;

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      try {
        // Try to create a server on the port to check if it's available
        const { createServer } = await import("net");
        const server = createServer();

        await new Promise<void>((resolve, reject) => {
          const timeout = setTimeout(() => {
            server.close();
            reject(new Error("Port check timeout"));
          }, 1000);

          server.listen(currentPort, () => {
            clearTimeout(timeout);
            server.close();
            resolve();
          });

          server.on("error", () => {
            clearTimeout(timeout);
            server.close();
            reject(new Error("Port in use"));
          });
        });

        // If we get here, the port is available
        logger.consoleInfo(`[${this.instanceId}] Port ${currentPort} is available`);
        logger.debug("Port available", {
          component: this.name,
          method: "findAvailablePort",
          port: currentPort,
        });
        return currentPort;
      } catch (error) {
        logger.consoleInfo(`[${this.instanceId}] Port ${currentPort} is in use, trying next port`);
        logger.debug("Port in use, trying next port", {
          component: this.name,
          method: "findAvailablePort",
          port: currentPort,
          error: error instanceof Error ? error.message : "Unknown error",
        });
        currentPort++;
      }
    }

    throw new Error(
      `No available ports found in range ${startPort}-${startPort + maxAttempts - 1}`
    );
  }

  /**
   * Start the audio daemon process
   */
  private async startDaemon(): Promise<void> {
    if (this.daemonProcess) {
      logger.warn("Daemon process already running", {
        component: this.name,
        method: "startDaemon",
      });
      return;
    }

    // Clean up any existing daemon processes first
    await this.cleanupExistingDaemons();

    // Try to find an available port
    logger.consoleDebug(
      `[${this.instanceId}] Checking for available port starting from:`,
      this.config.port
    );
    const availablePort = await this.findAvailablePort(this.config.port);
    if (availablePort !== this.config.port) {
      logger.consoleInfo(
        `[${this.instanceId}] Port conflict detected, switching from`,
        this.config.port,
        "to",
        availablePort
      );
      logger.consoleInfo("Port conflict detected, using fallback port", {
        component: this.name,
        method: "startDaemon",
        originalPort: this.config.port,
        fallbackPort: availablePort,
      });
      this.config.port = availablePort;
    } else {
      logger.consoleDebug(`[${this.instanceId}] Original port ${this.config.port} is available`);
    }

    logger.consoleInfo("Starting audio daemon process", {
      component: this.name,
      method: "startDaemon",
      daemonPath: this.config.daemonPath,
      daemonScriptPath: this.config.daemonScriptPath,
      port: this.config.port,
    });

    try {
      logger.consoleDebug(`[${this.instanceId}] Spawning daemon process with:`);
      logger.consoleDebug("  - Node executable:", this.config.daemonPath);
      logger.consoleDebug("  - Daemon script:", this.config.daemonScriptPath);
      logger.consoleDebug("  - Port:", this.config.port);

      const daemonProcess = spawn(
        this.config.daemonPath,
        [this.config.daemonScriptPath, "--port", this.config.port.toString()],
        {
          stdio: ["ignore", "pipe", "pipe"],
          detached: false,
          env: {
            ...process.env,
            NODE_ENV: this.config.developmentMode ? "development" : "production",
          },
        }
      );

      logger.consoleInfo("Daemon process spawned", {
        component: this.name,
        method: "startDaemon",
        pid: daemonProcess.pid,
        port: this.config.port,
      });

      // Set up process event handlers
      daemonProcess.on("error", (error) => {
        logger.consoleError(`[${this.instanceId}] Daemon process error:`, error);
        this.handleDaemonError(error);
      });

      daemonProcess.on("exit", (code, signal) => {
        logger.consoleInfo(
          `[${this.instanceId}] Daemon process exit - code: ${code} signal: ${signal}`
        );
        this.handleDaemonExit(code, signal);
      });

      // Set up stdout/stderr handlers
      if (daemonProcess.stdout) {
        daemonProcess.stdout.on("data", (data) => {
          const message = data.toString().trim();
          logger.consoleDebug("Daemon stdout:", message);
          logger.debug("Daemon stdout", {
            component: this.name,
            method: "startDaemon",
            pid: daemonProcess.pid,
            message: message,
          });
        });
      }

      if (daemonProcess.stderr) {
        daemonProcess.stderr.on("data", (data) => {
          const message = data.toString().trim();
          logger.consoleWarn("Daemon stderr:", message);
          logger.warn("Daemon stderr", {
            component: this.name,
            method: "startDaemon",
            pid: daemonProcess.pid,
            message: message,
          });

          // Check for port conflict error
          if (message.includes("EADDRINUSE") || message.includes("address already in use")) {
            logger.warn("Port conflict detected in daemon stderr", {
              component: this.name,
              method: "startDaemon",
              port: this.config.port,
              message,
            });

            // Kill the failed process and try with a different port
            daemonProcess.kill("SIGTERM");
            this.handlePortConflict();
          }
        });
      }

      this.daemonProcess = {
        process: daemonProcess,
        port: this.config.port,
        isConnected: false,
        lastHeartbeat: Date.now(),
        healthStatus: "healthy",
      };

      logger.consoleInfo("Daemon process setup complete", {
        component: this.name,
        method: "startDaemon",
        pid: daemonProcess.pid,
      });
    } catch (error) {
      logger.error("Failed to start daemon process", {
        component: this.name,
        method: "startDaemon",
        error: error instanceof Error ? error.message : "Unknown error",
      });
      throw error;
    }
  }

  /**
   * Wait for daemon to be ready
   */
  private async waitForConnection(): Promise<void> {
    if (!this.daemonProcess) {
      throw new Error("Daemon process not started");
    }

    logger.consoleInfo("Waiting for daemon connection", {
      component: this.name,
      method: "waitForConnection",
      port: this.config.port,
    });

    // Check daemon health endpoint to verify it's ready
    const maxWaitTime = 10000; // 10 seconds
    const startTime = Date.now();
    const healthUrl = `http://localhost:${this.config.port}/health`;

    logger.consoleInfo(`[${this.instanceId}] Checking daemon health at:`, healthUrl);

    while (Date.now() - startTime < maxWaitTime) {
      try {
        const response = await fetch(healthUrl, {
          method: "GET",
          headers: {
            Accept: "application/json",
          },
          signal: AbortSignal.timeout(2000), // 2 second timeout per request
        });

        if (response.ok) {
          const health = await response.json();
          logger.consoleInfo(`[${this.instanceId}] Daemon health check passed:`, health.status);

          // Mark as connected
          this.daemonProcess.isConnected = true;
          this.isConnected = true;

          // Establish WebSocket connection
          await this.establishWebSocketConnection();

          logger.consoleInfo("Daemon connection established", {
            component: this.name,
            method: "waitForConnection",
            port: this.config.port,
            health: health.status,
          });
          return;
        }
      } catch (error) {
        logger.consoleInfo(`[${this.instanceId}] Daemon not ready yet, retrying...`);
        // Continue waiting
      }

      await new Promise((resolve) => setTimeout(resolve, 500)); // Check every 500ms
    }

    throw new Error("Timeout waiting for daemon connection");
  }

  /**
   * Establish WebSocket connection to the daemon
   */
  private async establishWebSocketConnection(): Promise<void> {
    if (!WebSocket) {
      throw new Error("WebSocket library not available");
    }

    const wsUrl = `ws://localhost:${this.config.port}`;
    logger.consoleInfo(`[${this.instanceId}] Establishing WebSocket connection to:`, wsUrl);

    return new Promise<void>((resolve, reject) => {
      this.ws = new WebSocket(wsUrl);

      this.ws.on("open", () => {
        logger.consoleInfo(`[${this.instanceId}] WebSocket connection established`);
        logger.consoleInfo("WebSocket connection established", {
          component: this.name,
          method: "establishWebSocketConnection",
          url: wsUrl,
        });
        resolve();
      });

      this.ws.on("error", (error: Error) => {
        logger.consoleInfo(`[${this.instanceId}] WebSocket connection error:`, error);
        logger.error("WebSocket connection error", {
          component: this.name,
          method: "establishWebSocketConnection",
          error: error.message,
        });
        reject(error);
      });

      this.ws.on("close", (code: number, reason: string) => {
        logger.consoleInfo(
          `[${this.instanceId}] WebSocket connection closed - code: ${code} reason: ${reason}`
        );
        logger.debug("WebSocket connection closed", {
          component: this.name,
          method: "establishWebSocketConnection",
          code,
          reason,
        });
        this.isConnected = false;
        this.daemonProcess!.isConnected = false;
      });

      this.ws.on("message", (data: Buffer) => {
        try {
          const message = JSON.parse(data.toString());
          logger.consoleInfo(`[${this.instanceId}] Received message from daemon:`, message.type);
          this.handleIncomingMessage(message);
        } catch (error) {
          logger.consoleInfo(
            `[${this.instanceId}] Failed to parse WebSocket message:`,
            JSON.stringify(error)
          );
          logger.error("Failed to parse WebSocket message", {
            component: this.name,
            method: "establishWebSocketConnection",
            error: error instanceof Error ? error.message : "Unknown error",
          });
        }
      });

      // Set a timeout for the connection
      setTimeout(() => {
        if (this.ws.readyState !== WebSocket.OPEN) {
          reject(new Error("WebSocket connection timeout"));
        }
      }, 5000);
    });
  }

  /**
   * Configure audio settings with the daemon
   */
  private async configureAudio(): Promise<void> {
    logger.consoleInfo("Configuring audio settings", {
      component: this.name,
      method: "configureAudio",
      format: this.currentAudioFormat,
    });

    // Send configuration message to daemon
    const configMessage: ControlMessage = {
      type: "control",
      timestamp: Date.now(),
      data: {
        action: "configure",
        params: {
          format: this.currentAudioFormat,
          bufferSize: this.config.bufferSize,
        },
      },
    };

    await this.sendMessage(configMessage);

    logger.consoleInfo("Audio configuration sent to daemon", {
      component: this.name,
      method: "configureAudio",
    });
  }

  /**
   * Start audio playback in the daemon
   */
  async startPlayback(): Promise<void> {
    if (!this.daemonProcess?.isConnected) {
      throw new Error("Daemon not connected");
    }

    logger.consoleInfo("Starting audio playback", {
      component: this.name,
      method: "startPlayback",
    });

    const playMessage: ControlMessage = {
      type: "control",
      timestamp: Date.now(),
      data: {
        action: "play",
      },
    };

    await this.sendMessage(playMessage);
    this.isPlaying = true;
    this.isPaused = false;

    logger.consoleInfo("Audio playback started", {
      component: this.name,
      method: "startPlayback",
    });
  }

  /**
   * Write audio chunk to daemon
   */
  async writeChunk(chunk: Uint8Array): Promise<void> {
    if (!this.daemonProcess?.isConnected) {
      throw new Error("Daemon not connected");
    }

    logger.debug("Writing audio chunk to daemon", {
      component: this.name,
      method: "writeChunk",
      chunkSize: chunk.length,
      sequence: this.sequenceNumber,
    });

    // Update stats
    this.stats.chunksReceived++;
    this.stats.bytesReceived += chunk.length;
    this.stats.averageChunkSize = this.stats.bytesReceived / this.stats.chunksReceived;

    // Send audio chunk message to daemon
    const audioMessage: AudioChunkMessage = {
      type: "audio_chunk",
      timestamp: Date.now(),
      data: {
        chunk: chunk, // Send as Uint8Array, daemon will handle base64 conversion if needed
        format: this.currentAudioFormat,
        sequence: this.sequenceNumber++,
      },
    };

    await this.sendMessage(audioMessage);

    logger.debug("Audio chunk sent to daemon", {
      component: this.name,
      method: "writeChunk",
      chunkSize: chunk.length,
      sequence: this.sequenceNumber - 1,
    });
  }

  /**
   * End the audio stream
   */
  async endStream(): Promise<void> {
    if (!this.daemonProcess?.isConnected) {
      logger.warn("Cannot end stream - daemon not connected", {
        component: this.name,
        method: "endStream",
      });
      return;
    }

    logger.consoleInfo("Ending audio stream", {
      component: this.name,
      method: "endStream",
      totalChunks: this.stats.chunksReceived,
      totalBytes: this.stats.bytesReceived,
    });

    // Instead of immediately stopping, send an "end_stream" message to let the daemon
    // finish playing the buffered audio naturally
    const endMessage: DaemonMessage = {
      type: "control",
      timestamp: Date.now(),
      data: {
        action: "end_stream",
      },
    };

    await this.sendMessage(endMessage);

    // Wait for the audio to finish playing naturally
    // The daemon will send a "completed" event when audio finishes
    await this.waitForAudioCompletion();

    // Update stats
    this.stats.streamingDuration = Date.now() - (this.stats.streamingDuration || Date.now());
    this.stats.efficiency = this.calculateEfficiency();

    logger.consoleInfo("Audio stream ended", {
      component: this.name,
      method: "endStream",
      streamingDuration: this.stats.streamingDuration,
      efficiency: this.stats.efficiency,
    });
  }

  /**
   * Wait for audio playback to complete naturally
   */
  private async waitForAudioCompletion(): Promise<void> {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        logger.warn("Audio completion timeout - forcing stop", {
          component: this.name,
          method: "waitForAudioCompletion",
        });
        // Force stop if timeout occurs
        this.forceStop();
        resolve();
      }, 30000); // 30 second timeout

      const onCompleted = () => {
        clearTimeout(timeout);
        this.removeListener("completed", onCompleted);
        this.removeListener("error", onError);
        resolve();
      };

      const onError = (error: Error) => {
        clearTimeout(timeout);
        this.removeListener("completed", onCompleted);
        this.removeListener("error", onError);
        reject(error);
      };

      this.once("completed", onCompleted);
      this.once("error", onError);

      // Check if already completed
      if (!this.isPlaying && !this.daemonProcess?.isConnected) {
        clearTimeout(timeout);
        resolve();
      }
    });
  }

  /**
   * Force stop the audio playback (used as fallback)
   */
  private async forceStop(): Promise<void> {
    logger.warn("Forcing audio playback stop", {
      component: this.name,
      method: "forceStop",
    });

    const stopMessage: ControlMessage = {
      type: "control",
      timestamp: Date.now(),
      data: {
        action: "stop",
      },
    };

    await this.sendMessage(stopMessage);
    this.isPlaying = false;
    this.isPaused = false;
  }

  /**
   * Pause audio playback
   */
  async pause(): Promise<void> {
    if (!this.daemonProcess?.isConnected) {
      logger.warn("Cannot pause - daemon not connected", {
        component: this.name,
        method: "pause",
      });
      return;
    }

    logger.consoleInfo("Pausing audio playback", {
      component: this.name,
      method: "pause",
    });

    const pauseMessage: ControlMessage = {
      type: "control",
      timestamp: Date.now(),
      data: {
        action: "pause",
      },
    };

    await this.sendMessage(pauseMessage);
    this.isPaused = true;
    this.isPlaying = false;

    logger.consoleInfo("Audio playback paused", {
      component: this.name,
      method: "pause",
    });
  }

  /**
   * Resume audio playback
   */
  async resume(): Promise<void> {
    if (!this.daemonProcess?.isConnected) {
      logger.warn("Cannot resume - daemon not connected", {
        component: this.name,
        method: "resume",
      });
      return;
    }

    logger.consoleInfo("Resuming audio playback", {
      component: this.name,
      method: "resume",
    });

    const resumeMessage: ControlMessage = {
      type: "control",
      timestamp: Date.now(),
      data: {
        action: "resume",
      },
    };

    await this.sendMessage(resumeMessage);
    this.isPlaying = true;
    this.isPaused = false;

    logger.consoleInfo("Audio playback resumed", {
      component: this.name,
      method: "resume",
    });
  }

  /**
   * Stop audio playback
   */
  async stop(): Promise<void> {
    logger.consoleInfo("Stopping audio playback", {
      component: this.name,
      method: "stop",
    });

    if (this.daemonProcess?.isConnected) {
      const stopMessage: ControlMessage = {
        type: "control",
        timestamp: Date.now(),
        data: {
          action: "stop",
        },
      };

      await this.sendMessage(stopMessage);
    }

    this.isPlaying = false;
    this.isPaused = false;
    this.sequenceNumber = 0;

    logger.consoleInfo("Audio playback stopped", {
      component: this.name,
      method: "stop",
    });
  }

  /**
   * Send message to daemon via WebSocket
   */
  private async sendMessage(message: DaemonMessage): Promise<void> {
    if (!this.daemonProcess?.isConnected || !this.ws) {
      throw new Error("Daemon not connected or WebSocket not established");
    }

    if (this.ws.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket connection not open");
    }

    logger.debug("Sending message to daemon", {
      component: this.name,
      method: "sendMessage",
      messageType: message.type,
      timestamp: message.timestamp,
    });

    // Serialize the message to JSON
    const messageJson = JSON.stringify(message);
    logger.consoleDebug("Sending message to daemon:", message.type);

    this.ws.send(messageJson);
  }

  /**
   * Handle incoming messages from the daemon
   */
  private handleIncomingMessage(message: DaemonMessage): void {
    switch (message.type) {
      case "audio_chunk":
        const audioChunk = message as AudioChunkMessage;
        this.handleAudioChunk(audioChunk);
        break;
      case "status":
        const status = message as DaemonMessage; // Assuming status messages are just status updates
        this.handleStatusUpdate(status);
        break;
      case "heartbeat":
        const heartbeat = message as DaemonMessage;
        // this.handleHeartbeat(heartbeat);
        break;
      case "completed":
        const completed = message as DaemonMessage;
        this.handleCompleted(completed);
        break;
      case "error":
        const error = message as DaemonMessage;
        this.handleDaemonError(new Error(error.data as string));
        break;
      default:
        logger.warn("Received unknown message type from daemon", {
          component: this.name,
          method: "handleIncomingMessage",
          messageType: message.type,
        });
    }
  }

  /**
   * Handle audio chunk messages from the daemon
   */
  private handleAudioChunk(message: AudioChunkMessage): void {
    logger.debug("Handling audio chunk message", {
      component: this.name,
      method: "handleAudioChunk",
      chunkSize: message.data.chunk.length,
      sequence: message.data.sequence,
    });

    let chunkData = message.data.chunk;
    if (typeof chunkData === "string") {
      chunkData = Buffer.from(chunkData, "base64");
    } else if (chunkData instanceof Buffer || chunkData instanceof Uint8Array) {
      // Already correct
    } else if (
      chunkData &&
      typeof chunkData === "object" &&
      Object.keys(chunkData).every((k) => !isNaN(Number(k)))
    ) {
      // Convert plain object with numeric keys to Buffer
      chunkData = Buffer.from(Object.values(chunkData));
    } else {
      console.error("[AUDIO-DAEMON] Invalid chunk data format:", typeof chunkData, chunkData);
      return;
    }

    // Append the chunk to the audio buffer
    // In a real application, you would decode and play the audio
    // For now, we just update stats and emit an event
    this.stats.chunksReceived++;
    this.stats.bytesReceived += chunkData.length;
    this.stats.averageChunkSize = this.stats.bytesReceived / this.stats.chunksReceived;

    this.emit("audioChunk", chunkData);
  }

  /**
   * Handle status update messages from the daemon
   */
  private handleStatusUpdate(message: DaemonMessage): void {
    // logger.debug("Handling status update message", {
    //   component: this.name,
    //   method: "handleStatusUpdate",
    //   status: message.data,
    // });
    // For now, we'll just log the status
    // logger.consoleInfo("Received status update from daemon", {
    //   component: this.name,
    //   method: "handleStatusUpdate",
    //   status: message.data,
    // });
  }

  /**
   * Handle heartbeat messages from the daemon
   */
  private handleHeartbeat(message: DaemonMessage): void {
    logger.debug("Handling heartbeat message", {
      component: this.name,
      method: "handleHeartbeat",
      timestamp: message.timestamp,
    });
    // Update last heartbeat timestamp
    this.daemonProcess!.lastHeartbeat = message.timestamp;
  }

  /**
   * Handle completed message from daemon
   */
  private handleCompleted(message: DaemonMessage): void {
    logger.consoleInfo("Audio playback completed naturally", {
      component: this.name,
      method: "handleCompleted",
      timestamp: message.timestamp,
    });

    this.isPlaying = false;
    this.isPaused = false;

    // Emit completed event for the client
    this.emit("completed");
  }

  /**
   * Handle daemon process errors
   */
  private handleDaemonError(error: Error): void {
    logger.error("Daemon process error", {
      component: this.name,
      method: "handleDaemonError",
      error: error.message,
      stack: error.stack,
    });

    this.isConnected = false;
    this.emit("error", error);

    // Attempt reconnection
    this.attemptReconnect();
  }

  /**
   * Handle daemon process exit
   */
  private handleDaemonExit(code: number | null, signal: string | null): void {
    logger.consoleInfo("Daemon process exited", {
      component: this.name,
      method: "handleDaemonExit",
      code,
      signal,
      pid: this.daemonProcess?.process.pid,
    });

    this.isConnected = false;
    this.isPlaying = false;
    this.isPaused = false;

    if (this.daemonProcess) {
      this.daemonProcess.isConnected = false;
      this.daemonProcess.healthStatus = "unhealthy";
    }

    this.emit("exit", { code, signal });

    // Attempt reconnection if not a normal exit
    if (code !== 0) {
      this.attemptReconnect();
    }
  }

  /**
   * Attempt to reconnect to daemon
   */
  private async attemptReconnect(): Promise<void> {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      logger.error("Max reconnection attempts reached", {
        component: this.name,
        method: "attemptReconnect",
        attempts: this.reconnectAttempts,
        maxAttempts: this.maxReconnectAttempts,
      });
      return;
    }

    this.reconnectAttempts++;
    logger.consoleInfo("Attempting daemon reconnection", {
      component: this.name,
      method: "attemptReconnect",
      attempt: this.reconnectAttempts,
      maxAttempts: this.maxReconnectAttempts,
    });

    try {
      await this.stopDaemon();
      await new Promise((resolve) => setTimeout(resolve, this.reconnectDelay));
      await this.startDaemon();
      await this.waitForConnection();
      await this.configureAudio();

      this.reconnectAttempts = 0;
      logger.consoleInfo("Daemon reconnection successful", {
        component: this.name,
        method: "attemptReconnect",
      });
    } catch (error) {
      logger.error("Daemon reconnection failed", {
        component: this.name,
        method: "attemptReconnect",
        attempt: this.reconnectAttempts,
        error: error instanceof Error ? error.message : "Unknown error",
      });

      // Exponential backoff
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000);
    }
  }

  /**
   * Stop the daemon process
   */
  private async stopDaemon(): Promise<void> {
    if (!this.daemonProcess) {
      return;
    }

    logger.consoleInfo("Stopping daemon process", {
      component: this.name,
      method: "stopDaemon",
      pid: this.daemonProcess.process.pid,
    });

    try {
      this.daemonProcess.process.kill("SIGTERM");

      // Wait for process to terminate
      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error("Daemon process termination timeout"));
        }, 5000);

        this.daemonProcess!.process.on("exit", () => {
          clearTimeout(timeout);
          resolve();
        });
      });

      logger.consoleInfo("Daemon process stopped", {
        component: this.name,
        method: "stopDaemon",
      });
    } catch (error) {
      logger.error("Failed to stop daemon process", {
        component: this.name,
        method: "stopDaemon",
        error: error instanceof Error ? error.message : "Unknown error",
      });
    } finally {
      this.daemonProcess = null;
      this.isConnected = false;
    }
  }

  /**
   * Calculate streaming efficiency
   */
  private calculateEfficiency(): number {
    if (this.stats.chunksReceived === 0) return 0;

    const expectedBytes = this.stats.chunksReceived * this.stats.averageChunkSize;
    return expectedBytes > 0 ? this.stats.bytesReceived / expectedBytes : 0;
  }

  /**
   * Get streaming statistics
   */
  getStreamingStats(): StreamingStats {
    return { ...this.stats };
  }

  /**
   * Get buffer utilization (delegated to daemon)
   */
  getBufferUtilization(): number {
    // This would be retrieved from daemon status
    return 0.5; // Placeholder
  }

  /**
   * Get the current port being used by the daemon
   */
  getCurrentPort(): number {
    return this.config.port;
  }

  /**
   * Check if daemon is healthy
   */
  isHealthy(): boolean {
    if (!this.daemonProcess) return false;

    const now = Date.now();
    const timeSinceHeartbeat = now - this.daemonProcess.lastHeartbeat;

    return (
      this.daemonProcess.isConnected &&
      timeSinceHeartbeat < this.config.healthCheckTimeout &&
      this.daemonProcess.healthStatus === "healthy"
    );
  }

  /**
   * Clean up resources
   */
  async cleanup(): Promise<void> {
    logger.consoleInfo("Cleaning up audio daemon controller", {
      component: this.name,
      method: "cleanup",
    });

    await this.stop();
    await this.stopDaemon();

    this.removeAllListeners();
    this.reconnectAttempts = 0;
    this.reconnectDelay = 1000;

    logger.consoleInfo("Audio daemon controller cleanup complete", {
      component: this.name,
      method: "cleanup",
    });
  }
}
