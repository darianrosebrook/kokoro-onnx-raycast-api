/**
 * Persistent Audio Daemon Client - Raycast Extension Client
 *
 * This module implements a client that connects to a persistent audio daemon
 * instead of spawning its own daemon process. This approach is more efficient
 * and reduces startup time for each TTS request.
 *
 * ## Architecture Overview
 *
 * The PersistentDaemonClient implements a lightweight client architecture:
 *
 * 1. **Connection Management**: Connects to existing persistent daemon
 * 2. **WebSocket Client**: Communicates with daemon via WebSocket
 * 3. **Session Management**: Manages audio sessions through the daemon
 * 4. **Error Handling**: Implements reconnection logic for reliability
 *
 * ## Key Benefits
 *
 * - **Reduced Startup Time**: No daemon spawning overhead
 * - **Resource Efficiency**: Shared daemon across multiple requests
 * - **Simplified Architecture**: Client only handles communication
 * - **Better Reliability**: Persistent daemon handles audio processing
 *
 * @author @darianrosebrook
 * @version 3.0.0
 * @since 2025-08-17
 * @license MIT
 */

import { EventEmitter } from "events";
import { randomUUID } from "crypto";
import type {
  AudioFormat,
  StreamingStats,
  TTSProcessorConfig,
} from "../../validation/tts-types.js";

// Import WebSocket for client connection
let WebSocket: typeof import("ws").default;

async function loadWebSocket() {
  try {
    const wsModule = await import("ws");
    WebSocket = wsModule.default;
  } catch {
    throw new Error("WebSocket library not available");
  }
}

/**
 * Persistent Audio Daemon Client
 */
export class PersistentDaemonClient extends EventEmitter {
  private ws: WebSocket | null = null;
  private clientId: string;
  private daemonUrl: string;
  private isConnected = false;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private sessionActive = false;
  private audioFormat: AudioFormat | null = null;
  private stats: StreamingStats = {
    bytesSent: 0,
    chunksSent: 0,
    startTime: null,
    endTime: null,
  };

  constructor(daemonUrl = "ws://localhost:8081") {
    super();
    this.clientId = randomUUID();
    this.daemonUrl = daemonUrl;
  }

