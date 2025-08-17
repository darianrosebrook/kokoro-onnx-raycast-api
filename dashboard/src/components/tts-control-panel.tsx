/**
 * TTS Control Panel Component
 *
 * Interactive control panel for testing TTS functionality with real-time
 * audio streaming visualization, similar to the Raycast speak-selection
 * functionality but in a web interface.
 *
 * @author @darianrosebrook
 */

"use client";

import React, { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import {
  AudioClient,
  AudioStatus,
  AudioMessage,
  TTSRequest,
  StreamingStats,
  AudioChunk,
} from "@/lib/audio-client";
import {
  AudioVisualizer,
  AudioVisualizerRef,
} from "@/components/charts/audio-visualizer";

interface ConnectionStatus {
  connected: boolean;
  connecting: boolean;
  error: string | null;
}

interface TTSState {
  isPlaying: boolean;
  isPaused: boolean;
  currentText: string;
  voice: string;
  speed: number;
}

const VOICE_OPTIONS = [
  { value: "af_heart", label: "AF Heart" },
  { value: "af_sky", label: "AF Sky" },
  { value: "af_bella", label: "AF Bella" },
  { value: "af_sarah", label: "AF Sarah" },
  { value: "am_adam", label: "AM Adam" },
  { value: "am_michael", label: "AM Michael" },
];

const SPEED_OPTIONS = [
  { value: 0.5, label: "0.5x (Slow)" },
  { value: 0.75, label: "0.75x" },
  { value: 1.0, label: "1.0x (Normal)" },
  { value: 1.25, label: "1.25x" },
  { value: 1.5, label: "1.5x (Fast)" },
  { value: 2.0, label: "2.0x (Very Fast)" },
];

export function TTSControlPanel() {
  const audioClientRef = useRef<AudioClient | null>(null);
  const visualizerRef = useRef<AudioVisualizerRef | null>(null);

  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>({
    connected: false,
    connecting: false,
    error: null,
  });

  const [ttsState, setTtsState] = useState<TTSState>({
    isPlaying: false,
    isPaused: false,
    currentText:
      "Hello! This is a test of the Kokoro TTS system. You can type any text here and hear it spoken with real-time audio streaming.",
    voice: "af_heart",
    speed: 1.0,
  });

  const [audioStatus, setAudioStatus] = useState<AudioStatus | null>(null);
  const [streamingStats, setStreamingStats] = useState<StreamingStats>({
    chunksReceived: 0,
    bytesReceived: 0,
    streamingDuration: 0,
    timeToFirstAudio: 0,
    averageChunkSize: 0,
    efficiency: 0,
    underruns: 0,
  });

  const [sessionStats, setSessionStats] = useState({
    startTime: 0,
    firstChunkTime: 0,
    lastChunkTime: 0,
    totalChunks: 0,
  });

  /**
   * Initialize audio client and connection
   */
  useEffect(() => {
    const audioClient = new AudioClient("ws://localhost:8081");
    audioClientRef.current = audioClient;

    // Set up event listeners
    audioClient.on("status", (message: AudioMessage) => {
      setAudioStatus(message.data);
    });

    audioClient.on("completed", (message: AudioMessage) => {
      console.log("[TTSControlPanel] Audio playback completed");
      setTtsState((prev) => ({
        ...prev,
        isPlaying: false,
        isPaused: false,
      }));
    });

    audioClient.on("error", (message: AudioMessage) => {
      console.error("[TTSControlPanel] Audio error:", message.data);
      setConnectionStatus((prev) => ({
        ...prev,
        error: message.data.message || "Audio playback error",
      }));
    });

    audioClient.on("timing_analysis", (message: AudioMessage) => {
      console.log("[TTSControlPanel] Timing analysis:", message.data);
    });

    // Handle real-time audio chunks for visualization
    audioClient.on("chunk", (chunk: AudioChunk) => {
      console.log("[TTSControlPanel] Received audio chunk:", {
        index: chunk.index,
        size: chunk.data.length,
        timestamp: chunk.timestamp,
      });

      // Update session stats
      setSessionStats((prev) => {
        const now = Date.now();
        return {
          ...prev,
          firstChunkTime: prev.firstChunkTime || now,
          lastChunkTime: now,
          totalChunks: chunk.index + 1,
        };
      });

      // Update streaming stats
      setStreamingStats((prev) => ({
        ...prev,
        chunksReceived: chunk.index + 1,
        bytesReceived: prev.bytesReceived + chunk.data.length,
        averageChunkSize:
          (prev.bytesReceived + chunk.data.length) / (chunk.index + 1),
        streamingDuration:
          sessionStats.startTime > 0 ? Date.now() - sessionStats.startTime : 0,
      }));

      // Send to visualizer
      if (visualizerRef.current) {
        visualizerRef.current.processAudioChunk(chunk);
      }
    });

    // Initial connection
    connectToAudioDaemon();

    return () => {
      audioClient.disconnect();
    };
  }, []);

  /**
   * Connect to audio daemon
   */
  const connectToAudioDaemon = async () => {
    if (!audioClientRef.current) return;

    setConnectionStatus((prev) => ({ ...prev, connecting: true, error: null }));

    try {
      await audioClientRef.current.connect();
      setConnectionStatus({
        connected: true,
        connecting: false,
        error: null,
      });
    } catch (error) {
      console.error("[TTSControlPanel] Connection failed:", error);
      setConnectionStatus({
        connected: false,
        connecting: false,
        error: error instanceof Error ? error.message : "Connection failed",
      });
    }
  };

  /**
   * Start TTS playback
   */
  const startTTS = async () => {
    if (!audioClientRef.current || !connectionStatus.connected) {
      console.error("[TTSControlPanel] Audio client not connected");
      return;
    }

    if (!ttsState.currentText.trim()) {
      console.error("[TTSControlPanel] No text to speak");
      return;
    }

    try {
      setTtsState((prev) => ({ ...prev, isPlaying: true, isPaused: false }));
      setSessionStats({
        startTime: Date.now(),
        firstChunkTime: 0,
        lastChunkTime: 0,
        totalChunks: 0,
      });

      // Clear visualizer
      if (visualizerRef.current) {
        visualizerRef.current.clearWaveform();
      }

      const request: TTSRequest = {
        text: ttsState.currentText,
        voice: ttsState.voice,
        speed: ttsState.speed,
        format: "pcm",
      };

      // This will stream directly to the audio daemon
      await audioClientRef.current.sendTTSRequest(request);

      console.log("[TTSControlPanel] TTS request sent successfully");
    } catch (error) {
      console.error("[TTSControlPanel] TTS failed:", error);
      setTtsState((prev) => ({ ...prev, isPlaying: false, isPaused: false }));
      setConnectionStatus((prev) => ({
        ...prev,
        error: error instanceof Error ? error.message : "TTS request failed",
      }));
    }
  };

  /**
   * Stop TTS playback
   */
  const stopTTS = () => {
    if (audioClientRef.current) {
      audioClientRef.current.stop();
    }
    setTtsState((prev) => ({ ...prev, isPlaying: false, isPaused: false }));
  };

  /**
   * Pause TTS playback
   */
  const pauseTTS = () => {
    if (audioClientRef.current) {
      audioClientRef.current.pause();
    }
    setTtsState((prev) => ({ ...prev, isPaused: true }));
  };

  /**
   * Resume TTS playback
   */
  const resumeTTS = () => {
    if (audioClientRef.current) {
      audioClientRef.current.resume();
    }
    setTtsState((prev) => ({ ...prev, isPaused: false }));
  };

  /**
   * Update streaming stats from audio status messages
   */
  useEffect(() => {
    if (!audioClientRef.current) return;

    const updateFromStatus = (message: AudioMessage) => {
      if (message.data.performance?.timing) {
        const timing = message.data.performance.timing;
        setStreamingStats((prev) => ({
          ...prev,
          timeToFirstAudio:
            timing.firstChunkTime && sessionStats.startTime
              ? timing.firstChunkTime - sessionStats.startTime
              : prev.timeToFirstAudio,
        }));
      }
    };

    audioClientRef.current.on("status", updateFromStatus);

    return () => {
      if (audioClientRef.current) {
        audioClientRef.current.off("status", updateFromStatus);
      }
    };
  }, [sessionStats.startTime]);

  return (
    <div className="space-y-6">
      {/* Connection Status */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Audio Daemon Connection</CardTitle>
            <div className="flex items-center gap-2">
              {connectionStatus.connected ? (
                <Badge
                  variant="secondary"
                  className="bg-green-500/10 text-green-500"
                >
                  Connected
                </Badge>
              ) : connectionStatus.connecting ? (
                <Badge
                  variant="secondary"
                  className="bg-yellow-500/10 text-yellow-500"
                >
                  Connecting...
                </Badge>
              ) : (
                <Badge variant="destructive">Disconnected</Badge>
              )}
              {!connectionStatus.connected && (
                <Button
                  size="sm"
                  onClick={connectToAudioDaemon}
                  disabled={connectionStatus.connecting}
                >
                  Connect
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        {connectionStatus.error && (
          <CardContent>
            <div className="text-sm text-red-500">
              Error: {connectionStatus.error}
            </div>
          </CardContent>
        )}
      </Card>

      {/* TTS Controls */}
      <Card>
        <CardHeader>
          <CardTitle>Text-to-Speech Controls</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Text Input */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Text to speak</label>
            <textarea
              value={ttsState.currentText}
              onChange={(e) =>
                setTtsState((prev) => ({
                  ...prev,
                  currentText: e.target.value,
                }))
              }
              placeholder="Enter text to speak..."
              className="w-full h-24 px-3 py-2 border border-border rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-ring"
              disabled={ttsState.isPlaying}
            />
          </div>

          {/* Voice and Speed Controls */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Voice</label>
              <Select
                value={ttsState.voice}
                onValueChange={(value) =>
                  setTtsState((prev) => ({ ...prev, voice: value }))
                }
                disabled={ttsState.isPlaying}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {VOICE_OPTIONS.map((voice) => (
                    <SelectItem key={voice.value} value={voice.value}>
                      {voice.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Speed</label>
              <Select
                value={ttsState.speed.toString()}
                onValueChange={(value) =>
                  setTtsState((prev) => ({ ...prev, speed: parseFloat(value) }))
                }
                disabled={ttsState.isPlaying}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SPEED_OPTIONS.map((speed) => (
                    <SelectItem
                      key={speed.value}
                      value={speed.value.toString()}
                    >
                      {speed.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Playback Controls */}
          <div className="flex items-center gap-2">
            {!ttsState.isPlaying ? (
              <Button
                onClick={startTTS}
                disabled={
                  !connectionStatus.connected || !ttsState.currentText.trim()
                }
              >
                ▶ Speak
              </Button>
            ) : (
              <>
                {ttsState.isPaused ? (
                  <Button onClick={resumeTTS}>▶ Resume</Button>
                ) : (
                  <Button onClick={pauseTTS}>⏸ Pause</Button>
                )}
                <Button variant="outline" onClick={stopTTS}>
                  ⏹ Stop
                </Button>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Audio Visualizer */}
      <Card>
        <CardHeader>
          <CardTitle>Real-time Audio Stream</CardTitle>
        </CardHeader>
        <CardContent>
          <AudioVisualizer
            ref={visualizerRef}
            width={800}
            height={200}
            maxSamples={1000}
            showTimestamp={true}
          />
        </CardContent>
      </Card>

      {/* Streaming Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Performance Metrics</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">
                Time to First Audio:
              </span>
              <span className="text-sm font-mono">
                {streamingStats.timeToFirstAudio > 0
                  ? `${streamingStats.timeToFirstAudio.toFixed(0)}ms`
                  : "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">
                Chunks Received:
              </span>
              <span className="text-sm font-mono">
                {streamingStats.chunksReceived}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">
                Bytes Received:
              </span>
              <span className="text-sm font-mono">
                {streamingStats.bytesReceived > 0
                  ? `${(streamingStats.bytesReceived / 1024).toFixed(1)} KB`
                  : "0 B"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">
                Streaming Duration:
              </span>
              <span className="text-sm font-mono">
                {streamingStats.streamingDuration > 0
                  ? `${streamingStats.streamingDuration.toFixed(0)}ms`
                  : "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">
                Buffer Underruns:
              </span>
              <span className="text-sm font-mono">
                {streamingStats.underruns}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Audio Status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">
                Playback State:
              </span>
              <span className="text-sm font-mono">
                {ttsState.isPlaying
                  ? ttsState.isPaused
                    ? "Paused"
                    : "Playing"
                  : "Stopped"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">
                Buffer Utilization:
              </span>
              <span className="text-sm font-mono">
                {audioStatus?.bufferUtilization
                  ? `${(audioStatus.bufferUtilization * 100).toFixed(1)}%`
                  : "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">
                Audio Position:
              </span>
              <span className="text-sm font-mono">
                {audioStatus?.audioPosition
                  ? `${(audioStatus.audioPosition / 1000).toFixed(1)}s`
                  : "—"}
              </span>
            </div>
            {audioStatus?.performance?.timing?.accuracy && (
              <div className="flex justify-between">
                <span className="text-sm text-muted-foreground">
                  Timing Accuracy:
                </span>
                <span className="text-sm font-mono">
                  {audioStatus.performance.timing.accuracy}
                </span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
