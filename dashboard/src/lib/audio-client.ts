/**
 * Audio Client for Dashboard TTS Integration
 *
 * Handles WebSocket communication with the audio daemon for real-time
 * audio streaming and visualization, mirroring the Raycast audio integration.
 *
 * @author @darianrosebrook
 */

// Browser-compatible EventEmitter implementation
class BrowserEventEmitter {
  private events: { [key: string]: Function[] } = {};

  on(event: string, listener: Function): void {
    if (!this.events[event]) {
      this.events[event] = [];
    }
    this.events[event].push(listener);
  }

  off(event: string, listener: Function): void {
    if (!this.events[event]) return;
    this.events[event] = this.events[event].filter((l) => l !== listener);
  }

  emit(event: string, ...args: any[]): void {
    if (!this.events[event]) return;
    this.events[event].forEach((listener) => listener(...args));
  }
}

export interface AudioFormat {
  format: string;
  sampleRate: number;
  channels: number;
  bitDepth: number;
}

export interface TTSRequest {
  text: string;
  voice: string;
  speed: number;
  format: string;
  stream?: boolean;
}

export interface AudioChunk {
  data: Uint8Array;
  index: number;
  timestamp: number;
  duration?: number;
}

export interface AudioStatus {
  isPlaying: boolean;
  isPaused: boolean;
  bufferUtilization: number;
  audioPosition: number;
  performance?: {
    timing?: {
      expectedDuration: number;
      actualDuration: number;
      accuracy: string;
      processingOverhead: string;
      totalChunks: number;
      averageChunkSize: string;
      firstChunkTime: number;
      lastChunkTime: number;
    };
  };
}

export interface AudioMessage {
  type: string;
  timestamp: number;
  data: any;
}

export interface StreamingStats {
  chunksReceived: number;
  bytesReceived: number;
  streamingDuration: number;
  timeToFirstAudio: number;
  averageChunkSize: number;
  efficiency: number;
  underruns: number;
}

/**
 * Audio Client for dashboard communication with audio daemon
 * Mirrors the functionality from raycast/src/utils/tts/streaming/audio-playback-daemon.ts
 */
export class AudioClient extends BrowserEventEmitter {
  private ws: WebSocket | null = null;
  private url: string;
  private connected: boolean = false;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 5;
  private reconnectDelay: number = 1000;
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private sequenceNumber: number = 0;

  // Audio streaming state
  private currentRequest: TTSRequest | null = null;
  private serverUrl: string = "http://localhost:8000";
  private streamingStats: StreamingStats = {
    chunksReceived: 0,
    bytesReceived: 0,
    streamingDuration: 0,
    timeToFirstAudio: 0,
    averageChunkSize: 0,
    efficiency: 0,
    underruns: 0,
  };

  constructor(daemonUrl: string, serverUrl?: string) {
    super();
    this.url = daemonUrl;
    if (serverUrl) {
      this.serverUrl = serverUrl;
    }
  }