  /**
   * Connect to the persistent audio daemon
   */
  async connect(): Promise<void> {
    if (this.isConnected) {
      return;
    }

    await loadWebSocket();

    return new Promise((resolve, reject) => {
      try {
        console.log("Connecting to persistent audio daemon", {
          component: "PersistentDaemonClient",
          method: "connect",
          daemonUrl: this.daemonUrl,
          clientId: this.clientId,
        });

        this.ws = new WebSocket(this.daemonUrl);

        this.ws.on("open", () => {
          console.log("Connected to persistent audio daemon", {
            component: "PersistentDaemonClient",
            method: "connect",
            clientId: this.clientId,
          });

          this.isConnected = true;
          this.reconnectAttempts = 0;
          this.emit("connected");
          resolve();
        });

        this.ws.on("message", (data) => {
          this.handleMessage(data);
        });

        this.ws.on("close", (code, reason) => {
          console.log("Disconnected from persistent audio daemon", {
            component: "PersistentDaemonClient",
            method: "connect",
            clientId: this.clientId,
            code,
            reason: reason.toString(),
          });

          this.isConnected = false;
          this.sessionActive = false;
          this.emit("disconnected", { code, reason });

          // Attempt reconnection if not manually closed
          if (code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.attemptReconnect();
          }
        });

        this.ws.on("error", (error) => {
          console.error("WebSocket error", {
            component: "PersistentDaemonClient",
            method: "connect",
            clientId: this.clientId,
            error: error.message,
          });

          this.emit("error", error);
          reject(error);
        });

        // Set connection timeout
        setTimeout(() => {
          if (!this.isConnected) {
            this.ws?.close();
            reject(new Error("Connection timeout"));
          }
        }, 5000);

      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * Attempt to reconnect to the daemon
   */
  private async attemptReconnect(): Promise<void> {
    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

    console.log(`Attempting reconnection ${this.reconnectAttempts}/${this.maxReconnectAttempts}`, {
      component: "PersistentDaemonClient",
      method: "attemptReconnect",
      clientId: this.clientId,
      delay,
    });

    setTimeout(async () => {
      try {
        await this.connect();
      } catch (error) {
        console.error("Reconnection failed", {
          component: "PersistentDaemonClient",
          method: "attemptReconnect",
          clientId: this.clientId,
          error: error instanceof Error ? error.message : "Unknown error",
        });

        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.attemptReconnect();
        } else {
          this.emit("reconnect_failed");
        }
      }
    }, delay);
  }

  /**
   * Handle incoming messages from the daemon
   */
  private handleMessage(data: WebSocket.Data): void {
    try {
      const message = JSON.parse(data.toString());
      console.debug("Received message from daemon", {
        component: "PersistentDaemonClient",
        method: "handleMessage",
        clientId: this.clientId,
        messageType: message.type,
      });

      switch (message.type) {
        case "welcome":
          this.emit("welcome", message);
          break;

        case "session_started":
          this.sessionActive = true;
          this.audioFormat = message.audioFormat;
          this.stats.startTime = Date.now();
          this.emit("session_started", message);
          break;

        case "session_stopped":
          this.sessionActive = false;
          this.stats.endTime = Date.now();
          this.emit("session_stopped", message);
          break;

        case "pong":
          this.emit("pong", message);
          break;

        case "status":
          this.emit("status", message);
          break;

        case "error":
          console.error("Daemon error", {
            component: "PersistentDaemonClient",
            method: "handleMessage",
            clientId: this.clientId,
            error: message.error,
          });
          this.emit("daemon_error", message);
          break;

        default:
          console.warn("Unknown message type", {
            component: "PersistentDaemonClient",
            method: "handleMessage",
            clientId: this.clientId,
            messageType: message.type,
          });
      }
    } catch (error) {
      console.error("Error parsing daemon message", {
        component: "PersistentDaemonClient",
        method: "handleMessage",
        clientId: this.clientId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }

  /**
   * Send a message to the daemon
   */
  private sendMessage(message: any): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket not connected");
    }

    this.ws.send(JSON.stringify(message));
  }

  /**
   * Start an audio session
   */
  startSession(audioFormat: AudioFormat): void {
    if (!this.isConnected) {
      throw new Error("Not connected to daemon");
    }

    console.log("Starting audio session", {
      component: "PersistentDaemonClient",
      method: "startSession",
      clientId: this.clientId,
      audioFormat,
    });

    this.sendMessage({
      type: "start_session",
      audioFormat,
      timestamp: Date.now(),
    });
  }

  /**
   * Send an audio chunk to the daemon
   */
  sendAudioChunk(chunk: Buffer, encoding = "base64"): void {
    if (!this.isConnected || !this.sessionActive) {
      throw new Error("No active session");
    }

    this.stats.bytesSent += chunk.length;
    this.stats.chunksSent++;

    this.sendMessage({
      type: "audio_chunk",
      chunk: chunk.toString(encoding),
      encoding,
      timestamp: Date.now(),
    });
  }

  /**
   * Stop the current audio session
   */
  stopSession(): void {
    if (!this.isConnected) {
      return;
    }

    console.log("Stopping audio session", {
      component: "PersistentDaemonClient",
      method: "stopSession",
      clientId: this.clientId,
    });

    this.sendMessage({
      type: "stop_session",
      timestamp: Date.now(),
    });
  }

  /**
   * Ping the daemon to check connectivity
   */
  ping(): void {
    if (!this.isConnected) {
      return;
    }

    this.sendMessage({
      type: "ping",
      timestamp: Date.now(),
    });
  }

  /**
   * Get status from the daemon
   */
  getStatus(): void {
    if (!this.isConnected) {
      return;
    }

    this.sendMessage({
      type: "get_status",
      timestamp: Date.now(),
    });
  }

  /**
   * Disconnect from the daemon
   */
  disconnect(): void {
    if (this.ws) {
      this.ws.close(1000, "Client disconnecting");
      this.ws = null;
    }

    this.isConnected = false;
    this.sessionActive = false;
    this.emit("disconnected");
  }

  /**
   * Get current connection status
   */
  getConnectionStatus() {
    return {
      isConnected: this.isConnected,
      sessionActive: this.sessionActive,
      clientId: this.clientId,
      daemonUrl: this.daemonUrl,
      reconnectAttempts: this.reconnectAttempts,
      stats: this.stats,
    };
  }

  /**
   * Check if daemon is available
   */
  static async checkDaemonHealth(daemonUrl = "http://localhost:8081"): Promise<boolean> {
    try {
      const response = await fetch(`${daemonUrl}/health`);
      return response.ok;
    } catch {
      return false;
    }
  }

  /**
   * Get daemon status
   */
  static async getDaemonStatus(daemonUrl = "http://localhost:8081"): Promise<any> {
    try {
      const response = await fetch(`${daemonUrl}/status`);
      if (response.ok) {
        return await response.json();
      }
      throw new Error(`HTTP ${response.status}`);
    } catch (error) {
      throw new Error(`Failed to get daemon status: ${error instanceof Error ? error.message : "Unknown error"}`);
    }
  }
}
