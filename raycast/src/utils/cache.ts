/**
 * Enhanced Caching System for Raycast Kokoro TTS
 *
 * This module implements high-performance caching using LRU (Least Recently Used)
 * algorithm to optimize TTS response times and reduce server load.
 *
 * Features:
 * - LRU cache for TTS audio responses
 * - Persistent preference caching
 * - Automatic cache cleanup and TTL management
 * - Thread-safe operations
 * - Memory-efficient storage
 *
 * @author @darianrosebrook
 * @version 1.0.0
 * @since 2025-01-20
 */

import { LRUCache } from "lru-cache";
import { createHash } from "crypto";
import type { TTSRequest, TTSConfig, VoiceOption } from "../types";

/**
 * Configuration for different cache types
 */
interface CacheConfig {
  max?: number;
  maxSize?: number;
  ttl: number; // Time to live in milliseconds
  updateAgeOnGet: boolean;
  updateAgeOnHas: boolean;
  sizeCalculation?: (value: unknown, key: string) => number;
}

/**
 * Default cache configurations optimized for different use cases
 */
const CACHE_CONFIGS = {
  // TTS responses - larger cache with size-based eviction for audio data
  ttsResponse: {
    maxSize: 50 * 1024 * 1024, // 50MB total cache size
    ttl: 1800000, // 30 minutes
    updateAgeOnGet: true,
    updateAgeOnHas: true,
    sizeCalculation: (value: unknown) => (value as CachedTTSResponse).size,
  } as CacheConfig,

  // Server health checks - smaller cache with count-based eviction
  serverHealth: {
    max: 10, // Maximum 10 entries
    ttl: 60000, // 1 minute
    updateAgeOnGet: true,
    updateAgeOnHas: false,
  } as CacheConfig,

  // Voice configurations - count-based cache since voices are small
  voiceConfig: {
    max: 50, // Maximum 50 entries
    ttl: 3600000, // 1 hour
    updateAgeOnGet: false,
    updateAgeOnHas: false,
  } as CacheConfig,

  // User preferences - small cache with count-based eviction
  preferences: {
    max: 20, // Maximum 20 entries
    ttl: 1800000, // 30 minutes
    updateAgeOnGet: true,
    updateAgeOnHas: true,
  } as CacheConfig,
} as const;

/**
 * Cached TTS response data structure
 */
interface CachedTTSResponse {
  audioData: ArrayBuffer;
  format: string;
  voice: VoiceOption;
  speed: number;
  timestamp: number;
  size: number;
}

/**
 * Cached server health data
 */
interface CachedServerHealth {
  status: "healthy" | "unhealthy" | "unknown";
  latency: number;
  timestamp: number;
  version?: string;
}

/**
 * Enhanced caching system with LRU algorithm
 */
class TTSCacheManager {
  private ttsCache: LRUCache<string, CachedTTSResponse>;
  private healthCache: LRUCache<string, CachedServerHealth>;
  private voiceCache: LRUCache<string, unknown>;
  private preferenceCache: LRUCache<string, unknown>;

  constructor() {
    // Initialize LRU caches with optimized configurations
    this.ttsCache = new LRUCache<string, CachedTTSResponse>({
      maxSize: CACHE_CONFIGS.ttsResponse.maxSize,
      ttl: CACHE_CONFIGS.ttsResponse.ttl,
      updateAgeOnGet: CACHE_CONFIGS.ttsResponse.updateAgeOnGet,
      updateAgeOnHas: CACHE_CONFIGS.ttsResponse.updateAgeOnHas,
      sizeCalculation: CACHE_CONFIGS.ttsResponse.sizeCalculation,
    });

    this.healthCache = new LRUCache<string, CachedServerHealth>({
      max: CACHE_CONFIGS.serverHealth.max,
      ttl: CACHE_CONFIGS.serverHealth.ttl,
      updateAgeOnGet: CACHE_CONFIGS.serverHealth.updateAgeOnGet,
      updateAgeOnHas: CACHE_CONFIGS.serverHealth.updateAgeOnHas,
    });

    this.voiceCache = new LRUCache<string, unknown>({
      max: CACHE_CONFIGS.voiceConfig.max,
      ttl: CACHE_CONFIGS.voiceConfig.ttl,
      updateAgeOnGet: CACHE_CONFIGS.voiceConfig.updateAgeOnGet,
      updateAgeOnHas: CACHE_CONFIGS.voiceConfig.updateAgeOnHas,
    });

    this.preferenceCache = new LRUCache<string, unknown>({
      max: CACHE_CONFIGS.preferences.max,
      ttl: CACHE_CONFIGS.preferences.ttl,
      updateAgeOnGet: CACHE_CONFIGS.preferences.updateAgeOnGet,
      updateAgeOnHas: CACHE_CONFIGS.preferences.updateAgeOnHas,
    });
  }