  /**
   * Connect to the audio daemon WebSocket
   */
  async connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        console.log("[AudioClient] Attempting connection to:", this.url);
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
          console.log("[AudioClient] ✅ Connected to audio daemon");
          this.connected = true;
          this.reconnectAttempts = 0;
          this.startHeartbeat();
          this.emit("connected");
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const message: AudioMessage = JSON.parse(event.data);
            this.handleMessage(message);
          } catch (error) {
            console.error("[AudioClient] Failed to parse message:", error);
          }
        };

        this.ws.onclose = () => {
          console.log("[AudioClient] Disconnected from audio daemon");
          this.connected = false;
          this.stopHeartbeat();
          this.emit("disconnected");

          // Attempt reconnection
          if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            setTimeout(() => {
              console.log(
                `[AudioClient] Reconnection attempt ${this.reconnectAttempts}`
              );
              this.connect().catch(console.error);
            }, this.reconnectDelay * this.reconnectAttempts);
          }
        };

        this.ws.onerror = (error) => {
          console.error("[AudioClient]  WebSocket error:", error);
          console.error("[AudioClient] Connection URL was:", this.url);
          console.error("[AudioClient] Error details:", {
            type: error.type,
            target: error.target,
            readyState: this.ws?.readyState,
          });
          this.emit("error", {
            data: { message: "WebSocket connection error" },
          });
          reject(new Error("Failed to connect to audio daemon"));
        };

        // Timeout for connection
        setTimeout(() => {
          if (!this.connected) {
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
   * Disconnect from the audio daemon
   */
  disconnect(): void {
    this.stopHeartbeat();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.connected = false;
  }

  /**
   * Send TTS request and handle streaming
   */
  async sendTTSRequest(request: TTSRequest): Promise<void> {
    if (!this.connected || !this.ws) {
      throw new Error("Not connected to audio daemon");
    }

    this.currentRequest = request;
    this.resetStreamingStats();

    console.log("[AudioClient] Sending TTS request:", {
      text:
        request.text.substring(0, 100) +
        (request.text.length > 100 ? "..." : ""),
      voice: request.voice,
      speed: request.speed,
      format: request.format,
    });

    try {
      // Send request to TTS server and stream to daemon
      await this.streamAudioToTTS(request);
    } catch (error) {
      console.error("[AudioClient] TTS request failed:", error);
      throw error;
    }
  }

  /**
   * Stream audio from TTS server to audio daemon
   */
  private async streamAudioToTTS(request: TTSRequest): Promise<void> {
    const streamingRequest = {
      ...request,
      stream: true,
      format: "pcm", // Use PCM for streaming
    };

    const url = `${this.serverUrl}/v1/audio/speech`;
    const requestStartTime = performance.now();

    console.log("[AudioClient] Sending request to TTS server:", url);

    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "audio/pcm",
      },
      body: JSON.stringify(streamingRequest),
    });

    if (!response.ok) {
      throw new Error(`TTS request failed: ${response.statusText}`);
    }

    if (!response.body) {
      throw new Error("No response body");
    }

    const reader = response.body.getReader();
    let chunkIndex = 0;
    let firstChunk = true;
    let totalBytes = 0;

    try {
      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          console.log(
            "[AudioClient] Stream ended, sending end_stream to daemon"
          );
          await this.sendMessage({
            type: "end_stream",
            timestamp: Date.now(),
            data: {},
          });
          break;
        }

        if (value && value.length > 0) {
          const currentTime = Date.now();
          totalBytes += value.length;

          if (firstChunk) {
            const ttfa = performance.now() - requestStartTime;
            console.log(
              "[AudioClient] Time to First Audio (TTFA):",
              ttfa.toFixed(2) + "ms"
            );
            this.streamingStats.timeToFirstAudio = ttfa;
            firstChunk = false;
          }

          // Send chunk to audio daemon
          await this.sendMessage({
            type: "audio_chunk",
            timestamp: currentTime,
            data: {
              chunk: value,
              format: {
                format: "pcm",
                sampleRate: 24000,
                channels: 1,
                bitDepth: 16,
              },
              sequence: this.sequenceNumber++,
            },
          });

          // Update streaming stats
          this.streamingStats.chunksReceived++;
          this.streamingStats.bytesReceived = totalBytes;
          this.streamingStats.averageChunkSize =
            totalBytes / this.streamingStats.chunksReceived;

          // Emit chunk event for visualization
          this.emit("chunk", {
            data: value,
            index: chunkIndex++,
            timestamp: currentTime,
          });

          console.log(
            `[AudioClient] Sent chunk ${chunkIndex} (${value.length} bytes) to daemon`
          );
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  /**
   * Send message to audio daemon
   */
  private async sendMessage(message: any): Promise<void> {
    if (!this.ws || !this.connected) {
      throw new Error("Not connected to audio daemon");
    }

    this.ws.send(JSON.stringify(message));
  }

  /**
   * Handle incoming messages from audio daemon
   */
  private handleMessage(message: AudioMessage): void {
    switch (message.type) {
      case "status":
        this.emit("status", message);
        break;
      case "completed":
        console.log("[AudioClient] Audio playback completed");
        this.emit("completed", message);
        break;
      case "error":
        console.error("[AudioClient] Audio daemon error:", message.data);
        this.emit("error", message);
        break;
      case "heartbeat":
        // Heartbeat response, no action needed
        break;
      case "timing_analysis":
        this.emit("timing_analysis", message);
        break;
      default:
        console.log("[AudioClient] Unknown message type:", message.type);
    }
  }

  /**
   * Start heartbeat monitoring
   */
  private startHeartbeat(): void {
    this.heartbeatInterval = setInterval(() => {
      if (this.connected && this.ws) {
        this.sendMessage({
          type: "heartbeat",
          timestamp: Date.now(),
          data: {},
        }).catch(console.error);
      }
    }, 5000);
  }

  /**
   * Stop heartbeat monitoring
   */
  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  /**
   * Reset streaming statistics
   */
  private resetStreamingStats(): void {
    this.streamingStats = {
      chunksReceived: 0,
      bytesReceived: 0,
      streamingDuration: 0,
      timeToFirstAudio: 0,
      averageChunkSize: 0,
      efficiency: 0,
      underruns: 0,
    };
  }

  /**
   * Control methods
   */
  stop(): void {
    if (this.connected && this.ws) {
      this.sendMessage({
        type: "control",
        timestamp: Date.now(),
        data: { action: "stop" },
      }).catch(console.error);
    }
  }

  pause(): void {
    if (this.connected && this.ws) {
      this.sendMessage({
        type: "control",
        timestamp: Date.now(),
        data: { action: "pause" },
      }).catch(console.error);
    }
  }

  resume(): void {
    if (this.connected && this.ws) {
      this.sendMessage({
        type: "control",
        timestamp: Date.now(),
        data: { action: "resume" },
      }).catch(console.error);
    }
  }

  /**
   * Get current streaming statistics
   */
  getStreamingStats(): StreamingStats {
    return { ...this.streamingStats };
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.connected;
  }
}
