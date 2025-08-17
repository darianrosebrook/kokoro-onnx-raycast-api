/**
 * Audio Visualizer Component
 *
 * Real-time audio waveform visualization with timestamps, inspired by the
 * Raycast audio streaming implementation. Shows audio chunks as they arrive
 * with timing information.
 *
 * @author @darianrosebrook
 */

"use client";

import React, {
  useRef,
  useEffect,
  forwardRef,
  useImperativeHandle,
} from "react";

export interface AudioChunk {
  data: Uint8Array;
  index: number;
  timestamp: number;
  duration?: number;
}

export interface AudioVisualizerProps {
  width: number;
  height: number;
  maxSamples?: number;
  showTimestamp?: boolean;
  backgroundColor?: string;
  waveformColor?: string;
  timestampColor?: string;
  gridColor?: string;
}

export interface AudioVisualizerRef {
  processAudioChunk: (chunk: AudioChunk) => void;
  clearWaveform: () => void;
  getStats: () => VisualizerStats;
}

interface VisualizerStats {
  totalChunks: number;
  totalSamples: number;
  averageAmplitude: number;
  peakAmplitude: number;
  duration: number;
}

interface WaveformPoint {
  x: number;
  y: number;
  amplitude: number;
  timestamp: number;
  chunkIndex: number;
  sampleIndex: number;
  audioTime: number; // Actual audio timeline position
}

/**
 * Audio Visualizer Component for real-time waveform display
 */
export const AudioVisualizer = forwardRef<
  AudioVisualizerRef,
  AudioVisualizerProps
