/**
 * Shared Type Definitions for Raycast Kokoro TTS
 *
 * This module provides centralized type definitions used across all TTS modules
 * to ensure consistent typing and prevent circular dependencies.
 *
 * Features:
 * - Core TTS interfaces and types
 * - Performance monitoring types
 * - State management types
 * - Error handling types
 * - Streaming and playback types
 *
 * @author @darianrosebrook
 * @version 1.0.0
 * @since 2025-01-20
 */

import type { Toast } from "@raycast/api";
import type { ChildProcess } from "child_process";

export type VoiceOption =
  // American English
  | "af_heart"
  | "af_alloy"
  | "af_aoede"
  | "af_bella"
  | "af_jessica"
  | "af_kore"
  | "af_nicole"
  | "af_nova"
  | "af_river"
  | "af_sarah"
  | "af_sky"
  | "am_adam"
  | "am_echo"
  | "am_eric"
  | "am_fenrir"
  | "am_liam"
  | "am_michael"
  | "am_onyx"
  | "am_puck"
  | "am_santa"
  // British English
  | "bf_alice"
  | "bf_emma"
  | "bf_isabella"
  | "bf_lily"
  | "bm_daniel"
  | "bm_fable"
  | "bm_george"
  | "bm_lewis"
  // Japanese
  | "jf_alpha"
  | "jf_gongitsune"
  | "jf_nezumi"
  | "jf_tebukuro"
  | "jm_kumo"
  // Mandarin Chinese
  | "zf_xiaobei"
  | "zf_xiaoni"
  | "zf_xiaoxiao"
  | "zf_xiaoyi"
  | "zm_yunjian"
  | "zm_yunxi"
  | "zm_yunxia"
  | "zm_yunyang"
  // Spanish
  | "ef_dora"
  | "em_alex"
  | "em_santa"
  // French
  | "ff_siwis"
  // Hindi
  | "hf_alpha"
  | "hf_beta"
  | "hm_omega"
  | "hm_psi"
  // Italian
  | "if_sara"
  | "im_nicola"
  // Brazilian Portuguese
  | "pf_dora"
  | "pm_alex"
  | "pm_santa";

/**
 * Status update information for UI feedback
 */
export interface StatusUpdate {
  message: string;
  style?: Toast.Style;
  isPlaying: boolean;
  isPaused: boolean;
  primaryAction?: {
    title: string;
    onAction: () => void;
  };
  secondaryAction?: {
    title: string;
    onAction: () => void;
  };
}

/**
 * TTS processor configuration
 */
export interface TTSProcessorConfig {
  voice: VoiceOption;
  speed: number;
  serverUrl: string;
  useStreaming: boolean;
  sentencePauses: boolean;
  maxSentenceLength: number;
  format: "wav" | "pcm";
  developmentMode: boolean;
  onStatusUpdate: (status: StatusUpdate) => void;
}

/**
 * TTS request parameters
 */
export interface TTSRequestParams {
  text: string;
  voice: VoiceOption;
  speed: number;
  lang: string;
  stream: boolean;
  format: "wav" | "pcm";
}

/**
 * Audio chunk information
 */
export interface AudioChunk {
  data: Uint8Array;
  index: number;
  timestamp: number;
  duration?: number;
}

/**
 * Streaming context for audio processing
 */
export interface StreamingContext {
  requestId: string;
  segments: string[];
  currentSegmentIndex: number;
  totalSegments: number;
  abortController: AbortController;
  startTime: number;
}

/**
 * Performance metrics for individual operations
 */
export interface PerformanceMetrics {
  sessionStart: number;
  requestStart: number;
  timeToFirstByte: number;
  timeToFirstAudio: number;
  streamingEfficiency: number;
  bufferAdjustments: number;
  totalSegments: number;
  completedSegments: number;
  cacheHits: number;
  cacheMisses: number;
  adaptiveBufferMs: number;
  averageLatency: number;
  underrunCount: number;
  streamingSuccesses: number;
  streamingFailures: number;
  fallbackSuccesses: number;
  completeFailures: number;
}