  /**
   * Create a cache key for TTS requests
   * Uses MD5 hash for consistent, collision-resistant keys
   */
  private createTTSCacheKey(request: TTSRequest): string {
    const keyData = {
      text: request.text,
      voice: request.voice ?? "af_heart",
      speed: request.speed ?? 1.0,
      lang: request.lang ?? "en-us",
      format: request.format ?? "wav",
    };

    const keyString = JSON.stringify(keyData);
    return createHash("md5").update(keyString).digest("hex");
  }

  /**
   * Cache TTS response for future use
   */
  cacheTTSResponse(request: TTSRequest, audioData: ArrayBuffer): void {
    const key = this.createTTSCacheKey(request);
    const cachedData: CachedTTSResponse = {
      audioData,
      format: request.format ?? "wav",
      voice: (request.voice ?? "af_heart") as VoiceOption,
      speed: request.speed ?? 1.0,
      timestamp: Date.now(),
      size: audioData.byteLength,
    };

    this.ttsCache.set(key, cachedData);
  }

  /**
   * Retrieve cached TTS response
   */
  getCachedTTSResponse(request: TTSRequest): CachedTTSResponse | null {
    const key = this.createTTSCacheKey(request);
    return this.ttsCache.get(key) ?? null;
  }

  /**
   * Check if TTS response is cached
   */
  hasCachedTTSResponse(request: TTSRequest): boolean {
    const key = this.createTTSCacheKey(request);
    return this.ttsCache.has(key);
  }

  /**
   * Cache server health status
   */
  cacheServerHealth(serverUrl: string, health: CachedServerHealth): void {
    const key = createHash("md5").update(serverUrl).digest("hex");
    this.healthCache.set(key, health);
  }

  /**
   * Get cached server health
   */
  getCachedServerHealth(serverUrl: string): CachedServerHealth | null {
    const key = createHash("md5").update(serverUrl).digest("hex");
    return this.healthCache.get(key) ?? null;
  }

  /**
   * Cache voice configuration
   */
  cacheVoiceConfig(voice: VoiceOption, config: unknown): void {
    this.voiceCache.set(voice, config);
  }

  /**
   * Get cached voice configuration
   */
  getCachedVoiceConfig(voice: VoiceOption): unknown | null {
    return this.voiceCache.get(voice) ?? null;
  }

  /**
   * Cache user preferences
   */
  cachePreferences(userId: string, preferences: Partial<TTSConfig>): void {
    this.preferenceCache.set(userId, preferences);
  }

  /**
   * Get cached preferences
   */
  getCachedPreferences(userId: string): Partial<TTSConfig> | null {
    return (this.preferenceCache.get(userId) as Partial<TTSConfig>) ?? null;
  }

  /**
   * Clear all caches
   */
  clearAll(): void {
    this.ttsCache.clear();
    this.healthCache.clear();
    this.voiceCache.clear();
    this.preferenceCache.clear();
  }

  /**
   * Clear specific cache type
   */
  clearCache(type: "tts" | "health" | "voice" | "preferences"): void {
    switch (type) {
      case "tts":
        this.ttsCache.clear();
        break;
      case "health":
        this.healthCache.clear();
        break;
      case "voice":
        this.voiceCache.clear();
        break;
      case "preferences":
        this.preferenceCache.clear();
        break;
    }
  }

  /**
   * Get cache statistics for monitoring
   */
  getStats() {
    return {
      tts: {
        size: this.ttsCache.size,
        max: this.ttsCache.max,
        calculatedSize: this.ttsCache.calculatedSize,
      },
      health: {
        size: this.healthCache.size,
        max: this.healthCache.max,
      },
      voice: {
        size: this.voiceCache.size,
        max: this.voiceCache.max,
      },
      preferences: {
        size: this.preferenceCache.size,
        max: this.preferenceCache.max,
      },
    };
  }

  /**
   * Cleanup expired entries (manual cleanup for debugging)
   */
  cleanup(): void {
    // LRU cache handles cleanup automatically, but we can force it
    this.ttsCache.purgeStale();
    this.healthCache.purgeStale();
    this.voiceCache.purgeStale();
    this.preferenceCache.purgeStale();
  }
}

// Singleton instance for global use
export const cacheManager = new TTSCacheManager();

// Export types for use in other modules
export type { CachedTTSResponse, CachedServerHealth };
