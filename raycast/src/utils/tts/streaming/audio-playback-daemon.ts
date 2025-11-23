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
import type {
  AudioFormat,
  StreamingStats,
  TTSProcessorConfig,
} from "../../validation/tts-types.js";
import { environment } from "@raycast/api";
import { randomUUID } from "crypto";

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
} catch {
  // Fallback for environments where fileURLToPath fails
  __filename = process.cwd();
  __dirname = process.cwd();
}

// Import WebSocket for client connection
let WebSocket: typeof import("ws").default;

async function loadWebSocket() {
  try {
    const wsModule = await import("ws");
    WebSocket = wsModule.default;
  } catch {
    console.warn("WebSocket library not available, audio daemon communication will be limited");
  }
}

function findKokoroProjectRoot(startDir: string): string | null {
  console.warn("Starting project root search from:", startDir);
  let currentDir = startDir;
  for (let i = 0; i < 10; i++) {
    // Limit to 10 parent levels
    const markerPath = join(currentDir, ".kokoro-root");
    console.warn(`Level ${i}: Checking ${markerPath}`);
    try {
      if (existsSync(markerPath) && statSync(markerPath).isFile()) {
        console.warn("Found .kokoro-root marker at:", currentDir);
        return currentDir;
      }
    } catch (error) {
      console.warn(`Error checking ${markerPath}:`, error);
    }
    const parentDir = dirname(currentDir);
    if (parentDir === currentDir) {
      console.warn("Reached filesystem root, stopping search");
      break; // Reached filesystem root
    }
    currentDir = parentDir;
  }
  console.warn("No .kokoro-root marker found in any parent directory");
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
    params?: Record<string, unknown>;
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
    nodeExecutable: string;
    port: number;
    bufferSize: number;
    heartbeatInterval: number;
    healthCheckTimeout: number;
    developmentMode: boolean;
  };

  private daemonProcess: AudioDaemonProcess | null = null;
  private ws: InstanceType<typeof import("ws").default> | null = null; // WebSocket client connection
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
  private _statusUpdateCount: number = 0;
  private _waitingForCompletion: boolean = false;

  constructor(config: Partial<TTSProcessorConfig> = {}) {
    super();
    this.instanceId = randomUUID();

    const localDaemonPath = join(environment.supportPath, "audio-daemon.js");

    // Dynamic configuration with safe defaults
    this.config = {
      daemonPath: environment.assetsPath,
      daemonScriptPath: localDaemonPath,
      nodeExecutable: "", // Will be set after detection
      port: config.daemonPort ?? 8081, // Default to persistent daemon port from start scripts
      bufferSize: config.bufferSize ?? 1024 * 512, // 512 KB buffer
      heartbeatInterval: 3000,
      healthCheckTimeout: 10000,
      developmentMode: environment.isDevelopment,
    };

    // --- Daemon Script Path Resolution ---
    let daemonScriptPath: string | null = null;

    // 1) Prefer an already-copied local script in Raycast's support directory
    if (existsSync(localDaemonPath)) {
      daemonScriptPath = localDaemonPath;
    }

    // 2) If env var is provided, honor it and copy into supportPath for stable access
    if (!daemonScriptPath) {
      const envDaemonPath = process.env.KOKORO_AUDIO_DAEMON_PATH;
      if (envDaemonPath && existsSync(envDaemonPath)) {
        try {
          // eslint-disable-next-line @typescript-eslint/no-require-imports
          const fs = require("fs");
          fs.copyFileSync(envDaemonPath, localDaemonPath);
          daemonScriptPath = localDaemonPath;
          console.log("Copied daemon script from KOKORO_AUDIO_DAEMON_PATH", {
            component: this.name,
            method: "constructor",
            envDaemonPath,
            localDaemonPath,
          });
        } catch (copyError) {
          console.warn("Failed to copy daemon script from env path", {
            component: this.name,
            method: "constructor",
            envDaemonPath,
            error: copyError instanceof Error ? copyError.message : "Unknown error",
          });
        }
      }
    }

    // 3) Try pulling it from the packaged assets directory if present
    if (!daemonScriptPath) {
      const assetDaemonPath = join(environment.assetsPath, "audio-daemon.js");
      if (existsSync(assetDaemonPath)) {
        try {
          // eslint-disable-next-line @typescript-eslint/no-require-imports
          const fs = require("fs");
          fs.copyFileSync(assetDaemonPath, localDaemonPath);
          daemonScriptPath = localDaemonPath;
          console.log("Copied daemon script from assets", {
            component: this.name,
            method: "constructor",
            assetDaemonPath,
            localDaemonPath,
          });
        } catch (copyError) {
          console.warn("Failed to copy daemon script from assets", {
            component: this.name,
            method: "constructor",
            error: copyError instanceof Error ? copyError.message : "Unknown error",
          });
        }
      }
    }

    // 4) Development fallback: try to locate the repo via marker/env and copy from raycast/bin
    if (!daemonScriptPath) {
      const projectRoot = findKokoroProjectRoot(process.cwd()) ?? process.env.KOKORO_PROJECT_ROOT;
      if (projectRoot) {
        const sourcePath = join(projectRoot, "raycast/bin/audio-daemon.js");
        if (existsSync(sourcePath)) {
          try {
            // eslint-disable-next-line @typescript-eslint/no-require-imports
            const fs = require("fs");
            fs.copyFileSync(sourcePath, localDaemonPath);
            daemonScriptPath = localDaemonPath;
            console.log("Copied daemon script to extension directory", {
              component: this.name,
              method: "constructor",
              sourcePath,
              localDaemonPath,
            });
          } catch (copyError) {
            console.warn("Failed to copy daemon script from project root", {
              component: this.name,
              method: "constructor",
              error: copyError instanceof Error ? copyError.message : "Unknown error",
            });
          }
        }
      }
    }

    if (!daemonScriptPath) {
      const error = new Error(
        "Audio daemon script not found. Ensure one of the following: 1) set KOKORO_AUDIO_DAEMON_PATH, 2) place audio-daemon.js in raycast/assets, or 3) run raycast/setup-daemon-path.sh."
      );
      console.error("Daemon script resolution failed", {
        component: this.name,
        method: "constructor",
        localDaemonPath,
        assetsPath: environment.assetsPath,
        "process.env.KOKORO_AUDIO_DAEMON_PATH": process.env.KOKORO_AUDIO_DAEMON_PATH,
        "process.env.KOKORO_PROJECT_ROOT": process.env.KOKORO_PROJECT_ROOT,
      });
      throw error;
    }

    this.config.daemonScriptPath = daemonScriptPath;

    // --- Node.js Executable Detection ---
    let nodeExecutable = "";
    const nodePath = process.execPath;

    console.log("Detecting Node.js executable", {
      component: this.name,
      method: "constructor",
      processExecPath: nodePath,
    });

    if (nodePath && typeof nodePath === "string" && existsSync(nodePath)) {
      nodeExecutable = nodePath;
      console.log("Using process.execPath for Node.js", {
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
            console.log("Found Node.js in common location", {
              component: this.name,
              method: "constructor",
              nodeExecutable,
            });
            break;
          }
        } catch (error) {
          console.warn("Error checking Node.js path", {
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
      console.error("Node.js executable not found", {
        component: this.name,
        method: "constructor",
        error: error.message,
      });
      throw error;
    }

    // Store the detected node executable in config
    this.config.nodeExecutable = nodeExecutable;
  }

  /**
   * Initialize the daemon controller
   */
  async initialize(): Promise<void> {
    console.log("Initializing audio daemon controller", {
      component: this.name,
      method: "initialize",
    });

    // Load WebSocket library
    await loadWebSocket();

    try {
      // First, try to connect to existing daemon
      if (await this.tryConnectToExistingDaemon()) {
        console.log("Connected to existing audio daemon", {
          component: this.name,
          method: "initialize",
          port: this.config.port,
        });
        return;
      }

      // If no existing daemon, start our own
      await this.startDaemon();
      await this.waitForConnection();
      await this.configureAudio();

      console.log("Audio daemon controller initialized successfully", {
        component: this.name,
        method: "initialize",
        port: this.config.port,
      });
    } catch (error) {
      // Check if it's a port conflict error
      const errorMessage = error instanceof Error ? error.message : "Unknown error";
      if (errorMessage.includes("EADDRINUSE") || errorMessage.includes("address already in use")) {
        console.warn("Port conflict detected during initialization, attempting to resolve", {
          component: this.name,
          method: "initialize",
          error: errorMessage,
        });

        try {
          await this.handlePortConflict();
          console.log("Successfully resolved port conflict during initialization", {
            component: this.name,
            method: "initialize",
            port: this.config.port,
          });
        } catch (retryError) {
          console.error("Failed to resolve port conflict during initialization", {
            component: this.name,
            method: "initialize",
            originalError: errorMessage,
            retryError: retryError instanceof Error ? retryError.message : "Unknown error",
          });
          throw retryError;
        }
      } else {
        console.error("Failed to initialize audio daemon controller", {
          component: this.name,
          method: "initialize",
          error: errorMessage,
        });
        throw error;
      }
    }
  }

  /**
   * Try to connect to an existing daemon instead of spawning our own
   */
  private async tryConnectToExistingDaemon(): Promise<boolean> {
    console.log("Checking for existing audio daemon", {
      component: this.name,
      method: "tryConnectToExistingDaemon",
      port: this.config.port,
    });

    try {
      // Check if daemon is already running on our port
      const healthUrl = `http://localhost:${this.config.port}/health`;
      const response = await fetch(healthUrl, {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
        signal: AbortSignal.timeout(2000), // 2 second timeout
      });

      if (response.ok) {
        const health = await response.json();
        console.log("Found existing daemon", {
          component: this.name,
          method: "tryConnectToExistingDaemon",
          health: health.status,
        });

        // Create a mock daemon process object for the existing daemon
        this.daemonProcess = {
          process: null as ChildProcess | null, // No process to manage
          port: this.config.port,
          isConnected: false,
          lastHeartbeat: Date.now(),
          healthStatus: "healthy" as const,
        };

        // Mark as connected
        this.daemonProcess.isConnected = true;
        this.isConnected = true;

        // Establish WebSocket connection to existing daemon
        await this.establishWebSocketConnection();

        console.log("Successfully connected to existing daemon", {
          component: this.name,
          method: "tryConnectToExistingDaemon",
          port: this.config.port,
        });

        return true;
      }
    } catch (error) {
      console.log("No existing daemon found, will spawn our own", {
        component: this.name,
        method: "tryConnectToExistingDaemon",
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }

    return false;
  }

  /**
   * Clean up any existing daemon processes that might be using our ports
   */
  private async cleanupExistingDaemons(): Promise<void> {
    console.log("Checking for existing daemon processes", {
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
        console.warn("Found existing daemon processes", {
          component: this.name,
          method: "cleanupExistingDaemons",
          processes: result.stdout.trim(),
        });

        // Kill any existing daemon processes
        await execAsync("pkill -f 'audio-daemon.js'");

        console.log("Cleaned up existing daemon processes", {
          component: this.name,
          method: "cleanupExistingDaemons",
        });

        // Wait a moment for processes to terminate
        await new Promise((resolve) => setTimeout(resolve, 2000));
      }
    } catch (error) {
      // Ignore errors - this is just cleanup
      console.warn("Cleanup check failed (this is normal)", {
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
    console.log("Handling port conflict", {
      component: this.name,
      method: "handlePortConflict",
      currentPort: this.config.port,
    });

    try {
      // Find a new available port
      const newPort = await this.findAvailablePort(this.config.port + 1);

      console.log("Found new available port", {
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

      console.log("Successfully restarted daemon with new port", {
        component: this.name,
        method: "handlePortConflict",
        port: this.config.port,
      });
    } catch (error) {
      console.error("Failed to handle port conflict", {
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
        console.log(`[${this.instanceId}] Port ${currentPort} is available`);
        console.warn("Port available", {
          component: this.name,
          method: "findAvailablePort",
          port: currentPort,
        });
        return currentPort;
      } catch (error) {
        console.log(`[${this.instanceId}] Port ${currentPort} is in use, trying next port`);
        console.warn("Port in use, trying next port", {
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
      console.warn("Daemon process already running", {
        component: this.name,
        method: "startDaemon",
      });
      return;
    }

    // Clean up any existing daemon processes first
    await this.cleanupExistingDaemons();

    // Try to find an available port
    console.warn(
      `[${this.instanceId}] Checking for available port starting from:`,
      this.config.port
    );
    const availablePort = await this.findAvailablePort(this.config.port);
    if (availablePort !== this.config.port) {
      console.log(
        `[${this.instanceId}] Port conflict detected, switching from`,
        this.config.port,
        "to",
        availablePort
      );
      console.log("Port conflict detected, using fallback port", {
        component: this.name,
        method: "startDaemon",
        originalPort: this.config.port,
        fallbackPort: availablePort,
      });
      this.config.port = availablePort;
    } else {
      console.warn(`[${this.instanceId}] Original port ${this.config.port} is available`);
    }

    console.log("Starting audio daemon process", {
      component: this.name,
      method: "startDaemon",
      daemonPath: this.config.daemonPath,
      daemonScriptPath: this.config.daemonScriptPath,
      port: this.config.port,
    });

    try {
      console.warn(`[${this.instanceId}] Spawning daemon process with:`);
      console.warn("  - Node executable:", this.config.nodeExecutable);
      console.warn("  - Daemon script:", this.config.daemonScriptPath);
      console.warn("  - Port:", this.config.port);

      // Determine the working directory for the daemon
      // The daemon needs access to node_modules, so we need to run it from the project root
      const projectRoot = findKokoroProjectRoot(process.cwd()) ?? process.env.KOKORO_PROJECT_ROOT;
      const workingDir = projectRoot || process.cwd();

      console.log("Daemon working directory", {
        component: this.name,
        method: "startDaemon",
        workingDir,
        projectRoot,
        cwd: process.cwd(),
      });

      const daemonProcess = spawn(
        this.config.nodeExecutable,
        [this.config.daemonScriptPath, "--port", this.config.port.toString()],
        {
          stdio: ["ignore", "pipe", "pipe"],
          detached: false,
          cwd: workingDir, // Set working directory to project root
          env: {
            ...process.env,
            NODE_ENV: this.config.developmentMode ? "development" : "production",
          },
        }
      );

      console.log("Daemon process spawned", {
        component: this.name,
        method: "startDaemon",
        pid: daemonProcess.pid,
        port: this.config.port,
      });

      // Set up process event handlers
      daemonProcess.on("error", (error) => {
        console.error(`[${this.instanceId}] Daemon process error:`, error);
        this.handleDaemonError(error);
      });

      daemonProcess.on("exit", (code, signal) => {
        console.log(`[${this.instanceId}] Daemon process exit - code: ${code} signal: ${signal}`);
        this.handleDaemonExit(code, signal);
      });

      // Set up stdout/stderr handlers
      if (daemonProcess.stdout) {
        daemonProcess.stdout.on("data", (data) => {
          const message = data.toString().trim();
          console.warn("Daemon stdout:", message);
          console.warn("Daemon stdout", {
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
          console.warn("Daemon stderr:", message);
          console.warn("Daemon stderr", {
            component: this.name,
            method: "startDaemon",
            pid: daemonProcess.pid,
            message: message,
          });

          // Check for port conflict error
          if (message.includes("EADDRINUSE") || message.includes("address already in use")) {
            console.warn("Port conflict detected in daemon stderr", {
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

      console.log("Daemon process setup complete", {
        component: this.name,
        method: "startDaemon",
        pid: daemonProcess.pid,
      });
    } catch (error) {
      console.error("Failed to start daemon process", {
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

    console.log("Waiting for daemon connection", {
      component: this.name,
      method: "waitForConnection",
      port: this.config.port,
    });

    // Check daemon health endpoint to verify it's ready
    const maxWaitTime = 10000; // 10 seconds
    const startTime = Date.now();
    const healthUrl = `http://localhost:${this.config.port}/health`;

    console.log(`[${this.instanceId}] Checking daemon health at:`, healthUrl);

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
          console.log(`[${this.instanceId}] Daemon health check passed:`, health.status);

          // Mark as connected
          this.daemonProcess.isConnected = true;
          this.isConnected = true;

          // Establish WebSocket connection
          await this.establishWebSocketConnection();

          console.log("Daemon connection established", {
            component: this.name,
            method: "waitForConnection",
            port: this.config.port,
            health: health.status,
          });
          return;
        }
      } catch {
        console.log(`[${this.instanceId}] Daemon not ready yet, retrying...`);
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
    console.log(`[${this.instanceId}] Establishing WebSocket connection to:`, wsUrl);

    return new Promise<void>((resolve, reject) => {
      this.ws = new WebSocket(wsUrl);

      this.ws.on("open", () => {
        console.log(`[${this.instanceId}] WebSocket connection established`);
        console.log("WebSocket connection established", {
          component: this.name,
          method: "establishWebSocketConnection",
          url: wsUrl,
        });
        resolve();
      });

      this.ws.on("error", (error: Error) => {
        console.log(`[${this.instanceId}] WebSocket connection error:`, error);
        console.error("WebSocket connection error", {
          component: this.name,
          method: "establishWebSocketConnection",
          error: error.message,
        });
        reject(error);
      });

      this.ws.on("close", (code: number, reason: string) => {
        console.log(
          `[${this.instanceId}] WebSocket connection closed - code: ${code} reason: ${reason}`
        );
        console.warn("WebSocket connection closed", {
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
          // Only log non-heartbeat messages to reduce noise
          if (message.type !== "heartbeat") {
            console.log(`[${this.instanceId}] Received message from daemon:`, message.type);
          }
          this.handleIncomingMessage(message);
        } catch (error) {
          console.log(
            `[${this.instanceId}] Failed to parse WebSocket message:`,
            error instanceof Error ? error.message : String(error)
          );
          console.error("Failed to parse WebSocket message", {
            component: this.name,
            method: "establishWebSocketConnection",
            error: error instanceof Error ? error.message : String(error),
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
    console.log("Configuring audio settings", {
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

    console.log("Audio configuration sent to daemon", {
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

    console.log("Starting audio playback", {
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

    console.log("Audio playback started", {
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

    console.warn("Writing audio chunk to daemon", {
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

    console.warn("Audio chunk sent to daemon", {
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
      console.warn("Cannot end stream - daemon not connected", {
        component: this.name,
        method: "endStream",
      });
      return;
    }

    console.log("Ending audio stream", {
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
    console.log("End stream message sent to daemon, waiting for completion", {
      component: this.name,
      method: "endStream",
      totalChunks: this.stats.chunksReceived,
      totalBytes: this.stats.bytesReceived,
    });

    // Wait for the audio to finish playing naturally
    // The daemon will send a "completed" event when audio finishes
    const waitStartTime = Date.now();
    await this.waitForAudioCompletion();
    const waitDuration = Date.now() - waitStartTime;

    console.log("Audio completion wait finished", {
      component: this.name,
      method: "endStream",
      waitDuration: `${waitDuration}ms`,
    });

    // Update stats
    this.stats.streamingDuration = Date.now() - (this.stats.streamingDuration || Date.now());
    this.stats.efficiency = this.calculateEfficiency();

    console.log("Audio stream ended", {
      component: this.name,
      method: "endStream",
      streamingDuration: this.stats.streamingDuration,
      efficiency: this.stats.efficiency,
      waitDuration: `${waitDuration}ms`,
    });
  }

  /**
   * Wait for audio playback to complete naturally
   */
  private async waitForAudioCompletion(): Promise<void> {
    return new Promise((resolve, reject) => {
      console.log("Waiting for audio completion", {
        component: this.name,
        method: "waitForAudioCompletion",
        isPlaying: this.isPlaying,
        isConnected: this.daemonProcess?.isConnected,
        totalBytes: this.stats.bytesReceived,
        expectedDuration: this.stats.bytesReceived > 0 
          ? `${(this.stats.bytesReceived / 48000).toFixed(1)}s` 
          : "unknown",
      });

      // Mark that we're waiting for completion (used by status update handler)
      this._waitingForCompletion = true;

      const waitStartTime = Date.now();

      // Calculate expected audio duration + buffer
      // For 24kHz mono 16-bit PCM: bytesPerSecond = 24000 * 2 = 48000
      const expectedDurationMs = this.stats.bytesReceived > 0 
        ? (this.stats.bytesReceived / 48000) * 1000  // bytes / bytesPerSecond * 1000
        : 0;
      // Add generous buffer: expected duration + 5 seconds, minimum 15 seconds, maximum 120 seconds
      const timeoutDuration = Math.min(
        Math.max(expectedDurationMs + 5000, 15000),
        120000
      );

      console.log("Audio completion timeout configured", {
        component: this.name,
        method: "waitForAudioCompletion",
        expectedDurationMs: expectedDurationMs.toFixed(0),
        timeoutDuration: timeoutDuration.toFixed(0),
        totalBytes: this.stats.bytesReceived,
      });

      const timeout = setTimeout(() => {
        const elapsed = Date.now() - waitStartTime;
        console.warn("Audio completion timeout - forcing stop", {
          component: this.name,
          method: "waitForAudioCompletion",
          elapsed: `${(elapsed / 1000).toFixed(1)}s`,
          expectedDuration: expectedDurationMs > 0 ? `${(expectedDurationMs / 1000).toFixed(1)}s` : "unknown",
        });
        this._waitingForCompletion = false;
        // Force stop if timeout occurs
        this.forceStop();
        resolve();
      }, timeoutDuration);

      // Add periodic progress logging
      const progressInterval = setInterval(() => {
        const elapsed = Date.now() - waitStartTime;
        const remaining = Math.max(0, timeoutDuration - elapsed);
        console.log("Still waiting for audio completion", {
          component: this.name,
          method: "waitForAudioCompletion",
          isPlaying: this.isPlaying,
          isConnected: this.daemonProcess?.isConnected,
          totalBytes: this.stats.bytesReceived,
          expectedDuration: expectedDurationMs > 0 ? `${(expectedDurationMs / 1000).toFixed(1)}s` : "unknown",
          elapsed: `${(elapsed / 1000).toFixed(1)}s`,
          timeoutIn: `${(remaining / 1000).toFixed(1)}s`,
        });
      }, 10000); // Log every 10 seconds

      const onCompleted = () => {
        clearTimeout(timeout);
        clearInterval(progressInterval);
        this._waitingForCompletion = false;
        this.removeListener("completed", onCompleted);
        this.removeListener("error", onError);
        console.log("Audio completion event received", {
          component: this.name,
          method: "waitForAudioCompletion",
        });
        resolve();
      };

      const onError = (error: Error) => {
        clearTimeout(timeout);
        clearInterval(progressInterval);
        this.removeListener("completed", onCompleted);
        this.removeListener("error", onError);
        console.warn("Audio completion error", {
          component: this.name,
          method: "waitForAudioCompletion",
          error: error.message,
        });
        reject(error);
      };

      // CRITICAL FIX: Set up listeners FIRST to avoid race condition
      // If completion happens between check and listener setup, we'll catch it
      this.once("completed", onCompleted);
      this.once("error", onError);

      // Check if already completed AFTER setting up listeners
      // This ensures we don't miss a completion that happens during setup
      // Note: We check isPlaying OR connection status - if not playing but connected,
      // we should still wait for the daemon to signal completion
      if (!this.isPlaying && !this.daemonProcess?.isConnected) {
        console.log("Already completed (not playing and not connected)", {
          component: this.name,
          method: "waitForAudioCompletion",
        });
        clearTimeout(timeout);
        clearInterval(progressInterval);
        resolve();
      }
    });
  }

  /**
   * Force stop the audio playback (used as fallback)
   */
  private async forceStop(): Promise<void> {
    console.warn("Forcing audio playback stop", {
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
      console.warn("Cannot pause - daemon not connected", {
        component: this.name,
        method: "pause",
      });
      return;
    }

    console.log("Pausing audio playback", {
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

    console.log("Audio playback paused", {
      component: this.name,
      method: "pause",
    });
  }

  /**
   * Resume audio playback
   */
  async resume(): Promise<void> {
    if (!this.daemonProcess?.isConnected) {
      console.warn("Cannot resume - daemon not connected", {
        component: this.name,
        method: "resume",
      });
      return;
    }

    console.log("Resuming audio playback", {
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

    console.log("Audio playback resumed", {
      component: this.name,
      method: "resume",
    });
  }

  /**
   * Stop audio playback
   */
  async stop(): Promise<void> {
    console.log("Stopping audio playback", {
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

    console.log("Audio playback stopped", {
      component: this.name,
      method: "stop",
    });
  }

  /**
   * Send message to daemon via WebSocket
   */
  private async sendMessage(message: DaemonMessage): Promise<void> {
    // Auto-reconnect if daemon is not connected
    if (!this.daemonProcess?.isConnected || !this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.log("WebSocket not connected, attempting to reconnect...");
      try {
        await this.startDaemon();
        await this.establishWebSocketConnection();
        // Give connection a moment to establish
        await new Promise((resolve) => setTimeout(resolve, 100));
      } catch (error) {
        throw new Error(
          `Failed to reconnect to daemon: ${error instanceof Error ? error.message : "Unknown error"}`
        );
      }
    }

    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket connection could not be established");
    }

    console.warn("Sending message to daemon", {
      component: this.name,
      method: "sendMessage",
      messageType: message.type,
      timestamp: message.timestamp,
    });

    // Serialize the message to JSON
    const messageJson = JSON.stringify(message);
    console.warn("Sending message to daemon:", message.type);

    this.ws.send(messageJson);
  }

  /**
   * Handle incoming messages from the daemon
   */
  private handleIncomingMessage(message: DaemonMessage): void {
    switch (message.type) {
      case "audio_chunk": {
        const audioChunk = message as AudioChunkMessage;
        this.handleAudioChunk(audioChunk);
        break;
      }
      case "status": {
        const status = message as DaemonMessage; // Assuming status messages are just status updates
        this.handleStatusUpdate(status);
        break;
      }
      case "heartbeat": {
        const _heartbeat = message as DaemonMessage;
        // this.handleHeartbeat(_heartbeat);
        break;
      }
      case "completed": {
        const completed = message as DaemonMessage;
        this.handleCompleted(completed);
        break;
      }
      case "error": {
        const error = message as DaemonMessage;
        // Handle both legacy string format and new object format
        const errorMessage =
          typeof error.data === "string"
            ? error.data
            : ((error.data as { message: string })?.message ?? "Unknown daemon error");
        this.handleDaemonError(new Error(errorMessage));
        break;
      }
      default:
        console.warn("Received unknown message type from daemon", {
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
    console.warn("Handling audio chunk message", {
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
    // Extract state from status message
    const statusData = message.data as { state?: string; bufferUtilization?: number } | undefined;
    const state = statusData?.state;
    const bufferUtilization = statusData?.bufferUtilization ?? 0;

    // CRITICAL: Always log status updates when waiting for completion (for debugging)
    if (this._waitingForCompletion) {
      console.log("Status update received while waiting for completion", {
        component: this.name,
        method: "handleStatusUpdate",
        state,
        bufferUtilization,
        isPlaying: this.isPlaying,
        waitingForCompletion: this._waitingForCompletion,
        messageData: JSON.stringify(statusData).substring(0, 200),
      });
    }

    // CRITICAL FIX: Update isPlaying based on daemon status
    // This helps detect completion when the daemon reports "idle" state
    if (state === "idle" || state === "completed") {
      if (this.isPlaying) {
        console.log("Daemon reported idle/completed state - updating isPlaying", {
          component: this.name,
          method: "handleStatusUpdate",
          previousState: this.isPlaying,
          newState: false,
          bufferUtilization,
        });
        this.isPlaying = false;

        // CRITICAL FIX: If we're waiting for completion and daemon reports idle with empty buffer,
        // treat this as completion (fallback for when completion event doesn't arrive)
        // Also check if bufferUtilization is very low (< 0.01) to account for floating point precision
        if (this._waitingForCompletion && (bufferUtilization === 0 || bufferUtilization < 0.01)) {
          console.log("Completion fallback: daemon idle + empty buffer while waiting - emitting completion", {
            component: this.name,
            method: "handleStatusUpdate",
            state,
            bufferUtilization,
            waitingForCompletion: this._waitingForCompletion,
          });
          // Emit completion event as fallback
          this._waitingForCompletion = false;
          this.emit("completed");
        }
      } else if (this._waitingForCompletion && (bufferUtilization === 0 || bufferUtilization < 0.01)) {
        // Even if isPlaying was already false, if we're waiting and buffer is empty, complete
        console.log("Completion fallback: already idle + empty buffer while waiting - emitting completion", {
          component: this.name,
          method: "handleStatusUpdate",
          state,
          bufferUtilization,
          waitingForCompletion: this._waitingForCompletion,
        });
        this._waitingForCompletion = false;
        this.emit("completed");
      }
    } else if (state === "playing") {
      this.isPlaying = true;
    }

    // Log status updates periodically for debugging (when not waiting)
    if (!this._waitingForCompletion) {
      if (!this._statusUpdateCount) {
        this._statusUpdateCount = 0;
      }
      this._statusUpdateCount++;
      if (this._statusUpdateCount % 10 === 0) {
        console.log("Status update received", {
          component: this.name,
          method: "handleStatusUpdate",
          state,
          bufferUtilization,
          isPlaying: this.isPlaying,
          waitingForCompletion: this._waitingForCompletion,
        });
      }
    }
  }

  /**
   * Handle heartbeat messages from the daemon
   */
  private handleHeartbeat(message: DaemonMessage): void {
    console.warn("Handling heartbeat message", {
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
    console.log("Audio playback completed naturally", {
      component: this.name,
      method: "handleCompleted",
      timestamp: message.timestamp,
      waitingForCompletion: this._waitingForCompletion,
    });

    this.isPlaying = false;
    this.isPaused = false;
    this._waitingForCompletion = false;

    // Emit completed event for the client
    console.log("Emitting 'completed' event to listeners", {
      component: this.name,
      method: "handleCompleted",
      listenerCount: this.listenerCount("completed"),
    });
    this.emit("completed");
    console.log("'completed' event emitted", {
      component: this.name,
      method: "handleCompleted",
    });
  }

  /**
   * Handle daemon process errors
   */
  private handleDaemonError(error: Error): void {
    console.error("Daemon process error", {
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
    console.log("Daemon process exited", {
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
      console.error("Max reconnection attempts reached", {
        component: this.name,
        method: "attemptReconnect",
        attempts: this.reconnectAttempts,
        maxAttempts: this.maxReconnectAttempts,
      });
      return;
    }

    this.reconnectAttempts++;
    console.log("Attempting daemon reconnection", {
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
      console.log("Daemon reconnection successful", {
        component: this.name,
        method: "attemptReconnect",
      });
    } catch (error) {
      console.error("Daemon reconnection failed", {
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

    console.log("Stopping daemon process", {
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

      console.log("Daemon process stopped", {
        component: this.name,
        method: "stopDaemon",
      });
    } catch (error) {
      console.error("Failed to stop daemon process", {
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
    console.log("Cleaning up audio daemon controller", {
      component: this.name,
      method: "cleanup",
    });

    await this.stop();
    await this.stopDaemon();

    this.removeAllListeners();
    this.reconnectAttempts = 0;
    this.reconnectDelay = 1000;

    console.log("Audio daemon controller cleanup complete", {
      component: this.name,
      method: "cleanup",
    });
  }
}