/**
 * Buffer management configuration
 */
export interface BufferConfig {
  minBufferMs: number;
  targetBufferMs: number;
  maxBufferMs: number;
  sampleRate: number;
  channels: number;
  bytesPerSample: number;
}

/**
 * Text processing configuration
 */
export interface TextProcessingConfig {
  maxChunkSize: number;
  preservePunctuation: boolean;
  enablePreprocessing: boolean;
  sentencePauses: boolean;
  maxSentenceLength: number;
}

/**
 * Audio format specifications
 */
export interface AudioFormat {
  format: "wav" | "pcm";
  sampleRate: number;
  channels: number;
  bitDepth: number;
  bytesPerSample: number;
  bytesPerSecond: number;
}

/**
 * Playback state information
 */
export interface PlaybackState {
  isPlaying: boolean;
  isPaused: boolean;
  isStopped: boolean;
  currentSegment: number;
  totalSegments: number;
  currentProcess: ChildProcess; // ChildProcess type
  pausePromise: Promise<void> | null;
  pauseResolve: (() => void) | null;
}

/**
 * Retry configuration for error handling
 */
export interface RetryConfig {
  maxAttempts: number;
  baseDelayMs: number;
  maxDelayMs: number;
  retryCondition: (error: Error) => boolean;
  retryableErrors?: string[];
  nonRetryableErrors?: string[];
}

/**
 * Retry strategy configuration
 */
export interface RetryStrategy {
  maxRetries?: number;
  baseDelay?: number;
  maxDelay?: number;
  backoffMultiplier?: number;
  jitterFactor?: number;
  retryableErrors?: string[];
  nonRetryableErrors?: string[];
}

/**
 * Retry result information
 */
export interface RetryResult<T> {
  success: boolean;
  data: T | null;
  error: Error | null;
  attempts: unknown[];
  metrics: RetryMetrics;
  circuitBreakerOpen: boolean;
}

/**
 * Retry error classification
 */
export interface RetryError {
  type: "network" | "server" | "client" | "rate_limit" | "timeout" | "connection" | "unknown";
  retryable: boolean;
  priority: "low" | "medium" | "high";
  message?: string;
}

/**
 * Retry metrics for monitoring
 */
export interface RetryMetrics {
  totalAttempts: number;
  successfulRetries: number;
  failedRetries: number;
  totalRetryTime: number;
  averageRetryDelay: number;
  circuitBreakerTrips: number;
}

/**
 * Network request context
 */
export interface NetworkContext {
  url: string;
  method: string;
  headers: Record<string, string>;
  body?: string;
  timeout: number;
  signal: AbortSignal;
}

/**
 * Cache entry metadata
 */
export interface CacheEntry {
  key: string;
  data: ArrayBuffer;
  timestamp: number;
  size: number;
  ttl: number;
  voice: VoiceOption;
  speed: number;
  format: string;
}

/**
 * Error context information
 */
export interface ErrorContext {
  component: string;
  method: string;
  requestId?: string;
  voice?: VoiceOption;
  textLength?: number;
  error: Error;
  timestamp: number;
  retryAttempt?: number;
}

/**
 * Streaming statistics
 */
export interface StreamingStats {
  chunksReceived: number;
  bytesReceived: number;
  averageChunkSize: number;
  streamingDuration: number;
  efficiency: number;
  underruns: number;
  bufferHealth: number;
  totalAudioDuration: number; // Add missing property for Phase 1 optimization
}

/**
 * Text segment information
 */
export interface TextSegment {
  text: string;
  index: number;
  startOffset: number;
  endOffset: number;
  type: "paragraph" | "sentence" | "chunk";
  processed: boolean;
}

/**
 * Audio playback context
 */
export interface PlaybackContext {
  audioData: Uint8Array;
  format: AudioFormat;
  metadata: {
    voice: VoiceOption;
    speed: number;
    duration?: number;
    size: number;
  };
  playbackOptions: {
    volume?: number;
    useHardwareAcceleration: boolean;
    backgroundPlayback: boolean;
  };
}