>(
  (
    {
      width,
      height,
      maxSamples = 1000,
      showTimestamp = true,
      backgroundColor = "#000000",
      waveformColor = "#00ff00",
      timestampColor = "#ffffff",
      gridColor = "#333333",
    },
    ref
  ) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const animationFrameRef = useRef<number | undefined>(undefined);

    // Waveform data with temporal ordering
    const waveformPoints = useRef<WaveformPoint[]>([]);
    const audioStartTime = useRef<number>(0);
    const currentAudioTime = useRef<number>(0);
    const chunkBuffer = useRef<Map<number, AudioChunk>>(new Map());
    const stats = useRef<VisualizerStats>({
      totalChunks: 0,
      totalSamples: 0,
      averageAmplitude: 0,
      peakAmplitude: 0,
      duration: 0,
    });

    // Audio processing parameters
    const SAMPLE_RATE = 24000; // PCM sample rate from Kokoro TTS
    const CHANNELS = 1; // Mono audio
    const BYTES_PER_SAMPLE = 2; // 16-bit audio

    /**
     * Process incoming audio chunk and add to waveform
     */
    const processAudioChunk = (chunk: AudioChunk) => {
      if (!chunk.data || chunk.data.length === 0) return;

      // Initialize audio timeline on first chunk
      if (audioStartTime.current === 0) {
        audioStartTime.current = performance.now();
      }

      // Store chunk in buffer for ordered processing
      chunkBuffer.current.set(chunk.index, chunk);

      // Process chunks in order
      processOrderedChunks();
    };

    /**
     * Process chunks in chronological order to ensure smooth visualization
     */
    const processOrderedChunks = () => {
      const sortedChunks = Array.from(chunkBuffer.current.entries()).sort(
        ([a], [b]) => a - b
      );

      for (const [chunkIndex, chunk] of sortedChunks) {
        if (chunk && !isChunkProcessed(chunkIndex)) {
          addChunkToWaveform(chunk);
          // Mark as processed by removing from buffer
          chunkBuffer.current.delete(chunkIndex);
        }
      }
    };

    /**
     * Check if chunk has already been processed
     */
    const isChunkProcessed = (chunkIndex: number): boolean => {
      return waveformPoints.current.some(
        (point) => point.chunkIndex === chunkIndex
      );
    };

    /**
     * Add a chunk to the waveform using proper temporal positioning
     */
    const addChunkToWaveform = (chunk: AudioChunk) => {
      // Convert PCM data to amplitude values
      const samples = convertPCMToAmplitudes(chunk.data);

      // Calculate actual audio time for this chunk
      const chunkDurationMs = (samples.length / SAMPLE_RATE) * 1000;
      const chunkStartTime = currentAudioTime.current;
      const sampleSpacing = chunkDurationMs / samples.length;

      // Add samples to waveform points with proper temporal positioning
      const newPoints: WaveformPoint[] = [];
      for (
        let i = 0;
        i < samples.length;
        i += Math.max(1, Math.floor(samples.length / 50))
      ) {
        const audioTime = chunkStartTime + i * sampleSpacing;
        const x = (audioTime / 10000) * width; // Scale time to canvas width (10 seconds visible)
        const amplitude = samples[i];
        const y = height / 2 + amplitude * height * 0.4; // Scale amplitude to canvas height

        newPoints.push({
          x,
          y,
          amplitude: Math.abs(amplitude),
          timestamp: chunk.timestamp,
          chunkIndex: chunk.index,
          sampleIndex: i,
          audioTime,
        });

        // Update stats
        stats.current.totalSamples++;
        stats.current.peakAmplitude = Math.max(
          stats.current.peakAmplitude,
          Math.abs(amplitude)
        );
      }

      // Insert points in chronological order
      insertPointsInOrder(newPoints);

      // Update current audio time
      currentAudioTime.current += chunkDurationMs;

      // Update chunk stats
      stats.current.totalChunks++;
      stats.current.duration = currentAudioTime.current;

      // Calculate average amplitude
      if (stats.current.totalSamples > 0) {
        const totalAmplitude = waveformPoints.current.reduce(
          (sum, point) => sum + point.amplitude,
          0
        );
        stats.current.averageAmplitude =
          totalAmplitude / waveformPoints.current.length;
      }

      console.log(`[AudioVisualizer] Processed chunk ${chunk.index}:`, {
        chunkSize: chunk.data.length,
        samples: samples.length,
        points: waveformPoints.current.length,
        peakAmplitude: stats.current.peakAmplitude.toFixed(3),
      });
    };

    /**
     * Convert PCM data to normalized amplitude values
     */
    const convertPCMToAmplitudes = (pcmData: Uint8Array): number[] => {
      const samples: number[] = [];

      // Treat as 16-bit signed integers (little-endian)
      for (let i = 0; i < pcmData.length - 1; i += 2) {
        const sample = pcmData[i] | (pcmData[i + 1] << 8);
        // Convert from unsigned to signed 16-bit
        const signedSample = sample > 32767 ? sample - 65536 : sample;
        // Normalize to [-1, 1]
        const normalizedSample = signedSample / 32768;
        samples.push(normalizedSample);
      }

      return samples;
    };

    /**
     * Insert points in chronological order to maintain temporal continuity
     */
    const insertPointsInOrder = (newPoints: WaveformPoint[]) => {
      // Add new points to the array
      waveformPoints.current.push(...newPoints);

      // Sort by audio time to maintain temporal order
      waveformPoints.current.sort((a, b) => a.audioTime - b.audioTime);

      // Limit number of points for performance
      if (waveformPoints.current.length > maxSamples) {
        const excess = waveformPoints.current.length - maxSamples;
        waveformPoints.current.splice(0, excess);
      }
    };

    /**
     * Clear the waveform display
     */
    const clearWaveform = () => {
      waveformPoints.current = [];
      audioStartTime.current = 0;
      currentAudioTime.current = 0;
      chunkBuffer.current.clear();
      stats.current = {
        totalChunks: 0,
        totalSamples: 0,
        averageAmplitude: 0,
        peakAmplitude: 0,
        duration: 0,
      };

      // Clear canvas and redraw with baseline
      const canvas = canvasRef.current;
      if (canvas) {
        const ctx = canvas.getContext("2d");
        if (ctx) {
          ctx.clearRect(0, 0, width, height);
          drawBackground(ctx);
          drawWaveform(ctx); // This will now draw just the baseline
        }
      }
    };

    /**
     * Get current visualizer statistics
     */
    const getStats = (): VisualizerStats => {
      return { ...stats.current };
    };

    /**
     * Draw background grid and labels
     */
    const drawBackground = (ctx: CanvasRenderingContext2D) => {
      ctx.fillStyle = backgroundColor;
      ctx.fillRect(0, 0, width, height);

      // Draw grid lines
      ctx.strokeStyle = gridColor;
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 2]);

      // Horizontal center line
      ctx.beginPath();
      ctx.moveTo(0, height / 2);
      ctx.lineTo(width, height / 2);
      ctx.stroke();

      // Vertical time lines (every 1 second)
      const timeScale = width / 10000; // 10 seconds visible
      for (let t = 0; t <= 10000; t += 1000) {
        const x = t * timeScale;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }

      ctx.setLineDash([]);

      // Draw amplitude scale
      ctx.fillStyle = timestampColor;
      ctx.font = "10px monospace";
      ctx.textAlign = "left";
      ctx.fillText("+1.0", 5, 15);
      ctx.fillText("0.0", 5, height / 2 + 5);
      ctx.fillText("-1.0", 5, height - 5);

      // Draw time scale
      if (showTimestamp) {
        ctx.textAlign = "center";
        for (let t = 0; t <= 10; t += 1) {
          const x = t * 1000 * timeScale;
          ctx.fillText(`${t}s`, x, height - 5);
        }
      }
    };

    /**
     * Draw the waveform with smooth interpolation
     */
    const drawWaveform = (ctx: CanvasRenderingContext2D) => {
      // Always draw a baseline at center (y = height/2)
      const centerY = height / 2;

      // Draw baseline when no data or between chunks
      ctx.strokeStyle = "#555555"; // Slightly brighter than grid for baseline
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 4]);
      ctx.beginPath();
      ctx.moveTo(0, centerY);
      ctx.lineTo(width, centerY);
      ctx.stroke();
      ctx.setLineDash([]);

      if (waveformPoints.current.length < 2) {
        // No waveform data - just show the baseline
        return;
      }

      // Draw waveform line with smooth curves
      ctx.strokeStyle = waveformColor;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([]);
      ctx.lineCap = "round";
      ctx.lineJoin = "round";

      ctx.beginPath();
      const firstPoint = waveformPoints.current[0];
      ctx.moveTo(firstPoint.x, firstPoint.y);

      // Use quadratic curves for smoother line rendering
      for (let i = 1; i < waveformPoints.current.length - 1; i++) {
        const current = waveformPoints.current[i];
        const next = waveformPoints.current[i + 1];

        // Calculate control point for smooth curve
        const xMid = (current.x + next.x) / 2;
        const yMid = (current.y + next.y) / 2;

        ctx.quadraticCurveTo(current.x, current.y, xMid, yMid);
      }

      // Handle the last point
      if (waveformPoints.current.length > 1) {
        const lastPoint =
          waveformPoints.current[waveformPoints.current.length - 1];
        ctx.lineTo(lastPoint.x, lastPoint.y);

        // Extend to baseline if there's space
        if (lastPoint.x < width) {
          ctx.lineTo(width, centerY);
        }
      }

      ctx.stroke();

      // Draw chunk markers with better visibility
      if (showTimestamp) {
        drawChunkMarkers(ctx);
      }
    };

    /**
     * Draw chunk markers with improved visibility
     */
    const drawChunkMarkers = (ctx: CanvasRenderingContext2D) => {
      ctx.fillStyle = timestampColor;
      ctx.font = "8px monospace";
      ctx.textAlign = "center";

      const chunkMarkers = new Map<number, WaveformPoint>();
      waveformPoints.current.forEach((point) => {
        if (!chunkMarkers.has(point.chunkIndex)) {
          chunkMarkers.set(point.chunkIndex, point);
        }
      });

      chunkMarkers.forEach((point, chunkIndex) => {
        // Draw chunk index marker with background
        const text = `C${chunkIndex}`;
        const metrics = ctx.measureText(text);
        const padding = 2;

        // Background
        ctx.fillStyle = "rgba(0, 0, 0, 0.7)";
        ctx.fillRect(
          point.x - metrics.width / 2 - padding,
          2,
          metrics.width + padding * 2,
          12
        );

        // Text
        ctx.fillStyle = timestampColor;
        ctx.fillText(text, point.x, 12);

        // Draw subtle vertical line for chunk boundary
        ctx.strokeStyle = "rgba(102, 102, 102, 0.5)";
        ctx.lineWidth = 1;
        ctx.setLineDash([2, 2]);
        ctx.beginPath();
        ctx.moveTo(point.x, 20);
        ctx.lineTo(point.x, height - 5);
        ctx.stroke();
        ctx.setLineDash([]);
      });
    };

    /**
     * Main render function
     */
    const renderFrame = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;

      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      // Clear and draw background
      drawBackground(ctx);

      // Draw waveform
      drawWaveform(ctx);

      // Draw stats overlay
      if (stats.current.totalChunks > 0) {
        ctx.fillStyle = "rgba(0, 0, 0, 0.7)";
        ctx.fillRect(width - 200, 5, 190, 70);

        ctx.fillStyle = timestampColor;
        ctx.font = "10px monospace";
        ctx.textAlign = "left";
        ctx.fillText(`Chunks: ${stats.current.totalChunks}`, width - 195, 20);
        ctx.fillText(`Samples: ${stats.current.totalSamples}`, width - 195, 35);
        ctx.fillText(
          `Peak: ${stats.current.peakAmplitude.toFixed(3)}`,
          width - 195,
          50
        );
        ctx.fillText(
          `Duration: ${(stats.current.duration / 1000).toFixed(1)}s`,
          width - 195,
          65
        );
      }
    };

    /**
     * Start the render loop
     */
    useEffect(() => {
      const canvas = canvasRef.current;
      if (!canvas) return;

      // Set canvas size with device pixel ratio for crisp rendering
      const dpr = window.devicePixelRatio || 1;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;

      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.scale(dpr, dpr);
      }

      // Start render loop
      const startRenderLoop = () => {
        renderFrame();
        animationFrameRef.current = requestAnimationFrame(startRenderLoop);
      };
      startRenderLoop();

      return () => {
        if (animationFrameRef.current) {
          cancelAnimationFrame(animationFrameRef.current);
        }
      };
    }, [width, height]);

    // Expose methods through ref
    useImperativeHandle(ref, () => ({
      processAudioChunk,
      clearWaveform,
      getStats,
    }));

    return (
      <div className="relative">
        <canvas
          ref={canvasRef}
          width={width}
          height={height}
          className="border border-border rounded-md bg-black"
          style={{ width: `${width}px`, height: `${height}px` }}
        />
        {waveformPoints.current.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
            <div className="text-center">
              <div className="text-sm mb-1">Waiting for audio stream...</div>
              <div className="text-xs opacity-70">
                Baseline at 0.0 amplitude
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }
);

AudioVisualizer.displayName = "AudioVisualizer";