/**
 * Module interface for TTS components
 */
export interface TTSModule {
  name: string;
  version: string;
  initialize(config: Partial<TTSProcessorConfig>): Promise<void>;
  cleanup(): Promise<void>;
  isInitialized(): boolean;
}

/**
 * Text processor interface
 */
export interface ITextProcessor extends TTSModule {
  preprocessText(text: string): string;
  segmentText(text: string, maxLength: number): TextSegment[];
  validateText(text: string): { isValid: boolean; errors: string[] };
}

/**
 * Audio streamer interface
 */
export interface IAudioStreamer extends TTSModule {
  streamAudio(
    request: TTSRequestParams,
    context: StreamingContext,
    onChunk: (chunk: AudioChunk) => void
  ): Promise<void>;
  getStreamingStats(): StreamingStats;
  adjustBuffer(metrics: PerformanceMetrics): number;
}

/**
 * Playback manager interface
 */
export interface IPlaybackManager extends TTSModule {
  playAudio(context: PlaybackContext, signal: AbortSignal): Promise<void>;
  pause(): void;
  resume(): void;
  stop(): Promise<void>;
  getPlaybackState(): PlaybackState;
  // PHASE 1 OPTIMIZATION: Add streaming playback method
  startStreamingPlayback(signal: AbortSignal): Promise<{
    writeChunk: (chunk: Uint8Array) => Promise<void>;
    endStream: () => Promise<void>;
  }>;
}

/**
 * Performance monitor interface
 */
export interface IPerformanceMonitor extends TTSModule {
  startTracking(requestId: string): void;
  recordMetric(metric: string, value: number): void;
  endTracking(requestId: string): PerformanceMetrics;
  getMetrics(): PerformanceMetrics;
  logPerformanceReport(): void;
}

/**
 * Retry manager interface
 */
export interface IRetryManager {
  retryWithBackoff<T>(
    operation: () => Promise<T>,
    config: RetryConfig,
    context?: ErrorContext
  ): Promise<T>;
  shouldRetry(error: Error, attempt: number): boolean;
  executeWithRetry<T>(
    operation: () => Promise<T>,
    context: string,
    customConfig?: Partial<RetryConfig>
  ): Promise<RetryResult<T>>;
  executeWithStrategy<T>(
    operation: () => Promise<T>,
    strategy: RetryStrategy,
    context: string
  ): Promise<RetryResult<T>>;
  getRetryMetrics(): RetryMetrics;
  resetMetrics(): void;
  getCircuitBreakerState(): unknown;
  resetCircuitBreaker(): void;
  updateConfig(config: Partial<RetryConfig>): void;
  getConfig(): RetryConfig;
  logRetryStats(): void;
}

/**
 * Network conditions for adaptive buffering
 */
export interface NetworkConditions {
  latency: number;
  bandwidth: number;
  packetLoss: number;
  timestamp: number;
}

/**
 * Buffer health assessment
 */
export interface BufferHealth {
  score: number;
  status: "healthy" | "degraded" | "poor";
  issues: string[];
  recommendations: string[];
}

/**
 * Adaptive buffer manager interface
 */
export interface IAdaptiveBufferManager extends TTSModule {
  updateBuffer(metrics: PerformanceMetrics, networkConditions?: NetworkConditions): BufferConfig;
  getBufferConfig(): BufferConfig;
  getBufferHealth(metrics: PerformanceMetrics): BufferHealth;
  predictOptimalBuffer(networkConditions: NetworkConditions): number;
  estimateBandwidth(): number;
  getNetworkConditions(): NetworkConditions;
  updateStrategy(strategy: unknown): void;
  getStrategy(): unknown;
  resetToDefaults(): void;
  getAdaptationStats(): unknown;
  logBufferStats(): void;
}

/**
 * Event types for TTS processor
 */
export enum TTSEvent {
  REQUEST_START = "request_start",
  REQUEST_COMPLETE = "request_complete",
  REQUEST_ERROR = "request_error",
  SEGMENT_START = "segment_start",
  SEGMENT_COMPLETE = "segment_complete",
  AUDIO_CHUNK = "audio_chunk",
  PLAYBACK_START = "playback_start",
  PLAYBACK_COMPLETE = "playback_complete",
  PLAYBACK_PAUSE = "playback_pause",
  PLAYBACK_RESUME = "playback_resume",
  PLAYBACK_STOP = "playback_stop",
  BUFFER_ADJUSTMENT = "buffer_adjustment",
  CACHE_HIT = "cache_hit",
  CACHE_MISS = "cache_miss",
  RETRY_ATTEMPT = "retry_attempt",
  PERFORMANCE_REPORT = "performance_report",
  STREAMING_STARTED = "streaming_started",
  STREAMING_COMPLETED = "streaming_completed",
  STREAMING_ERROR = "streaming_error",
  STREAMING_PAUSED = "streaming_paused",
  STREAMING_RESUMED = "streaming_resumed",
  STREAMING_STOPPED = "streaming_stopped",
  STREAMING_BUFFER_ADJUSTMENT = "streaming_buffer_adjustment",
}

/**
 * Event data for TTS processor events
 */
export interface TTSEventData {
  event: TTSEvent;
  timestamp: number;
  requestId?: string;
  data?: unknown;
  error?: Error;
}

/**
 * Constants for TTS processing
 */
export const TTS_CONSTANTS = {
  // Server limits
  MAX_TEXT_LENGTH: 1800,
  MAX_CHUNK_SIZE: 2000,

  // Audio format (Kokoro ONNX)
  SAMPLE_RATE: 24000,
  CHANNELS: 1,
  BIT_DEPTH: 16,
  BYTES_PER_SAMPLE: 2,

  // Buffer configuration
  MIN_BUFFER_MS: 200,
  TARGET_BUFFER_MS: 400,
  MAX_BUFFER_MS: 1000,

  // Performance targets
  TARGET_TTFA_MS: 800,
  TARGET_EFFICIENCY: 0.9,

  // Retry configuration
  MAX_RETRY_ATTEMPTS: 3,
  BASE_RETRY_DELAY_MS: 500,
  MAX_RETRY_DELAY_MS: 5000,

  // Cache configuration
  CACHE_TTL_MS: 30 * 60 * 1000, // 30 minutes
  MAX_CACHE_SIZE: 50 * 1024 * 1024, // 50MB

  // Timeout configuration
  NETWORK_TIMEOUT_MS: 30000,
  HEALTH_CHECK_TIMEOUT_MS: 5000,
} as const;

/**
 * Utility type for making properties optional
 */
export type PartialBy<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;

/**
 * Utility type for making properties required
 */
export type RequiredBy<T, K extends keyof T> = Omit<T, K> & Required<Pick<T, K>>;

/**
 * Type guard for checking if an object is a valid TTS request
 */
export function isTTSRequest(obj: unknown): obj is TTSRequestParams {
  return (
    typeof obj === "object" &&
    obj !== null &&
    "text" in obj &&
    "voice" in obj &&
    "speed" in obj &&
    typeof (obj as TTSRequestParams).text === "string" &&
    typeof (obj as TTSRequestParams).voice === "string" &&
    typeof (obj as TTSRequestParams).speed === "number"
  );
}

/**
 * Type guard for checking if an object is a valid audio chunk
 */
export function isAudioChunk(obj: unknown): obj is AudioChunk {
  return (
    typeof obj === "object" &&
    obj !== null &&
    "data" in obj &&
    "index" in obj &&
    "timestamp" in obj &&
    obj.data instanceof Uint8Array
  );
}

/**
 * Type guard for checking if an error is retryable
 */
export function isRetryableError(error: Error): boolean {
  const retryablePatterns = [
    /network/i,
    /timeout/i,
    /connection/i,
    /econnreset/i,
    /enotfound/i,
    /5\d{2}/i, // 5xx HTTP errors
  ];

  return retryablePatterns.some(
    (pattern) => pattern.test(error.message) || pattern.test(error.name)
  );
}
